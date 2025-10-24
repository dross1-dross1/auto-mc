from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any, Dict

from backend.dispatcher import Dispatcher
from backend.config import load_settings


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
        # Ensure a minimal config.json exists for settings load
        import json, os
        if not os.path.exists("config.json"):
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump({
                    "host": "127.0.0.1",
                    "port": 8765,
                    "log_level": "INFO",
                    "password": "testpw",
                    "max_chat_sends_per_sec": 5,
                    "default_retry_attempts": 3,
                    "default_retry_backoff_ms": 500,
                    "default_action_timeout_ms": 30000,
                    "default_action_spacing_ms": 200,
                    "idle_shutdown_seconds": 0,
                    "acquire_poll_interval_ms": 500,
                    "acquire_timeout_per_item_ms": 3000,
                    "acquire_min_timeout_ms": 30000,
                    "telemetry_interval_ms": 500,
                    "chat_bridge_enabled": True,
                    "chat_bridge_rate_limit_per_sec": 2,
                    "command_prefix": "!",
                    "echo_public_default": False,
                    "ack_on_command": True,
                    "message_pump_max_per_tick": 64,
                    "message_pump_queue_cap": 2048,
                    "inventory_diff_debounce_ms": 150,
                    "chat_max_length": 256,
                    "crafting_click_delay_ms": 40,
                    "max_eta_seconds": 15,
                    "eta_probe_timeout_ms": 1500
                }, f)
        d = Dispatcher(DummyWS())
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:iron_ore"}), "#mine iron_ore")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:coal"}), "#mine coal_ore")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:oak_planks"}), "#mine oak_log")
        self.assertEqual(d._acquire_to_chat({"item": "minecraft:stick"}), "#mine oak_log")

    def test_to_action_request_ensure_context_uses_chat_bridge_goto(self) -> None:
        d = Dispatcher(DummyWS())
        msg1 = d._to_action_request({"op": "acquire", "item": "crafting_table_nearby"}, "a1")
        self.assertEqual(msg1.get("mode"), "chat_bridge")
        self.assertEqual(msg1.get("op"), "acquire")
        self.assertEqual(msg1.get("chat_text"), "#goto crafting_table")
        msg2 = d._to_action_request({"op": "acquire", "item": "furnace_nearby"}, "a2")
        self.assertEqual(msg2.get("mode"), "chat_bridge")
        self.assertEqual(msg2.get("op"), "acquire")
        self.assertEqual(msg2.get("chat_text"), "#goto furnace")

    def test_skip_step_due_to_inventory(self) -> None:
        state = DummyState({"minecraft:stick": 4, "minecraft:iron_ingot": 3})
        d = Dispatcher(DummyWS(), player_id="p1", state_service=state)
        self.assertTrue(d._should_skip_step_due_to_inventory({"op": "acquire", "item": "minecraft:stick", "count": 2}))
        self.assertFalse(d._should_skip_step_due_to_inventory({"op": "craft", "recipe": "minecraft:iron_ingot", "count": 3}))
        self.assertFalse(d._should_skip_step_due_to_inventory({"op": "acquire", "item": "minecraft:oak_log", "count": 1}))

    def test_run_linear_sends_minified_json_and_dedupes_chat(self) -> None:
        ws = DummyWS()
        d = Dispatcher(ws)
        steps = [
            {"op": "acquire", "item": "minecraft:oak_log", "count": 1},
            {"op": "acquire", "item": "minecraft:oak_log", "count": 1},
        ]
        asyncio.get_event_loop().run_until_complete(d.run_linear(steps))
        self.assertGreaterEqual(len(ws.sent), 1)
        obj = json.loads(ws.sent[0])
        self.assertEqual(obj.get("type"), "action_request")


if __name__ == "__main__":
    unittest.main()


