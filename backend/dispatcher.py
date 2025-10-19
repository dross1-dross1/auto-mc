from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List

from websockets.server import WebSocketServerProtocol


logger = logging.getLogger("automc.dispatcher")


class Dispatcher:
    def __init__(self, websocket: WebSocketServerProtocol) -> None:
        self.websocket = websocket

    async def run_linear(self, steps: List[Dict[str, Any]]) -> None:
        for step in steps:
            action_id = str(uuid.uuid4())
            msg = self._to_action_request(step, action_id)
            await self.websocket.send(json.dumps(msg, separators=(",", ":")))
            # In v0, we do not wait synchronously for progress; the mod should reply
            await asyncio.sleep(0)  # yield control

    def _to_action_request(self, step: Dict[str, Any], action_id: str) -> Dict[str, Any]:
        op = step.get("op")
        if op in {"acquire", "craft", "smelt"}:
            # For now send as mod_native where appropriate
            return {
                "type": "action_request",
                "action_id": action_id,
                "mode": "mod_native" if op != "acquire" else "chat_bridge",
                "op": op,
                **{k: v for k, v in step.items() if k != "op"},
            }
        # Fallback to chat bridge noop
        return {
            "type": "action_request",
            "action_id": action_id,
            "mode": "chat_bridge",
            "chat_text": "#stop",
        }
