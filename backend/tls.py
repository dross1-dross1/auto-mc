from __future__ import annotations

"""TLS utilities for the WebSocket server.

Purpose: Build an SSL context from settings when TLS is enabled.
"""

import os
import ssl
from typing import Any, Optional


def build_server_ssl_context(settings: Any) -> Optional[ssl.SSLContext]:
    if not getattr(settings, "tls_enabled", False):
        return None
    cert_file = getattr(settings, "tls_cert_file", None)
    key_file = getattr(settings, "tls_key_file", None)
    if not cert_file or not key_file:
        raise ValueError("TLS enabled but certificate or key path not provided")
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        raise FileNotFoundError("TLS certificate or key file not found")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
    # Harden minimal defaults
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:@STRENGTH")
    return ctx


