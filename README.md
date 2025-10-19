# AutoMinecraft

Type a plain-English command in Minecraft Java chat and watch an in-game agent do the work end-to-end. AutoMinecraft pairs a Fabric client mod (I/O and execution) with Baritone/Wurst for movement/building and a small Python backend for planning, dispatch, and progress tracking.

## Compatibility
- Minecraft Java Edition: 1.21.8+
- Fabric Loader + Fabric API: latest compatible with 1.21.8+
- Wurst7 and Baritone: latest compatible with 1.21.8+

## What you get
- Type commands like `!craft 1 iron pickaxe`; the agent handles navigation, mining, crafting, and confirmations.
- Multiplayer-ready: multiple clients connect to one backend with optional auth.
- Chat-bridge control for Baritone (`#...`) and Wurst (`.`); mod-native actions fill gaps.
- Deterministic planner first (no LLM required), with resume-on-reconnect and bounded retries.
- Dimension-aware tasks (portal registry, optional creation), shared storage catalog, and simple claims for multi-agent fairness.

## Architecture (at a glance)
- Fabric mod: captures `!` chat, streams telemetry, executes actions (chat bridge + mod-native), keeps small caches (portals, storage), and persists minimal local state.
- Python backend: WebSocket gateway, state service, deterministic planner, and dispatcher with timeouts/retries.
- Flow: `!command` → mod sends JSON → backend parses → planner emits steps → backend streams actions → mod executes → telemetry/progress update.

## Configuration
Use environment variables for the backend and a small JSON file for the mod. No secrets in the repo.

Backend `.env` (examples):
```env
HOST=127.0.0.1
PORT=8765
LOG_LEVEL=INFO
AUTH_TOKEN=change-me
ALLOW_REMOTE=false
TLS_ENABLED=false
MAX_CHAT_SENDS_PER_SEC=5
DEFAULT_RETRY_ATTEMPTS=3
DEFAULT_RETRY_BACKOFF_MS=500
DEFAULT_ACTION_TIMEOUT_MS=30000
```

Mod config `autominecraft.json` (in the game’s config folder):
```json
{
  "backend_url": "ws://127.0.0.1:8765",
  "player_id": "player-1",
  "telemetry_interval_ms": 1000,
  "chat_bridge_enabled": true,
  "inventory_snapshot_debounce_ms": 250,
  "inventory_snapshot_max_payload_kb": 64,
  "auth_token": null,
  "rate_limit_chat_sends_per_sec": 5,
  "settings_overrides": { "baritone": {}, "wurst": {} }
}
```

## Build the Fabric mod (JAR)
Windows (PowerShell):
```powershell
cd fabric-mod
.\gradlew.bat --no-daemon clean build
# Output: .\build\libs\autominecraft-0.1.0.jar
```
macOS/Linux:
```bash
cd fabric-mod
./gradlew --no-daemon clean build
# Output: ./build/libs/autominecraft-0.1.0.jar
```

## Getting started
1) Start the backend
- Create and fill a `.env` using the example in Configuration. Then install deps and run the server.

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend/requirements.txt
.\.venv\Scripts\python -m backend
```
macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend
```
- Watch logs for: "listening on HOST:PORT".

2) Start Minecraft with Fabric + Baritone + Wurst + this mod
- Copy the built JAR from `fabric-mod/build/libs/autominecraft-0.1.0.jar` into your Minecraft `mods` folder.
- Confirm the mod connects and telemetry starts.

3) Try small things
- Type `!echo hello` and see a reply. Trigger a simple navigation via `#goto` from the backend.

4) Try a real goal
- Type `!craft 1 iron pickaxe` and watch the planner emit steps and the mod execute them.

## Security and observability
- Sanitize/escape outbound chat; never echo arbitrary backend input to public chat.
- Optional shared `AUTH_TOKEN` for non-local agents; optional TLS when remote.
- Structured logs and lightweight metrics (Requests/Errors/Duration). Rate limits and message size caps.

## Repository layout (planned)
- `fabric-mod/` (Gradle project)
- `backend/` (Python project)
- `docs/` (design and diagrams)
- `data/` (runtime state; gitignored)

## Contributing
Small, reliable changes over big bang features. Use clear commits and keep configs out of code.

## License
See `LICENSE` for details.


