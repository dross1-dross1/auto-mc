# AutoMinecraft

Type chat commands in Minecraft Java and watch an in-game agent execute tasks end-to-end. AutoMinecraft pairs a Fabric client mod (I/O and execution) with Baritone/Wurst for movement/building and a small Python backend for planning, dispatch, and progress tracking.

## Compatibility
- Minecraft Java Edition: 1.21.8+
- Fabric Loader + Fabric API: latest compatible with 1.21.8+
- Wurst7 and Baritone: latest compatible with 1.21.8+

## What you get
- Type commands like `!get stone_pickaxe 1`; the agent handles navigation, mining, crafting, and confirmations.
  - Messaging: `!say <text|!command|#cmd|.cmd>`, `!saymulti <name1,name2,...> <...>`, `!sayall <...>`.
- Multiplayer-ready: multiple clients connect to one backend with optional auth.
- Chat-bridge control for Baritone (`#...`) and Wurst (`.`); mod-native actions fill gaps.
- Deterministic planner; retries/resume not yet implemented.
- Shared storage catalog across agents; claims are not implemented.

## Architecture (at a glance)
- Fabric mod: captures `!` chat, streams telemetry, executes actions (chat bridge + mod-native), and does not persist client-side state.
- Python backend: WebSocket gateway, state service, deterministic planner, and dispatcher with timeouts/retries.

## Configuration
Use a single JSON file `settings/config.json`. No environment variables or per-client mod files are used. This file is required and must include both server and client runtime keys (flattened). Recipe/planning data is curated in `settings/*.json`.

Policy: All runtime tunables are sourced exclusively from `settings/config.json`. Required keys must be present; the only optional defaults are `feedback_prefix_bracket_color` (GRAY) and `feedback_prefix_inner_color` (DARK_GREEN). If a required key is missing, the backend will error at startup so you can fix the configuration explicitly.

See the configuration reference for all parameters and meanings in `docs/docs.md` (Configuration section).


## Build the Fabric mod (JAR)
Windows (PowerShell):
```powershell
./run_build.ps1
# Output: .\fabric-mod\build\libs\autominecraft-0.1.0.jar (or .\fabric-mod\build\devlibs\autominecraft-0.1.0-dev.jar during dev)
```

## Tooling (Gradle wrapper)
- Use the Gradle Wrapper in `fabric-mod/` (`gradlew.bat`). The build commands above already use the wrapper; no separate Gradle install is required.
- If you ever need to refresh wrapper files, run from `fabric-mod/`: `.\gradlew.bat wrapper`

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
After this, build with the wrapper:
- `.\gradlew.bat --no-daemon clean build`

## Getting started (after cloning)

### Setup (TL;DR)
- Clone repo; open PowerShell in project root.
- Ensure Python 3.10+ and JDK 21 available.
- Create `settings/config.json` (see Configuration in `docs/docs.md`; include client runtime keys).
- Install Python deps: `pip install websockets` (system Python; no venvs).
- Start backend: `./run_backend.ps1`.
- Build mod: `./run_build.ps1`.

0) Prerequisites
- JDK 21 on PATH
- Python 3.10+ on PATH

If Java isn’t on PATH (Windows PowerShell, current shell only):
```powershell
$env:JAVA_HOME = 'C:\\Program Files\\Java\\jdk-21'
$env:Path = "$env:JAVA_HOME\\bin;" + $env:Path
java -version
```

1) Backend: setup and run
- Create `settings/config.json` using the Configuration section in `docs/docs.md`.
- Install Python dependencies to your main interpreter:
```powershell
pip install websockets
```
- Start the backend:
```powershell
./run_backend.ps1
```
- Watch logs for: "listening on HOST:PORT".

2) Build the mod (JAR)
- Preferred: `./run_build.ps1`.
- Or: `cd fabric-mod` then run the wrapper. If the wrapper JAR is missing, follow Tooling → Gradle wrapper recovery.

3) Install and run in Minecraft
- Copy the built JAR into your Minecraft `mods` folder alongside Fabric Loader/API, Baritone, Wurst. Preferred: `fabric-mod/build/libs/autominecraft-0.1.0.jar`. If not present, use the dev JAR: `fabric-mod/build/devlibs/autominecraft-0.1.0-dev.jar`.
- Start Minecraft and connect to a world/server.

Tips
- AutoMC in-game help: `!help`; Repo: https://github.com/dross1-dross1/auto-mc.
- Baritone in-game help: `#help`; Repo: https://github.com/cabaletta/baritone.
- Wurst in-game help: `.help`; Repo: https://github.com/Wurst-Imperium/Wurst7.
 

## Developer workflow

Keep changes small and verify in-game for interactions (crafting UI, placement, Baritone pathing). Build the mod and run the backend when needed.

 
