from __future__ import annotations

import tempfile
import unittest


class DummySettings:
    def __init__(self, tls_enabled: bool, cert: str | None, key: str | None) -> None:
        self.tls_enabled = tls_enabled
        self.tls_cert_file = cert
        self.tls_key_file = key


class TestTLS(unittest.TestCase):
    def test_build_context_disabled_returns_none(self) -> None:
        from backend.tls import build_server_ssl_context  # to be implemented

        settings = DummySettings(False, None, None)
        ctx = build_server_ssl_context(settings)
        self.assertIsNone(ctx)

    def test_build_context_missing_files_raises(self) -> None:
        from backend.tls import build_server_ssl_context

        settings = DummySettings(True, "missing_cert.pem", "missing_key.pem")
        with self.assertRaises((FileNotFoundError, ValueError)):
            _ = build_server_ssl_context(settings)

    def test_build_context_paths_present_but_invalid_raises_ssl(self) -> None:
        # Create empty files to ensure existence; loading should fail with an SSL error or ValueError
        from backend.tls import build_server_ssl_context
        with tempfile.TemporaryDirectory() as td:
            cert = td + "/cert.pem"
            key = td + "/key.pem"
            open(cert, "w", encoding="utf-8").close()
            open(key, "w", encoding="utf-8").close()
            settings = DummySettings(True, cert, key)
            with self.assertRaises(Exception):
                _ = build_server_ssl_context(settings)


if __name__ == "__main__":
    unittest.main()


