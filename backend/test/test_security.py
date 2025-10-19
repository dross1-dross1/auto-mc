from __future__ import annotations

import unittest


class DummySettings:
    def __init__(self, allow_remote: bool, auth_token: str | None) -> None:
        self.allow_remote = allow_remote
        self.auth_token = auth_token


class TestSecurityPolicy(unittest.TestCase):
    def test_remote_denied_when_not_allowed(self) -> None:
        from backend.security import decide_accept_connection  # to be implemented

        settings = DummySettings(allow_remote=False, auth_token=None)
        # Simulate a remote IPv4 address
        accepted, reason = decide_accept_connection(("192.168.1.10", 50000), settings, {"type": "handshake", "player_id": "p1"})
        self.assertFalse(accepted)
        self.assertEqual(reason, "remote_disabled")

    def test_local_allowed_without_token_even_when_token_configured(self) -> None:
        from backend.security import decide_accept_connection

        settings = DummySettings(allow_remote=False, auth_token="secret")
        accepted, reason = decide_accept_connection(("127.0.0.1", 50000), settings, {"type": "handshake", "player_id": "p1"})
        self.assertTrue(accepted)
        self.assertEqual(reason, "ok")

    def test_remote_requires_correct_auth_token_when_enabled(self) -> None:
        from backend.security import decide_accept_connection

        settings = DummySettings(allow_remote=True, auth_token="secret")
        # Wrong/missing token rejected for remote
        accepted1, reason1 = decide_accept_connection(("10.0.0.5", 40000), settings, {"type": "handshake", "player_id": "p1"})
        self.assertFalse(accepted1)
        self.assertEqual(reason1, "auth_failed")

        accepted2, reason2 = decide_accept_connection(("10.0.0.5", 40000), settings, {"type": "handshake", "player_id": "p1", "auth_token": "wrong"})
        self.assertFalse(accepted2)
        self.assertEqual(reason2, "auth_failed")

        accepted3, reason3 = decide_accept_connection(("10.0.0.5", 40000), settings, {"type": "handshake", "player_id": "p1", "auth_token": "secret"})
        self.assertTrue(accepted3)
        self.assertEqual(reason3, "ok")


if __name__ == "__main__":
    unittest.main()


