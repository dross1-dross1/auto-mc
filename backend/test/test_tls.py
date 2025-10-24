from __future__ import annotations

import unittest


class TestTLS(unittest.TestCase):
    def test_tls_build_returns_none(self) -> None:
        from backend.tls import build_server_ssl_context

        class DummySettings: pass

        self.assertIsNone(build_server_ssl_context(DummySettings()))


if __name__ == "__main__":
    unittest.main()


