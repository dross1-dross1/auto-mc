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
DEFAULT_ACTION_SPACING_MS=200
# Optional idle auto-shutdown (0 disables)
IDLE_SHUTDOWN_SECONDS=0
```

Mod config `autominecraft.json` (in the game’s config folder):
```json
{
  "backendUrl": "ws://127.0.0.1:8765",
  "playerId": "player-1",
  "telemetryIntervalMs": 1000,
  "chatBridgeEnabled": true,
  "chatBridgeRateLimitPerSec": 2
}
```

## Build the Fabric mod (JAR)
Windows (PowerShell):
```powershell
./build_mod.ps1
# Output: .\fabric-mod\build\libs\autominecraft-0.1.0.jar
```
macOS/Linux:
```bash
cd fabric-mod
./gradlew --no-daemon clean build
# Output: ./build/libs/autominecraft-0.1.0.jar
```

## Tooling (Gradle wrapper)
- The `tools/` directory is gitignored and should not be committed.
- Use the Gradle Wrapper in `fabric-mod/` (`gradlew.bat` on Windows, `./gradlew` on macOS/Linux). The build commands above already use the wrapper; no separate Gradle install is required.
- If you ever need to refresh wrapper files, run from `fabric-mod/`:
  - Windows (PowerShell): `.\gradlew.bat wrapper`
  - macOS/Linux: `./gradlew wrapper`

### Gradle wrapper recovery (if gradle-wrapper.jar is missing)
If you see `Unable to access jarfile .../gradle-wrapper.jar`, regenerate the wrapper using a one-time local Gradle install (no admin required), then use the wrapper normally.

Windows (PowerShell):
```powershell
$base = "$env:USERPROFILE\tools\gradle"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$zip  = "$base\gradle-8.14-bin.zip"
$url  = "https://services.gradle.org/distributions/gradle-8.14-bin.zip"
Invoke-WebRequest -Uri $url -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $base -Force
cd fabric-mod
& "$env:USERPROFILE\tools\gradle\gradle-8.14\bin\gradle.bat" wrapper
```
macOS/Linux:
```bash
mkdir -p "$HOME/tools/gradle"
cd "$HOME/tools/gradle"
curl -LO https://services.gradle.org/distributions/gradle-8.14-bin.zip
unzip -o gradle-8.14-bin.zip
cd -
cd fabric-mod
"$HOME/tools/gradle/gradle-8.14/bin/gradle" wrapper
```
After this, build with the wrapper:
- Windows: `.\gradlew.bat --no-daemon clean build`
- macOS/Linux: `./gradlew --no-daemon clean build`

## Getting started (after cloning)

0) Prerequisites
- JDK 21 on PATH
- Python 3.10+ on PATH

1) Backend: setup and run
- Create `.env` using the example in Configuration (or rely on defaults).

Windows (PowerShell):
```powershell
python -m venv .venv
./.venv/Scripts/python -m pip install -r backend/requirements.txt
./run_backend.ps1
```
macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend
```
- Watch logs for: "listening on HOST:PORT".

2) Smoke test backend (optional)
```powershell
.\.venv\Scripts\python tests\integration_backend.py
```
Expected: `PASSED 7/7`.

3) Build the mod (JAR)
- Preferred: `./build_mod.ps1`.
- Or: `cd fabric-mod` then run the wrapper (`gradlew`/`./gradlew`). If the wrapper JAR is missing, follow Tooling → Gradle wrapper recovery.

4) Install and run in Minecraft
- Copy the built JAR from `fabric-mod/build/libs/autominecraft-0.1.0.jar` into your Minecraft `mods` folder alongside Fabric Loader/API, Baritone, Wurst for `1.21.8`.
- First run creates `config/autominecraft.json`. Ensure `backendUrl` points to your backend.
- Try `!echo hello` and `!craft 1 iron pickaxe`.

Tips
- Baritone in-game help: `#help`; Repo: https://github.com/cabaletta/baritone (usage.md).
- Wurst in-game help: `.help`; Repo: https://github.com/Wurst-Imperium/Wurst7.
- Planner inspiration: Plan4MC https://github.com/PKU-RL/Plan4MC.

## Testing workflow

When to use tests vs. manual Minecraft:
- Use automated tests when changing logic that does not require a live world: parsing (`backend/intents.py`), planning (`backend/planner.py`), dispatch formatting (`backend/dispatcher.py`), config/state handling, and message routing in the mod (`MessageRouter`).
- Use manual testing when behavior depends on the live client or world state: UI interactions, block placement, hotbar selection, Baritone pathing outcomes, inventory UIs, or timing-sensitive actions.

Unit tests (fast, local):
- Python backend (run from repo root):
  - Preferred: `./run_tests.ps1` (runs Java then Python tests)
  - Or: `python -m unittest discover -s tests -p test_*.py -q`
  - Covers: intents parsing, planner expansion/gating/order, dispatcher mappings and skip-by-inventory, state persistence/selection, env config parsing.
- Java (Fabric mod logic):
  - Windows (PowerShell): `./run_tests.ps1`
  - macOS/Linux: `cd fabric-mod; ./gradlew --no-daemon test`
  - Covers: `MessageRouter` chat_send filtering and action_request routing/progress.

Integration tests (backend only, optional):
- `python tests/integration_backend.py` starts a client WS and exercises handshake, telemetry persistence, command → plan, and basic action_request flow.

Continuous integration (recommended):
- Configure CI to run both: backend unit tests and `fabric-mod` Gradle tests on every PR. Fail the build on test failures.

Guidelines:
- Keep tests deterministic and environment-free; mock external effects where needed.
- Prefer testing message shapes, ordering, and invariants over implementation details.

## Developer workflow

Daily loop:
1) Write or modify backend/mod code for a small change.
2) Add/adjust unit tests that capture expected behavior.
3) Run fast tests locally:
   - Backend: `python -m unittest discover -s tests -p test_*.py -q`
   - Mod: `cd fabric-mod; (./gradlew|.\\gradlew.bat) --no-daemon test`
4) If the change affects live interactions (crafting UI, placement, Baritone pathing), build the mod and verify in-game.
5) Commit with clear message; open PR; let CI run both suites.

When to prefer automated tests:
- Text/JSON in, text/JSON out logic (parsers, planners, routers, dispatchers).
- Pure calculations, ordering, gating rules, and coalescing/deduping logic.

When manual testing is required:
- Minecraft-specific APIs (UI open/interactions, block placement/use, world scans) and timing on the MC thread.
- Baritone/Wurst behavior differences across worlds/servers.

Commands recap:
- All tests (Windows): `./run_tests.ps1`
- Backend unit tests: `python -m unittest discover -s tests -p test_*.py -q`
- Java tests: `cd fabric-mod; (./gradlew|.\\gradlew.bat) --no-daemon test`
- Backend integration check: `python tests/integration_backend.py`

## Security and observability
- Sanitize/escape outbound chat; never echo arbitrary backend input to public chat.
- Optional shared `AUTH_TOKEN` for non-local agents; optional TLS when remote.
- Structured logs and lightweight metrics (Requests/Errors/Duration). Rate limits and message size caps.

## Repository layout (planned)
- `fabric-mod/` (Gradle project)
- `backend/` (Python project)
- `docs/` (design and diagrams)
- `data/` (runtime state; gitignored)
 - `tools/` (local tooling; gitignored)

## Contributing
Small, reliable changes over big bang features. Use clear commits and keep configs out of code.

## License
See `LICENSE` for details.


