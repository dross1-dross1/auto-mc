# AutoMinecraft Configuration Reference

This document is the authoritative reference for `settings/config.json`. The backend fails fast if required keys are missing. No defaults are hardcoded in code.

## Server settings (required)
- `host` (string): Bind address for backend WebSocket server.
- `port` (int): Listening port.
- `log_level` (string): Logging level (INFO, DEBUG, WARN, ERROR).
- `password` (string): Shared password; clients must present this in handshake via `!connect`.
- `max_chat_sends_per_sec` (int): Max chat sends per second per client (server guidance).
- `default_action_spacing_ms` (int): Inter-action spacing in milliseconds (added on top of client chat rate interval).

## Acquisition tuning (required)
- `acquire_poll_interval_ms` (int): Poll interval for inventory checks during world acquisition.

## Client settings (required)
Applied to clients at runtime via `settings_update`.

- `telemetry_interval_ms` (int): Telemetry heartbeat interval (ms).
- `chat_bridge_enabled` (bool): Enable chat-bridge actions.
- `chat_bridge_rate_limit_per_sec` (int): Client chat rate limit.
- `command_prefix` (string): Chat command prefix captured by the mod (e.g., `!`).
- `echo_public_default` (bool): Whether non-command chat_send is echoed to public chat by default.
- `ack_on_command` (bool): Show local HUD ack when command is captured.
- `feedback_prefix` (string): Prefix shown in HUD messages from the backend.

### Client runtime parameters (required)
- `message_pump_max_per_tick` (int): Max backend messages processed per client tick.
- `message_pump_queue_cap` (int): Max queued inbound messages before dropping new ones.
- `inventory_diff_debounce_ms` (int): Minimum interval between inventory diff emissions.
- `chat_max_length` (int): Max length for outgoing chat text before clamping.
- `crafting_click_delay_ms` (int): Delay between GUI slot clicks during 2x2 crafting (ms).

Notes:
- The backend pushes settings on handshake; the client does not read local files or fall back to built-in defaults.
- For stability, start with conservative values, then tune based on world/server performance.
