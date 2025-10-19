from __future__ import annotations

import os
import unittest

from backend.config import load_settings


class TestConfig(unittest.TestCase):
    def test_env_overrides(self) -> None:
        # Save and restore environment
        old = dict(os.environ)
        try:
            os.environ["HOST"] = "0.0.0.0"
            os.environ["PORT"] = "9001"
            os.environ["LOG_LEVEL"] = "debug"
            os.environ["ALLOW_REMOTE"] = "true"
            os.environ["MAX_CHAT_SENDS_PER_SEC"] = "7"
            os.environ["DEFAULT_RETRY_ATTEMPTS"] = "5"
            os.environ["IDLE_SHUTDOWN_SECONDS"] = "3"
            s = load_settings()
            self.assertEqual(s.host, "0.0.0.0")
            self.assertEqual(s.port, 9001)
            self.assertEqual(s.log_level, "DEBUG")
            self.assertTrue(s.allow_remote)
            self.assertEqual(s.max_chat_sends_per_sec, 7)
            self.assertEqual(s.default_retry_attempts, 5)
            self.assertEqual(s.idle_shutdown_seconds, 3)
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
