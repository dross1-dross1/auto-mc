from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from dataclasses import dataclass
from typing import Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve

from .config import configure_logging, load_settings
from .intents import parse_command_text
from .planner import plan_craft
from .dispatcher import Dispatcher


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

    async def start(self) -> None:
        configure_logging(self.settings.log_level)
        host = self.settings.host
        port = self.settings.port

        logger.info("listening on %s:%s", host, port)

        async with serve(self._handle_client, host, port):
            await self._shutdown_event.wait()

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
                    session.player_id = pid
                    logger.info("handshake from player_id=%s", pid)
                    # Optional: could send settings_update later
                    continue

                if mtype == "command":
                    await self._on_command(session, msg)
                    continue

                if mtype == "telemetry_update":
                    await self._on_telemetry(session, msg)
                    continue

                if mtype == "progress_update":
                    await self._on_progress(session, msg)
                    continue

                if mtype == "ping":
                    await self._send_json(websocket, {"type": "pong"})
                    continue

                logger.debug("unhandled message type: %s", mtype)

        except websockets.ConnectionClosedError:
            logger.info("client disconnected: %s", client)
        finally:
            self.sessions.pop(websocket, None)

    async def _on_command(self, session: Session, msg: dict) -> None:
        text: str = msg.get("text", "")
        request_id: str = msg.get("request_id") or str(uuid.uuid4())
        player_id = session.player_id or "unknown"
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
            # stream actions
            dispatcher = Dispatcher(session.websocket)
            await dispatcher.run_linear(steps)
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
        # In a future step, persist/update last telemetry per agent
        logger.debug("telemetry_update from %s: %s", player_id, msg.get("state", {}) )

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
