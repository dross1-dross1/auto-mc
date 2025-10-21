from __future__ import annotations

"""Backend configuration and logging setup.

Purpose: Load settings from a single JSON file in the project root
(`config.json`). Environment variables are no longer used. Configure root
logging with a concise format.

"""

import logging
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    log_level: str
    auth_token: Optional[str]
    allow_remote: bool
    tls_enabled: bool
    tls_cert_file: Optional[str]
    tls_key_file: Optional[str]
    max_chat_sends_per_sec: int
    default_retry_attempts: int
    default_retry_backoff_ms: int
    default_action_timeout_ms: int
    default_action_spacing_ms: int
    idle_shutdown_seconds: int
    client_settings: dict
    # Backend behavioral tuning
    acquire_poll_interval_ms: int
    acquire_timeout_per_item_ms: int
    acquire_min_timeout_ms: int


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    try:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return default


def load_settings() -> Settings:
    """Load settings strictly from config.json at project root.

    No environment variables or fallbacks are used; the file must exist and contain the required keys.
    """
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        raise FileNotFoundError("config.json not found in project root")
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"failed to parse config.json: {e}")

    def gv(key: str, default):
        return data.get(key, default)

    required_keys = [
        "host","port","log_level","allow_remote","tls_enabled",
        "tls_cert_file","tls_key_file","max_chat_sends_per_sec",
        "default_retry_attempts","default_retry_backoff_ms",
        "default_action_timeout_ms","default_action_spacing_ms",
        "idle_shutdown_seconds","client_settings",
    ]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise KeyError(f"config.json missing required keys: {', '.join(missing)}")

    client_settings = data.get("client_settings")
    for ck in [
        "telemetry_interval_ms","chat_bridge_enabled","chat_bridge_rate_limit_per_sec",
        "command_prefix","echo_public_default","ack_on_command",
        "message_pump_max_per_tick","message_pump_queue_cap","inventory_diff_debounce_ms",
        "chat_max_length","crafting_click_delay_ms",
    ]:
        if ck not in client_settings:
            raise KeyError(f"config.json client_settings missing key: {ck}")

    settings = Settings(
        host=str(gv("host", None)),
        port=int(gv("port", None)),
        log_level=str(gv("log_level", None)).upper(),
        auth_token=gv("auth_token", None),
        allow_remote=_as_bool(gv("allow_remote", None), False),
        tls_enabled=_as_bool(gv("tls_enabled", None), False),
        tls_cert_file=gv("tls_cert_file", None),
        tls_key_file=gv("tls_key_file", None),
        max_chat_sends_per_sec=int(gv("max_chat_sends_per_sec", None)),
        default_retry_attempts=int(gv("default_retry_attempts", None)),
        default_retry_backoff_ms=int(gv("default_retry_backoff_ms", None)),
        default_action_timeout_ms=int(gv("default_action_timeout_ms", None)),
        default_action_spacing_ms=int(gv("default_action_spacing_ms", None)),
        idle_shutdown_seconds=int(gv("idle_shutdown_seconds", None)),
        client_settings=dict(client_settings),
        acquire_poll_interval_ms=int(data["acquire_poll_interval_ms"]),
        acquire_timeout_per_item_ms=int(data["acquire_timeout_per_item_ms"]),
        acquire_min_timeout_ms=int(data["acquire_min_timeout_ms"]),
    )
    return settings


def configure_logging(log_level: str) -> None:
    """Configure root logger with a concise, structured-ish format."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
