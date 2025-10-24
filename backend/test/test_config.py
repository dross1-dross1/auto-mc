from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from backend.config import load_settings


class TestConfig(unittest.TestCase):
    def test_load_from_config_json(self) -> None:
        tmp = Path("settings/config.json").resolve()
        try:
            data = {
                "host": "0.0.0.0",
                "port": 9001,
                "log_level": "debug",
                "password": "testpw",
                "max_chat_sends_per_sec": 7,
                "default_action_spacing_ms": 150,
                "acquire_poll_interval_ms": 500,
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
                
            }
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data), encoding="utf-8")
            s = load_settings()
            self.assertEqual(s.host, "0.0.0.0")
            self.assertEqual(s.port, 9001)
            self.assertEqual(s.log_level, "DEBUG")
            self.assertEqual(s.password, "testpw")
            self.assertEqual(s.max_chat_sends_per_sec, 7)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()


