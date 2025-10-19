from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List

from websockets.server import WebSocketServerProtocol
from .config import load_settings


logger = logging.getLogger("automc.dispatcher")


class Dispatcher:
    def __init__(self, websocket: WebSocketServerProtocol) -> None:
        self.websocket = websocket
        self.settings = load_settings()

    async def run_linear(self, steps: List[Dict[str, Any]]) -> None:
        spacing = max(0, int(self.settings.default_action_spacing_ms)) / 1000.0
        for step in steps:
            action_id = str(uuid.uuid4())
            msg = self._to_action_request(step, action_id)
            await self.websocket.send(json.dumps(msg, separators=(",", ":")))
            # In v0, we do not wait synchronously for progress; the mod should reply
            if spacing > 0:
                await asyncio.sleep(spacing)
            else:
                await asyncio.sleep(0)  # yield control

    def _to_action_request(self, step: Dict[str, Any], action_id: str) -> Dict[str, Any]:
        op = step.get("op")
        if op == "acquire":
            chat_text = self._acquire_to_chat(step)
            return {
                "type": "action_request",
                "action_id": action_id,
                "mode": "chat_bridge",
                "op": op,
                "chat_text": chat_text,
                **{k: v for k, v in step.items() if k not in {"op"}},
            }
        if op in {"craft", "smelt"}:
            return {
                "type": "action_request",
                "action_id": action_id,
                "mode": "mod_native",
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

    def _acquire_to_chat(self, step: Dict[str, Any]) -> str:
        """Map acquire step to a Baritone chat command."""
        item: str = str(step.get("item", "")).lower()
        # Basic mappings to mine something useful for the desired resource
        item_to_target = {
            "minecraft:iron_ore": "iron_ore",
            "minecraft:coal": "coal_ore",
            "minecraft:coal_ore": "coal_ore",
            "minecraft:cobblestone": "stone",
            "minecraft:planks": "oak_log",
            "minecraft:stick": "oak_log",
            "minecraft:log": "oak_log",
        }
        if item in item_to_target:
            return f"#mine {item_to_target[item]}"
        if item.startswith("minecraft:"):
            return f"#mine {item.split(':', 1)[1]}"
        if item:
            return f"#mine {item}"
        # Position-based acquire (rare in v0)
        pos = step.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            x, y, z = pos
            return f"#mine {x} {y} {z}"
        return "#stop"
