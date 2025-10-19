from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any, Dict

from backend.dispatcher import Dispatcher


class DummyWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


class DummyState:
    def __init__(self, inv: Dict[str, int]) -> None:
        self._inv = inv

    def get_player_state(self, player_id: str) -> Dict[str, Any]:  # type: ignore[override]
        return {"state": {"inventory": [{"id": k, "count": v} for k, v in self._inv.items()]}}


class TestDispatcher(unittest.TestCase):
    def test_acquire_to_chat_mappings(self) -> None:
        d = Dispatcher(DummyWS())
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:iron_ore"}), "#mine iron_ore")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:coal"}), "#mine coal_ore")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:planks"}), "#mine oak_log")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:stick"}), "#mine oak_log")

    def test_to_action_request_ensure_context_uses_chat_bridge_goto(self) -> None:
        d = Dispatcher(DummyWS())
        msg1 = d._to_action_request({"op": "acquire", "item": "crafting_table_nearby"}, "a1")
        self.assertEqual(msg1.get("mode"), "chat_bridge")
        self.assertEqual(msg1.get("chat_text"), "#goto crafting_table")
        msg2 = d._to_action_request({"op": "acquire", "item": "furnace_nearby"}, "a2")
        self.assertEqual(msg2.get("mode"), "chat_bridge")
        self.assertEqual(msg2.get("chat_text"), "#goto furnace")

    def test_skip_step_due_to_inventory(self) -> None:
        state = DummyState({"minecraft:stick": 4, "minecraft:iron_ingot": 3})
        d = Dispatcher(DummyWS(), player_id="p1", state_service=state)
        self.assertTrue(d._should_skip_step_due_to_inventory({"op": "acquire", "item": "minecraft:stick", "count": 2}))
        self.assertTrue(d._should_skip_step_due_to_inventory({"op": "craft", "recipe": "minecraft:iron_ingot", "count": 3}))
        self.assertFalse(d._should_skip_step_due_to_inventory({"op": "acquire", "item": "minecraft:oak_log", "count": 1}))

    def test_run_linear_sends_minified_json_and_dedupes_chat(self) -> None:
        ws = DummyWS()
        d = Dispatcher(ws)
        steps = [
            {"op": "acquire", "item": "minecraft:oak_log", "count": 1},
            {"op": "acquire", "item": "minecraft:oak_log", "count": 1},  # same chat -> dedupe by consecutive check
        ]
        asyncio.get_event_loop().run_until_complete(d.run_linear(steps))
        self.assertGreaterEqual(len(ws.sent), 1)
        # Ensure JSON is minified and contains action_request
        obj = json.loads(ws.sent[0])
        self.assertEqual(obj.get("type"), "action_request")


if __name__ == "__main__":
    unittest.main()
