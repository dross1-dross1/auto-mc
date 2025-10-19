from __future__ import annotations

"""Connection admission policy helpers.

Purpose: Decide whether to accept a connection based on remote/local address,
ALLOW_REMOTE, and AUTH_TOKEN in the handshake.

Contract:
- decide_accept_connection(remote_addr, settings, handshake) -> (accepted: bool, reason: str)
  Reasons: "ok", "remote_disabled", "auth_failed", "bad_handshake"
"""

from typing import Any, Dict, Tuple


def _is_local_address(addr: str) -> bool:
    return addr.startswith("127.") or addr == "::1" or addr == "localhost"


def decide_accept_connection(
    remote: Tuple[str, int] | None,
    settings: Any,
    handshake: Dict[str, Any],
) -> tuple[bool, str]:
    if not isinstance(handshake, dict) or handshake.get("type") != "handshake":
        return False, "bad_handshake"

    host = remote[0] if remote else "127.0.0.1"
    is_local = _is_local_address(host)
    # Deny non-local when ALLOW_REMOTE is False
    if not is_local and not bool(getattr(settings, "allow_remote", False)):
        return False, "remote_disabled"

    # If remote and AUTH_TOKEN configured, require match
    token_cfg = getattr(settings, "auth_token", None)
    if not is_local and token_cfg:
        token = handshake.get("auth_token")
        if token != token_cfg:
            return False, "auth_failed"

    return True, "ok"


