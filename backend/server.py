from __future__ import annotations

"""AutoMinecraft backend server.

Purpose: WebSocket gateway that accepts client connections, parses chat commands
into intents, plans deterministic steps, and streams actions to the client.

How: One connection per agent; keeps lightweight session state; persists last
telemetry; optional idle shutdown for dev.

Engineering notes: Validate inputs defensively; keep handlers small; structured
logging with request and player ids; avoid blocking the event loop.

"""

import asyncio
import json
import logging
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve

from .config import configure_logging, load_settings
from .storage import StorageCatalog
from .intents import parse_command_text
from .planner import plan_craft
from .dispatcher import Dispatcher
from .state_service import StateService
from .schemas import ChatSend


logger = logging.getLogger("automc.server")


@dataclass
class Session:
    player_uuid: Optional[str]
    websocket: WebSocketServerProtocol
    last_eta_ms: Optional[int] = None


class BackendServer:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.sessions: Dict[WebSocketServerProtocol, Session] = {}
        self._shutdown_event = asyncio.Event()
        self._idle_task: Optional[asyncio.Task] = None
        self.state = StateService(Path("data/state.json"))
        self.state.load()
        self.storage = StorageCatalog()

    def _player_label(self, player_id: Optional[str]) -> str:
        pid = player_id or "unknown"
        try:
            ps = self.state.get_player_state(pid)
            uname = ps.get("state", {}).get("username") if ps else None
            if isinstance(uname, str) and uname:
                return f"{pid} ({uname})"
        except Exception:
            pass
        return pid

    async def start(self) -> None:
        configure_logging(self.settings.log_level)
        host = self.settings.host
        port = self.settings.port

        logger.info("listening on %s:%s", host, port)

        async with serve(self._handle_client, host, port, ssl=None):
            try:
                await self._shutdown_event.wait()
            finally:
                pass

    async def stop(self) -> None:
        self._shutdown_event.set()

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        session = Session(player_uuid=None, websocket=websocket)
        self.sessions[websocket] = session
        client = f"{websocket.remote_address}"
        logger.info("client connected: %s", client)
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except Exception:
                    logger.warning("invalid JSON from %s", client)
                    continue

                mtype = msg.get("type")
                if mtype == "handshake":
                    pid = msg.get("player_uuid")
                    provided_pw = msg.get("password")
                    pname = msg.get("player_name")
                    # Validate password strictly
                    if not isinstance(provided_pw, str) or provided_pw != self.settings.password:
                        logger.info("handshake rejected for %s: auth_failed", pid)
                        try:
                            await websocket.close(code=1008, reason="auth_failed")
                        finally:
                            return
                    session.player_uuid = pid if isinstance(pid, str) and pid else None
                    # If a player name is provided in handshake, persist it so labels include it immediately
                    try:
                        if isinstance(pname, str) and pname and isinstance(pid, str) and pid:
                            await self.state.update_telemetry(pid, "", {"username": pname})
                    except Exception:
                        pass
                    # Log using uuid (name) if we have a cached username
                    logger.info("handshake from %s", self._player_label(session.player_uuid))
                    # Immediately push flattened client settings so the mod has no local fallbacks
                    try:
                        await self._send_json(session.websocket, {
                            "type": "settings_update",
                            "settings": {
                                "telemetry_interval_ms": self.settings.telemetry_interval_ms,
                                "chat_bridge_enabled": self.settings.chat_bridge_enabled,
                                "chat_bridge_rate_limit_per_sec": self.settings.chat_bridge_rate_limit_per_sec,
                                "command_prefix": self.settings.command_prefix,
                                "echo_public_default": self.settings.echo_public_default,
                                "ack_on_command": self.settings.ack_on_command,
                                "message_pump_max_per_tick": self.settings.message_pump_max_per_tick,
                                "message_pump_queue_cap": self.settings.message_pump_queue_cap,
                                "inventory_diff_debounce_ms": self.settings.inventory_diff_debounce_ms,
                                "chat_max_length": self.settings.chat_max_length,
                                "crafting_click_delay_ms": self.settings.crafting_click_delay_ms,
                                "feedback_prefix": self.settings.feedback_prefix,
                            },
                        })
                    except Exception:
                        logger.debug("failed to send initial settings_update")
                    continue

                if mtype == "command":
                    await self._on_command(session, msg)
                    continue

                if mtype == "telemetry_update":
                    # If player_uuid is 'auto' and state includes a uuid hint, adopt it
                    try:
                        if (session.player_uuid == "auto"):
                            st = msg.get("state", {})
                            # accept uuid from possible future field, or from equipment/other hints (not present now)
                            uuid_hint = st.get("uuid")
                            if isinstance(uuid_hint, str) and uuid_hint:
                                session.player_uuid = uuid_hint
                                logger.info("adopted player uuid for session: %s", session.player_uuid)
                    except Exception:
                        pass
                    await self._on_telemetry(session, msg)
                    continue
                if mtype == "inventory_snapshot":
                    container = msg.get("container") or {}
                    try:
                        self.storage.handle_snapshot(session.player_uuid or "unknown", container)
                    except Exception:
                        logger.debug("invalid inventory_snapshot ignored")
                    continue

                if mtype == "inventory_diff":
                    try:
                        self.storage.handle_diff(session.player_uuid or "unknown", msg)
                    except Exception:
                        logger.debug("invalid inventory_diff ignored")
                    continue

                if mtype == "state_request":
                    await self._on_state_request(session, msg)
                    continue

                if mtype == "progress_update":
                    await self._on_progress(session, msg)
                    continue

                if mtype == "ping":
                    await self._send_json(websocket, {"type": "pong"})
                    continue

                logger.debug("unhandled message type: %s", mtype)
                # Log chat_event minimally (already handled client-side)
                if mtype == "chat_event":
                    text = str(msg.get("text", ""))
                    # Parse Baritone ETA lines to capture last ETA
                    try:
                        # Examples: "Next segment: 6.6s (131 ticks)\nGoal: 10.6s (213 ticks)"
                        import re
                        m = re.search(r"Goal:\s*([0-9]+(?:\.[0-9]+)?)s", text)
                        if m:
                            sec = float(m.group(1))
                            session.last_eta_ms = int(sec * 1000)
                    except Exception:
                        pass
                    logger.info("chat_event: %s", text)

        except websockets.ConnectionClosedError:
            logger.info("client disconnected: %s", client)
        finally:
            self.sessions.pop(websocket, None)

    

    async def _on_command(self, session: Session, msg: dict) -> None:
        text: str = msg.get("text", "")
        request_id: str = msg.get("request_id") or str(uuid.uuid4())
        player_id = session.player_uuid or "unknown"
        # Log using uuid (name) when username is known
        logger.info("command from %s: %s", self._player_label(player_id), text)

        intent = parse_command_text(text)
        if intent and intent.get("type") == "echo":
            prefix = self.settings.feedback_prefix or ""
            text_out = f"{prefix}{str(intent.get('text', ''))}"
            await self._send_json(session.websocket, {
                "type": "chat_send",
                "request_id": request_id,
                "player_uuid": player_id,
                "text": text_out,
            })
            return

        if intent and intent.get("type") == "help":
            prefix = self.settings.feedback_prefix or ""
            help_text = (
                "Available commands:\n"
                "!help - Show this help\n"
                "!who - List online agents (uuid and username)\n"
                "!stop - Halt current Baritone action\n"
                "!connect <host:port> <password> - Connect client to backend\n"
                "!disconnect - Disconnect client from backend\n"
                "!echo <text> - Display text locally (or publicly if configured)\n"
                "!get <item> <count> - Plan and execute acquisition/crafting (2x2 crafts acknowledged, 3x3/smelt pending)\n"
                "!echomulti <name1,name2,...> <message|#cmd|.cmd> - Send chat/command to targets\n"
                "!echoall <message|#cmd|.cmd> - Send chat/command to all online agents\n"
                "!settings <json> - Apply runtime settings to clients (rate limits, intervals)\n"
            )
            await self._send_json(session.websocket, {
                "type": "chat_send",
                "request_id": request_id,
                "player_uuid": player_id,
                "text": f"{prefix}{help_text}",
            })
            return

        if intent and intent.get("type") == "craft_item":
            item_id = str(intent["item"])  # type: ignore[index]
            count = int(intent["count"])  # type: ignore[index]
            # Build current inventory counts from last telemetry for inventory-aware planning
            inv_counts: Dict[str, int] = {}
            try:
                ps = self.state.get_player_state(player_id)
                inv_list = (ps or {}).get("state", {}).get("inventory", [])
                if isinstance(inv_list, list):
                    for slot in inv_list:
                        try:
                            iid = str(slot.get("id"))
                            c = int(slot.get("count", 0))
                            if iid:
                                inv_counts[iid] = inv_counts.get(iid, 0) + c
                        except Exception:
                            continue
            except Exception:
                inv_counts = {}
            steps = plan_craft(item_id, count, inventory_counts=inv_counts)
            plan_id = str(uuid.uuid4())
            plan = {
                "type": "plan",
                "plan_id": plan_id,
                "request_id": request_id,
                "steps": steps,
            }
            await self._send_json(session.websocket, plan)
            # stream actions in the background to keep the receive loop responsive
            # Track action_id -> (request_id, step) for basic progress bookkeeping
            action_index: dict[str, dict] = {}
            def _on_action_send(aid: str, step: dict) -> None:
                action_index[aid] = {"request_id": request_id, "step": step}

            dispatcher = Dispatcher(
                session.websocket,
                player_id=session.player_uuid,
                state_service=self.state,
                on_action_send=_on_action_send,
            )
            # Store the index on the session object for later lookups
            setattr(session, "_action_index", action_index)
            asyncio.create_task(dispatcher.run_linear(steps))
            return

        if intent and intent.get("type") == "multicast":
            targets = list(intent.get("targets", []))  # type: ignore[assignment]
            payload = str(intent.get("text", ""))
            # Build action_request chat_bridge and fan out to specified targets
            out = {
                "type": "action_request",
                "action_id": str(uuid.uuid4()),
                "mode": "chat_bridge",
                "op": "chat",
                "chat_text": payload,
            }
            await self._multicast(targets, out)
            return

        if intent and intent.get("type") == "broadcast":
            payload = str(intent.get("text", ""))
            out = {
                "type": "action_request",
                "action_id": str(uuid.uuid4()),
                "mode": "chat_bridge",
                "op": "chat",
                "chat_text": payload,
            }
            await self._multicast([], out)
            return

        if intent and intent.get("type") == "stop":
            # Force stop current Baritone action for this client
            await self._send_json(session.websocket, {
                "type": "action_request",
                "action_id": str(uuid.uuid4()),
                "mode": "chat_bridge",
                "op": "chat",
                "chat_text": "#stop",
            })
            return

        if intent and intent.get("type") == "who":
            # Build list of online agents from telemetry cache
            try:
                players = []
                for s in self.sessions.values():
                    pid = s.player_uuid or "unknown"
                    ps = self.state.get_player_state(pid)
                    uname = ps.get("state", {}).get("username") if ps else None
                    if isinstance(uname, str) and uname:
                        players.append(f"{pid} ({uname})")
                    else:
                        players.append(pid)
                text = "Online agents:\n" + ("\n".join(players) if players else "<none>")
            except Exception:
                text = "Online agents: <unavailable>"
            await self._send_json(session.websocket, {
                "type": "chat_send",
                "request_id": request_id,
                "player_uuid": player_id,
                "text": f"{self.settings.feedback_prefix}{text}",
            })
            return

        # Admin: !settings {json}
        if text.startswith("!settings "):
            try:
                payload = json.loads(text[len("!settings "):].strip())
                # Merge with current flattened settings
                merged = {
                    "telemetry_interval_ms": self.settings.telemetry_interval_ms,
                    "chat_bridge_enabled": self.settings.chat_bridge_enabled,
                    "chat_bridge_rate_limit_per_sec": self.settings.chat_bridge_rate_limit_per_sec,
                    "command_prefix": self.settings.command_prefix,
                    "echo_public_default": self.settings.echo_public_default,
                    "ack_on_command": self.settings.ack_on_command,
                    "message_pump_max_per_tick": self.settings.message_pump_max_per_tick,
                    "message_pump_queue_cap": self.settings.message_pump_queue_cap,
                    "inventory_diff_debounce_ms": self.settings.inventory_diff_debounce_ms,
                    "chat_max_length": self.settings.chat_max_length,
                    "crafting_click_delay_ms": self.settings.crafting_click_delay_ms,
                }
                if isinstance(payload, dict):
                    merged.update(payload)
                await self._send_json(session.websocket, {
                    "type": "settings_update",
                    "settings": merged,
                })
            except Exception:
                await self._send_json(session.websocket, {
                    "type": "chat_send",
                    "request_id": request_id,
                    "player_uuid": player_id,
                    "text": "Invalid settings JSON",
                })
            return

        # Fallback: acknowledge with a polite note
        await self._send_json(session.websocket, {
            "type": "chat_send",
            "request_id": request_id,
            "player_uuid": player_id,
            "text": f"Unrecognized command: {text}",
        })

    async def _on_telemetry(self, session: Session, msg: dict) -> None:
        player_id = session.player_uuid or "unknown"
        logger.debug("telemetry_update from %s: %s", player_id, msg.get("state", {}))
        await self.state.update_telemetry(player_id, str(msg.get("ts", "")), msg.get("state", {}))

    async def _on_state_request(self, session: Session, msg: dict) -> None:
        req_id: str = msg.get("request_id", str(uuid.uuid4()))
        target_player: str = msg.get("player_uuid") or (session.player_uuid or "unknown")
        selector = msg.get("selector")
        player_state = self.state.get_player_state(target_player)
        payload = {}
        if player_state is not None:
            payload = self.state.select_state(player_state, selector)
        await self._send_json(session.websocket, {
            "type": "state_response",
            "request_id": req_id,
            "player_uuid": target_player,
            "state": payload,
        })

    async def _on_progress(self, session: Session, msg: dict) -> None:
        player_id = session.player_uuid or "unknown"
        logger.info(
            "progress_update from %s: action_id=%s status=%s note=%s",
            self._player_label(player_id),
            msg.get("action_id"),
            msg.get("status"),
            msg.get("note"),
        )
        try:
            idx = getattr(session, "_action_index", {})
            aid = str(msg.get("action_id"))
            if aid and aid in idx:
                rec = idx[aid]
                logger.info(
                    "request %s step %s -> %s",
                    rec.get("request_id"),
                    rec.get("step"),
                    msg.get("status"),
                )
                # Optionally drop the entry on terminal status
                if msg.get("status") in {"ok", "fail", "skipped", "cancelled"}:
                    idx.pop(aid, None)
        except Exception:
            pass

    async def _multicast(self, targets: list[str], message: dict) -> None:
        # Targets can be UUIDs or usernames; resolve usernames using last telemetry
        if not targets:
            uuids = [s.player_uuid or "unknown" for s in self.sessions.values()]
        else:
            # Build uuid set by mapping names to uuids where applicable
            uuids = []
            name_to_uuid = {}
            try:
                for uuid_key, state in (self.state._last_telemetry or {}).items():  # type: ignore[attr-defined]
                    uname = state.get("state", {}).get("username")
                    if isinstance(uname, str) and uname:
                        name_to_uuid[uname] = uuid_key
            except Exception:
                pass
            for t in targets:
                if t in name_to_uuid:
                    uuids.append(name_to_uuid[t])
                else:
                    uuids.append(t)
        for s in list(self.sessions.values()):
            if (s.player_uuid or "unknown") in uuids:
                try:
                    await self._send_json(s.websocket, message)
                except Exception:
                    continue

    async def _send_json(self, websocket: WebSocketServerProtocol, obj: dict) -> None:
        await websocket.send(json.dumps(obj, separators=(",", ":")))


def main() -> None:
    server = BackendServer()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _signal_handler() -> None:
        logger.info("shutdown requested")
        loop.create_task(server.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Signals not supported on some platforms (e.g., Windows)
            pass

    try:
        loop.run_until_complete(server.start())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
