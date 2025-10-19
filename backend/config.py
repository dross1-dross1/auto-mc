from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


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


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    """Load settings from environment variables and optional .env file."""
    if load_dotenv is not None:
        # Load a local .env if present; ignored otherwise
        load_dotenv(override=False)

    settings = Settings(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8765")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        auth_token=os.getenv("AUTH_TOKEN"),
        allow_remote=_get_bool("ALLOW_REMOTE", False),
        tls_enabled=_get_bool("TLS_ENABLED", False),
        tls_cert_file=os.getenv("TLS_CERT_FILE"),
        tls_key_file=os.getenv("TLS_KEY_FILE"),
        max_chat_sends_per_sec=int(os.getenv("MAX_CHAT_SENDS_PER_SEC", "5")),
        default_retry_attempts=int(os.getenv("DEFAULT_RETRY_ATTEMPTS", "3")),
        default_retry_backoff_ms=int(os.getenv("DEFAULT_RETRY_BACKOFF_MS", "500")),
        default_action_timeout_ms=int(os.getenv("DEFAULT_ACTION_TIMEOUT_MS", "30000")),
        default_action_spacing_ms=int(os.getenv("DEFAULT_ACTION_SPACING_MS", "200")),
        idle_shutdown_seconds=int(os.getenv("IDLE_SHUTDOWN_SECONDS", "0")),
    )
    return settings


def configure_logging(log_level: str) -> None:
    """Configure root logger with a concise, structured-ish format."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
