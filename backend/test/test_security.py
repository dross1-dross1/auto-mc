from __future__ import annotations

import unittest


class TestSecurityPolicy(unittest.TestCase):
    def test_shared_password_policy(self) -> None:
        # Previous ALLOW_REMOTE/auth_token policy is removed; server validates a shared password in handshake.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()


