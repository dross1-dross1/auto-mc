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
from .security import decide_accept_connection
from .tls import build_server_ssl_context
from .storage import StorageCatalog
from .intents import parse_command_text
from .planner import plan_craft
from .dispatcher import Dispatcher
from .state_service import StateService
from .schemas import ChatSend


logger = logging.getLogger("automc.server")


@dataclass
class Session:
    player_id: Optional[str]
    websocket: WebSocketServerProtocol


class BackendServer:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.sessions: Dict[WebSocketServerProtocol, Session] = {}
        self._shutdown_event = asyncio.Event()
        self._idle_task: Optional[asyncio.Task] = None
        self.state = StateService(Path("data/state.json"))
        self.state.load()
        self.storage = StorageCatalog()

    async def start(self) -> None:
        configure_logging(self.settings.log_level)
        host = self.settings.host
        port = self.settings.port

        logger.info("listening on %s:%s", host, port)

        ssl_ctx = build_server_ssl_context(self.settings)
        async with serve(self._handle_client, host, port, ssl=ssl_ctx):
            # Start idle watchdog if enabled
            if self.settings.idle_shutdown_seconds > 0:
                self._idle_task = asyncio.create_task(self._idle_watchdog())
            try:
                await self._shutdown_event.wait()
            finally:
                if self._idle_task is not None:
                    self._idle_task.cancel()
                    try:
                        await self._idle_task
                    except asyncio.CancelledError:
                        pass

    async def stop(self) -> None:
        self._shutdown_event.set()

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        session = Session(player_id=None, websocket=websocket)
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
                    pid = msg.get("player_id")
                    # Replace 'auto' with client UUID if provided later via telemetry; for now set as given
                    session.player_id = pid
                    # Admission control: ALLOW_REMOTE and AUTH_TOKEN
                    accepted, reason = decide_accept_connection(websocket.remote_address, self.settings, msg)
                    if not accepted:
                        logger.info("handshake rejected for %s: %s", pid, reason)
                        try:
                            await websocket.close(code=1008, reason=reason)
                        finally:
                            return
                    logger.info("handshake from player_id=%s", pid)
                    # Optional: could send settings_update later
                    continue

                if mtype == "command":
                    await self._on_command(session, msg)
                    continue

                if mtype == "telemetry_update":
                    # If player_id is 'auto' and state includes a uuid hint, adopt it
                    try:
                        if (session.player_id == "auto"):
                            st = msg.get("state", {})
                            # accept uuid from possible future field, or from equipment/other hints (not present now)
                            uuid_hint = st.get("uuid")
                            if isinstance(uuid_hint, str) and uuid_hint:
                                session.player_id = uuid_hint
                                logger.info("adopted player uuid for session: %s", session.player_id)
                    except Exception:
                        pass
                    await self._on_telemetry(session, msg)
                    continue
                if mtype == "inventory_snapshot":
                    container = msg.get("container") or {}
                    try:
                        self.storage.handle_snapshot(session.player_id or "unknown", container)
                    except Exception:
                        logger.debug("invalid inventory_snapshot ignored")
                    continue

                if mtype == "inventory_diff":
                    try:
                        self.storage.handle_diff(session.player_id or "unknown", msg)
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
                    logger.info("chat_event: %s", msg.get("text"))

        except websockets.ConnectionClosedError:
            logger.info("client disconnected: %s", client)
        finally:
            self.sessions.pop(websocket, None)

    async def _idle_watchdog(self) -> None:
        """Shut the server down if there are no connected clients for a configured duration.

        This is a best-effort idle shutdown to avoid orphaning the port in development.
        """
        assert self.settings.idle_shutdown_seconds >= 0
        timeout_s = self.settings.idle_shutdown_seconds
        if timeout_s == 0:
            return
        no_client_since: Optional[float] = None
        try:
            while True:
                await asyncio.sleep(1)
                has_clients = bool(self.sessions)
                now = asyncio.get_event_loop().time()
                if has_clients:
                    no_client_since = None
                    continue
                if no_client_since is None:
                    no_client_since = now
                    continue
                if now - no_client_since >= timeout_s:
                    logger.info("idle timeout (%ss) reached with no clients; shutting down", timeout_s)
                    await self.stop()
                    return
        except asyncio.CancelledError:
            return

    async def _on_command(self, session: Session, msg: dict) -> None:
        text: str = msg.get("text", "")
        request_id: str = msg.get("request_id") or str(uuid.uuid4())
        player_id = session.player_id or "unknown"
        # If we have a username alias recorded for this uuid, append it for readability
        alias = None
        ps = self.state.get_player_state(player_id)
        try:
            if ps:
                alias = ps.get("state", {}).get("username")
        except Exception:
            alias = None
        if alias:
            logger.info("command from %s(%s): %s", player_id, alias, text)
        else:
            logger.info("command from %s: %s", player_id, text)

        intent = parse_command_text(text)
        if intent and intent.get("type") == "echo":
            await self._send_json(session.websocket, {
                "type": "chat_send",
                "request_id": request_id,
                "player_id": player_id,
                "text": str(intent.get("text", "")),
            })
            return

        if intent and intent.get("type") == "help":
            help_text = (
                "Available commands:\n"
                "!help - Show this help\n"
                "!who - List online agents (uuid and username)\n"
                "!echo <text> - Display text locally (or publicly if configured)\n"
                "!craft <count> <item> - Plan and execute crafting (v0: 2x2 crafts acknowledged, 3x3/smelt pending)\n"
                "!echomulti <name1,name2,...> <message|#cmd|.cmd> - Send chat/command to targets\n"
                "!echoall <message|#cmd|.cmd> - Send chat/command to all online agents\n"
            )
            await self._send_json(session.websocket, {
                "type": "chat_send",
                "request_id": request_id,
                "player_id": player_id,
                "text": help_text,
            })
            return

        if intent and intent.get("type") == "craft_item":
            item_id = str(intent["item"])  # type: ignore[index]
            count = int(intent["count"])  # type: ignore[index]
            steps = plan_craft(item_id, count)
            plan_id = str(uuid.uuid4())
            plan = {
                "type": "plan",
                "plan_id": plan_id,
                "request_id": request_id,
                "steps": steps,
            }
            await self._send_json(session.websocket, plan)
            # stream actions in the background to keep the receive loop responsive
            dispatcher = Dispatcher(session.websocket, player_id=session.player_id, state_service=self.state)
            asyncio.create_task(dispatcher.run_linear(steps))
            return

        if intent and intent.get("type") == "multicast":
            targets = list(intent.get("targets", []))  # type: ignore[assignment]
            payload = str(intent.get("text", ""))
            # Build chat_send and fan out: only to specified player_ids
            out: ChatSend = {
                "type": "chat_send",
                "request_id": request_id,
                "player_id": player_id,
                "text": payload,
            }
            await self._multicast(targets, out)
            return

        if intent and intent.get("type") == "broadcast":
            payload = str(intent.get("text", ""))
            out: ChatSend = {
                "type": "chat_send",
                "request_id": request_id,
                "player_id": player_id,
                "text": payload,
            }
            await self._multicast([], out)
            return

        if intent and intent.get("type") == "who":
            # Build list of online agents from telemetry cache
            try:
                players = []
                for s in self.sessions.values():
                    pid = s.player_id or "unknown"
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
                "player_id": player_id,
                "text": text,
            })
            return

        # Fallback: acknowledge with a polite note
        await self._send_json(session.websocket, {
            "type": "chat_send",
            "request_id": request_id,
            "player_id": player_id,
            "text": f"Unrecognized command: {text}",
        })

    async def _on_telemetry(self, session: Session, msg: dict) -> None:
        player_id = session.player_id or "unknown"
        logger.debug("telemetry_update from %s: %s", player_id, msg.get("state", {}))
        await self.state.update_telemetry(player_id, str(msg.get("ts", "")), msg.get("state", {}))

    async def _on_state_request(self, session: Session, msg: dict) -> None:
        req_id: str = msg.get("request_id", str(uuid.uuid4()))
        target_player: str = msg.get("player_id") or (session.player_id or "unknown")
        selector = msg.get("selector")
        player_state = self.state.get_player_state(target_player)
        payload = {}
        if player_state is not None:
            payload = self.state.select_state(player_state, selector)
        await self._send_json(session.websocket, {
            "type": "state_response",
            "request_id": req_id,
            "player_id": target_player,
            "state": payload,
        })

    async def _on_progress(self, session: Session, msg: dict) -> None:
        player_id = session.player_id or "unknown"
        logger.info(
            "progress_update from %s: action_id=%s status=%s note=%s",
            player_id,
            msg.get("action_id"),
            msg.get("status"),
            msg.get("note"),
        )
        # TODO: correlate with current request/step and advance; v0 just logs

    async def _multicast(self, targets: list[str], message: dict) -> None:
        # Targets can be UUIDs or usernames; resolve usernames using last telemetry
        if not targets:
            uuids = [s.player_id or "unknown" for s in self.sessions.values()]
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
            if (s.player_id or "unknown") in uuids:
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
