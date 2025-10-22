from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from backend.config import load_settings


class TestConfig(unittest.TestCase):
    def test_load_from_config_json(self) -> None:
        tmp = Path("config.json").resolve()
        try:
            data = {
                "host": "0.0.0.0",
                "port": 9001,
                "log_level": "debug",
                "allow_remote": True,
                "tls_enabled": False,
                "tls_cert_file": None,
                "tls_key_file": None,
                "max_chat_sends_per_sec": 7,
                "default_retry_attempts": 5,
                "default_retry_backoff_ms": 400,
                "default_action_timeout_ms": 25000,
                "default_action_spacing_ms": 150,
                "idle_shutdown_seconds": 3,
                "acquire_poll_interval_ms": 500,
                "acquire_timeout_per_item_ms": 3000,
                "acquire_min_timeout_ms": 30000,
                "client_settings": {
                    "backend_url": "ws://127.0.0.1:8765",
                    "telemetry_interval_ms": 500,
                    "chat_bridge_enabled": True,
                    "chat_bridge_rate_limit_per_sec": 2,
                    "command_prefix": "!",
                    "echo_public_default": False,
                    "ack_on_command": True,
                    # Required client runtime parameters
                    "message_pump_max_per_tick": 64,
                    "message_pump_queue_cap": 2048,
                    "inventory_diff_debounce_ms": 150,
                    "chat_max_length": 256,
                    "crafting_click_delay_ms": 40
                }
            }
            tmp.write_text(json.dumps(data), encoding="utf-8")
            s = load_settings()
            self.assertEqual(s.host, "0.0.0.0")
            self.assertEqual(s.port, 9001)
            self.assertEqual(s.log_level, "DEBUG")
            self.assertTrue(s.allow_remote)
            self.assertEqual(s.max_chat_sends_per_sec, 7)
            self.assertEqual(s.default_retry_attempts, 5)
            self.assertEqual(s.idle_shutdown_seconds, 3)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()


