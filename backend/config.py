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
    password: str
    max_chat_sends_per_sec: int
    default_action_spacing_ms: int
    # Client runtime settings (flattened)
    telemetry_interval_ms: int
    chat_bridge_enabled: bool
    chat_bridge_rate_limit_per_sec: int
    command_prefix: str
    echo_public_default: bool
    ack_on_command: bool
    feedback_prefix: str
    message_pump_max_per_tick: int
    message_pump_queue_cap: int
    inventory_diff_debounce_ms: int
    chat_max_length: int
    crafting_click_delay_ms: int
    # Backend behavioral tuning
    acquire_poll_interval_ms: int
    # Timeouts removed


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
    cfg_path = Path("settings/config.json")
    if not cfg_path.exists():
        raise FileNotFoundError("settings/config.json not found in project root")
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"failed to parse settings/config.json: {e}")

    def gv(key: str, default):
        return data.get(key, default)

    required_keys = [
        "host","port","log_level","password",
        "max_chat_sends_per_sec",
        "default_action_spacing_ms",
        # flattened client settings
        "telemetry_interval_ms","chat_bridge_enabled","chat_bridge_rate_limit_per_sec",
        "command_prefix","echo_public_default","ack_on_command","feedback_prefix",
        "message_pump_max_per_tick","message_pump_queue_cap","inventory_diff_debounce_ms",
        "chat_max_length","crafting_click_delay_ms",
        # backend tuning
        "acquire_poll_interval_ms",
    ]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise KeyError(f"settings/config.json missing required keys: {', '.join(missing)}")

    settings = Settings(
        host=str(gv("host", None)),
        port=int(gv("port", None)),
        log_level=str(gv("log_level", None)).upper(),
        password=str(gv("password", None)),
        max_chat_sends_per_sec=int(gv("max_chat_sends_per_sec", None)),
        default_action_spacing_ms=int(gv("default_action_spacing_ms", None)),
        telemetry_interval_ms=int(gv("telemetry_interval_ms", None)),
        chat_bridge_enabled=_as_bool(gv("chat_bridge_enabled", None), False),
        chat_bridge_rate_limit_per_sec=int(gv("chat_bridge_rate_limit_per_sec", None)),
        command_prefix=str(gv("command_prefix", None)),
        echo_public_default=_as_bool(gv("echo_public_default", None), False),
        ack_on_command=_as_bool(gv("ack_on_command", None), False),
        feedback_prefix=str(gv("feedback_prefix", None)),
        message_pump_max_per_tick=int(gv("message_pump_max_per_tick", None)),
        message_pump_queue_cap=int(gv("message_pump_queue_cap", None)),
        inventory_diff_debounce_ms=int(gv("inventory_diff_debounce_ms", None)),
        chat_max_length=int(gv("chat_max_length", None)),
        crafting_click_delay_ms=int(gv("crafting_click_delay_ms", None)),
        acquire_poll_interval_ms=int(data["acquire_poll_interval_ms"]),
    )
    return settings


def configure_logging(log_level: str) -> None:
    """Configure root logger with a concise, structured-ish format."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
