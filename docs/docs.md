# AutoMinecraft

A Minecraft Java Edition project that lets you type high-level commands in chat and have an in-game agent do the work for you. It uses a Fabric mod for in-game I/O and Baritone/Wurst for movement/building, plus a small Python service for planning and control.

This file is the working plan: what to build, the outcomes to hit, and how to do it.

---

## What works now

- Type commands like `!get minecraft:stone_pickaxe 1` and watch the agent do it end-to-end (from resource gathering to hierarchical automatic component crafting), survival-safe.
- Multiplayer-ready: multiple agents (clients) connect to one Python backend with auth.
- Chat-bridge control for Baritone/Wurst; mod-native actions only for ensure-context and minimal UI interactions; settings can be broadcast/overridden centrally.
- Deterministic planner and shared storage catalog persist. Pause/resume not implemented yet.
- Planner bootstrap: ensure prerequisites (e.g., craft planks from logs before crafting crafting table, or ensure raw material (diamonds for `diamond_pickaxe`) can be mined with tools the player currently has (`iron_pickaxe` or better)).

---

## How it fits together (simple flow)

chat `!get ...` → mod sends JSON → backend parses → planner makes linear steps → backend streams actions → mod executes via chat bridge (Baritone/Wurst) or limited mod-native crafting → mod emits telemetry, chat events, and container inventory updates → backend updates progress → done.

---

## Architecture

### Scope
Small, deterministic system to accept chat commands, produce explicit plans, and execute via chat bridge or minimal mod-native actions. Stateless client; single-source `config.json`; JSON-only persistence.

### Contracts (wire protocol + actions)

Wire protocol (selected messages)
- handshake
  - { type, player_uuid, password, client_version, capabilities }
- settings_update / settings_broadcast
  - { type, settings: { telemetry_interval_ms, chat_bridge_enabled, chat_bridge_rate_limit_per_sec, command_prefix, echo_public_default, ack_on_command, feedback_prefix, feedback_prefix_bracket_color, feedback_prefix_inner_color, message_pump_max_per_tick, message_pump_queue_cap, inventory_diff_debounce_ms, chat_max_length, crafting_click_delay_ms, baritone? } }
- progress_update
  - { type, action_id, status, note? }

Action table (excerpt)
- acquire: world acquisition via Baritone chat bridge (e.g., `#mine iron_ore`, `#goto crafting_table`)
- craft: mod-native crafting (2x2 supported: planks, stick, crafting_table; limited 3x3 when crafting table UI is already open: wooden_pickaxe)
- chat_send: backend-to-client chat; client rate-limits; non-command text shown in HUD instead of public chat by default

### Boundaries & ownership

#### Fabric mod
Components
- Fabric mod: input (`!` chat), telemetry, chat bridge, minimal mod-native crafting, shared storage catalog; no client persistence.
- Baritone/Wurst: movement/building/mining/combat via chat commands; no tight API coupling.
- Python backend: WebSocket server, intent parsing, deterministic planner, dispatcher, per-agent state; no resume.

Interfaces
- Inbound: player types `!command` → mod sends `{type:"command"}` → backend converts to intent → planner emits plan → dispatcher sends actions.
- Execution: mod executes actions via chat bridge (`#`, `.`) and limited mod-native crafting. Ensure-context is handled by backend using Baritone settings + `#goto`; mod does not auto-open/close screens.
- Feedback: mod emits `progress_update`, `telemetry_update`, `inventory_snapshot`/`inventory_diff`, and forwards filtered `chat_event` lines.

### Identifiers & sequencing
- Correlate with ids and sequence numbers: `request_id`, `plan_id`, `action_id`, `seq`.
### Reliability
- `action_request` yields a `progress_update` from the client. No automatic retries/backoff; no resume on reconnect.

State & persistence
- Backend: last telemetry per agent and shared storage catalog (JSON files in `data/`). No active-plan persistence.
- Mod: stateless; runtime settings applied via backend; emits inventory snapshots/diffs, but does not persist locally.

Failure semantics
- No backend timer-based retries. A manual `!stop` cancels active dispatchers and sends `#stop` to Baritone; client clears pending crafts and keeps screens unchanged.

Multi-agent
- One WebSocket per `player_uuid`; dispatcher per agent. No claims/fair scheduler yet.

Security & observability
- Sanitize/escape outbound chat; never echo arbitrary backend input to public chat.
- Structured logs with `request_id`, `action_id`, `player_uuid`; lightweight metrics for Requests/Errors/Duration.
- Auth: shared `password` in `handshake`.
 - Rate limits: configurable max chat sends/sec and message size caps.

---

#### Fabric mod (modules)
 - Mod Core
  - Responsibilities: lifecycle, WebSocket client, handshake/auth, seq numbers.
  - Threads: main game thread for MC events; IO thread for WebSocket.
- Event Bus Adapters
  - ChatListener: `!` command capture; `chat_event` filter/forwarder.
  - TelemetryCollector: heartbeat assembly; on-demand `state_response`.
  - InventoryWatcher: container open/close/slot updates → `inventory_snapshot`/`inventory_diff`.
 - Action Executor
  - ChatBridgeExecutor: formats Baritone/Wurst commands; rate-limits sends.
  - NativeExecutor: crafting only (2x2 and limited 3x3); no general interact/smelt yet.
  
 - Storage Events (client)
  - Emit snapshots/diffs for container UIs; backend merges latest by `(dim,pos)`.

#### Backend (modules)
 - Gateway Server
  - WebSocket endpoints; per-agent session.
 - State Service
  - Last telemetry per agent; applies settings on handshake; JSON persistence only.
 - Planner
  - Deterministic expander using curated recipes; inventory-aware pruning; minimal tool gating.
 - Dispatcher
  - Plan to actions; no retries/backoff; `!stop` cancels and broadcasts `#stop`.
  - Chat bridge mapping for `acquire`; context placeholders handled via Baritone `#set` + `#goto` and optional `#eta`.
 - Settings Service
  - Sends `settings_update` on handshake; optional `baritone` map applied via chat `#set`.
 - Persistence
  - Storage: JSON files only; persists storage catalog and latest telemetry.


Persistence layout (current)
 - data/
  - state.json
  - storage_catalog.json

Timing and reliability
- No automatic resume.

Security
- Shared password in handshake; message size caps; rate limits; strict schema validation server-side.

---

## What to build (checklists + how)

### 1) Fabric mod (Java)

Outcome: The game sends and receives JSON, executes actions via Baritone/Wurst, and prints clear progress.

Build this:
- Chat intake
  - Listen for chat starting with `!`.
  - Consume (don’t broadcast) the message; send a JSON payload to the backend.
- Telemetry and state
  - Heartbeat: periodically send telemetry (pos, dim, yaw/pitch, health, hunger, saturation, air, xp_level, time, username, uuid, and non-empty inventory slots).
  - On-demand: handle `state_request` from the backend and reply with `state_response` using the same snapshot builder (supports selector slices).
  - Use Minecraft’s stats for counts (e.g., blocks mined) rather than bespoke dirt/grass trackers.
  - Shared storage catalog:
    - Listen for container open/close and slot changed events (chests, barrels, shulkers, furnaces, etc.).
    - On open/close or meaningful change, emit `inventory_snapshot` (location, type, slots, items with ids/count/nbt) and update local cache.
    - Deduplicate by container position + dimension; include hash/version to allow backend diffs.
- Networking
  - Keep a single connection to the backend. Backend pushes `settings_update` immediately on handshake.
  - Message types: `handshake`, `command`, `plan`, `action_request`, `progress_update`, `telemetry_update`, `state_request`, `state_response`, `inventory_snapshot`, `inventory_diff`, `chat_send`, `chat_event`, `settings_update`.
  - Rate/spacing: backend spaces action sends (`default_action_spacing_ms`), client rate-limits chat bridge sends.
- Action executor
  - Chat bridge actions: backend sends `#mine`, `#goto`, `#stop`, and `#set`.
  - Mod-native actions: `craft` only (2x2 recipes planks/stick/crafting_table; limited 3x3 for wooden_pickaxe when the crafting table screen is open).
  - Confirm each action with a success/fail and a short note.
  
- Persistence
  - No local config files; runtime settings updates adjust telemetry interval, echo policy, and chat rate limit; Baritone settings applied via `#set`.

Notes:
- Keep code small and clear. Prefer early returns. Only log what helps.
- If an action is requested that you can’t perform, reply with `progress_update` indicating `skipped` or `fail` and a short note.
- Sanitize outbound chat to prevent unintended command injection; the client clamps chat length per settings.

### 2) Python backend

Outcome: A small service that speaks JSON with the mod, turns requests into steps, streams actions, and tracks progress.

Build this:
- Server
  - WebSocket endpoint for bidirectional, concurrent messaging (one connection per agent); supports `ping`→`pong`.
- Command intake
  - Accept `command` messages with the original text and a fresh `request_id`.
  - Normalize text (`!get iron pickaxe 1` → a small intent JSON).
 - Telemetry
  - Store `telemetry_update` messages as the latest known agent state.
  - Send `state_request` when a fresh snapshot is needed; expect `state_response`.
 - Inventory catalog
  - Accept `inventory_snapshot`/`inventory_diff` from agents; index by container key `(dim,x,y,z)` and type. Client emits snapshots on container open and diffs on slot changes.
  - Maintain a merged view across agents; last-write-wins with version/hash; debounce rapid updates.
  - Provide queries to the planner/dispatcher: find items by id/nbt across player inventories and storage.
- Planner (deterministic first)
  - Given an intent like "craft 1 iron_pickaxe," expand into a concrete, ordered step list with pre/post checks.
  - Use the current inventory snapshot to prune leaves/outputs before emitting steps (no heuristic conversions).
  - Include resource requirements (sticks, iron ingots) and where to get them (mine, smelt, craft).
- Dispatcher
  - Stream steps one at a time to the mod with conservative spacing. No built-in retries; `!stop` cancels and broadcasts `#stop`.
 - Multi-agent
- One controller per `player_uuid`; concurrent connections; shared world model with simple claims and fair scheduling.
- Progress + resume
  - Keep a lightweight record (e.g., a JSON file) for request status, current step, and inventory snapshot. The server correlates `action_id` with `{request_id, step}` for logs and basic bookkeeping.

Notes:
- Keep everything in plain functions and simple modules. Avoid frameworks.
- Make weird input hard to break you: validate and default to a safe message.

### 3) Protocols (speak the same language)

Keep it simple and explicit. Examples:

Incoming chat → intent
```json
{
  "type": "command",
  "request_id": "uuid",
  "text": "!get iron pickaxe 1",
  "player_uuid": "player-1"
}
```

Backend intent (derived):
```json
{
  "type": "craft_item",
  "request_id": "uuid",
  "item": "minecraft:iron_pickaxe",
  "count": 1
}
```

Planner output (steps):
```json
{
  "type": "plan",
  "plan_id": "uuid",
  "request_id": "uuid",
  "steps": [
    { "op": "acquire", "item": "minecraft:iron_ingot", "count": 3 },
    { "op": "acquire", "item": "minecraft:stick", "count": 2 },
    { "op": "craft", "recipe": "minecraft:iron_pickaxe", "count": 1 }
  ]
}
```

Action to mod:
```json
{ "type": "action_request", "action_id": "uuid", "mode": "chat_bridge", "op": "acquire", "chat_text": "#mine iron_ore" }
```

Progress from mod:
```json
{ "type": "progress_update", "action_id": "uuid", "status": "ok", "note": "sent chat" }
```

Telemetry update (from mod):
```json
{
  "type": "telemetry_update",
  "player_uuid": "<uuid>",
  "ts": "2025-10-18T12:34:56Z",
  "state": {
    "pos": [0, 64, 0],
    "dim": "minecraft:overworld",
    "yaw": 0.0, "pitch": 0.0,
    "health": 20, "hunger": 20, "saturation": 5, "air": 300,
    "effects": [],
    "inventory": [],
    "equipment": {},
    "looking_at": null,
    "hotbar_slot": 0,
    "xp_level": 0,
    "time": 6000,
    "biome": "minecraft:plains",
    "uuid": "<uuid>",
    "username": "playerName"
  }
}
```

State request/response:
```json
{ "type": "state_request", "request_id": "uuid", "player_uuid": "player-1", "selector": ["inventory","equipment"] }
```
```json
{ "type": "state_response", "request_id": "uuid", "player_uuid": "player-1", "state": { "inventory": [], "equipment": {} } }
```

Chat bridge:
```json
{ "type": "action_request", "action_id": "uuid", "mode": "chat_bridge", "op": "chat", "chat_text": "#mine iron_ore" }
```
```json
{ "type": "chat_event", "player_uuid": "player-1", "text": "[Baritone] Mining iron_ore...", "ts": "2025-10-18T12:35:00Z" }
```


Action to mod (chat bridge):
```json
{ "type": "action_request", "action_id": "uuid", "mode": "chat_bridge", "op": "chat", "chat_text": "#goto 100 70 100" }
```
Action to mod (mod-native):
```json
{ "type": "action_request", "action_id": "uuid", "mode": "mod_native", "op": "craft", "recipe": "minecraft:oak_planks", "count": 1 }
```
Semantics:
- For `mode=chat_bridge`, the client sends the `chat_text` and immediately replies with `progress_update {status: ok|skipped}` based on local rate limit.
- For `mode=mod_native`:
  - `craft` supports 2x2 recipes (`minecraft:oak_planks`, `minecraft:stick`, `minecraft:crafting_table`) and limited 3x3 when the screen is already a crafting table (`minecraft:wooden_pickaxe`).
  - If a 3x3 context is required and not present, the client replies with `progress_update {status: skipped, note: "craft requires 3x3 context"}` or queues when `context: "crafting_table"` until the UI opens.
  - If unimplemented or inputs missing, the client replies with `progress_update {status: skipped|fail, note}`.

Shared storage: container inventory snapshot
```json
{
  "type": "inventory_snapshot",
  "player_uuid": "player-1",
  "container": {
    "dim": "minecraft:overworld",
    "pos": [123, 64, -45],
    "container_type": "minecraft:chest",
    "version": 7,
    "hash": "b1c2...",
    "slots": [
      { "slot": 0, "id": "minecraft:iron_ingot", "count": 12, "nbt": null },
      { "slot": 1, "id": "minecraft:coal", "count": 8, "nbt": null }
    ]
  }
}
```

Shared storage: delta update
```json
{
  "type": "inventory_diff",
  "player_uuid": "player-1",
  "container_key": { "dim": "minecraft:overworld", "pos": [123,64,-45] },
  "from_version": 7,
  "to_version": 8,
  "adds": [ { "slot": 2, "id": "minecraft:stick", "count": 4 } ],
  "removes": [ { "slot": 1, "id": "minecraft:coal", "count": 1 } ],
  "moves": []
}
```

### 4) Deterministic planner

Outcome: From a small set of goals you care about now, produce reliable step lists.

Start with:
- Craft graph for: sticks, planks, crafting_table, furnace, iron_ingot (smelt), torches, iron_pickaxe.
- Checks: do we already have enough? If yes, skip.
- Acquisition: if missing, choose "mine" + "smelt" + "craft" as needed.
- Output: a linear list of clear steps your mod understands.

Small, correct, and boring beats clever here.

Known gaps and next steps:
- Recipe data: curated in `settings/skill_graph.json` and `settings/mineable_items.json`; expand coverage over time.
- 2x2 vs 3x3 separation: client currently only acknowledges 2x2 `craft` ops; full 3x3 crafting and smelting will require mod-native UI logic after ensure via Baritone navigate (`#goto`).
- Acquire coalescing: consecutive duplicate acquires are coalesced to reduce chat noise; planner and dispatcher maintain inventory awareness to skip satisfied leaves.
- Context ensure: `crafting_table_nearby`/`furnace_nearby` use Baritone navigation (`#set rightClickContainerOnArrival true` + `#goto <container>`). No client placement fallback.
- Telemetry/state: client sends heartbeats; backend persists `data/state.json`.

### 5) Multi-agent

Outcome: Run two or more agents concurrently without tripping over each other, including handoffs.

- Give each agent a unique id and separate progress files.
- No claims yet; no `handoff`/`task_assign` APIs.

---

### Inventory-aware planning
- The planner expands a dependency tree and prunes leaves/outputs using the current inventory snapshot before emitting steps.
- The dispatcher avoids duplicate chat text, respects client rate limits, and can stop Baritone after reaching requested counts by polling telemetry inventory.

---

### Configuration

Use a single `settings/config.json` for the backend and runtime client settings (flattened). No environment variables or per-client mod config files are used.

Backend: `settings/config.json` (single source of truth, required)
- `host`, `port`, `log_level`, `password`
- `max_chat_sends_per_sec`, `default_action_spacing_ms`, `acquire_poll_interval_ms`
- flattened client settings applied at handshake via `settings_update` (e.g., `telemetry_interval_ms`, `chat_bridge_enabled`, `chat_bridge_rate_limit_per_sec`, `command_prefix`, `echo_public_default`, `ack_on_command`, `feedback_prefix`, `message_pump_max_per_tick`, `message_pump_queue_cap`, `inventory_diff_debounce_ms`, `chat_max_length`, `crafting_click_delay_ms`)
Policy: All runtime tunables come from `settings/config.json`. Missing required keys cause startup errors. Optional defaults: `feedback_prefix_bracket_color` and `feedback_prefix_inner_color`.

Mod: stateless; runtime behavior is controlled by the backend `settings_update` messages.

No secrets in the repo.

#### Server settings (required)
- `host` (string): Bind address for backend WebSocket server.
- `port` (int): Listening port.
- `log_level` (string): Logging level (INFO, DEBUG, WARN, ERROR).
- `password` (string): Shared password; clients present this in handshake.
- `max_chat_sends_per_sec` (int): Max chat sends per second per client (server guidance).
- `default_action_spacing_ms` (int): Inter-action spacing in milliseconds (added on top of client chat rate interval).

#### Acquisition tuning (required)
- `acquire_poll_interval_ms` (int): Poll interval for inventory checks during world acquisition.

#### Client settings (required)
Applied to clients at runtime via `settings_update`.

- `telemetry_interval_ms` (int): Telemetry heartbeat interval (ms).
- `chat_bridge_enabled` (bool): Enable chat-bridge actions.
- `chat_bridge_rate_limit_per_sec` (int): Client chat rate limit.
- `command_prefix` (string): Chat command prefix captured by the mod (e.g., `!`).
- `echo_public_default` (bool): Whether non-command chat_send is echoed to public chat by default.
- `ack_on_command` (bool): Show local HUD ack when command is captured.
- `feedback_prefix` (string): Prefix shown in HUD messages from the backend.
- `feedback_prefix_bracket_color` (string, optional): Color for brackets; default GRAY.
- `feedback_prefix_inner_color` (string, optional): Color for inner text; default DARK_GREEN.

#### Client runtime parameters (required)
- `message_pump_max_per_tick` (int): Max backend messages processed per client tick.
- `message_pump_queue_cap` (int): Max queued inbound messages before dropping new ones.
- `inventory_diff_debounce_ms` (int): Minimum interval between inventory diff emissions.
- `chat_max_length` (int): Max length for outgoing chat text before clamping.
- `crafting_click_delay_ms` (int): Delay between GUI slot clicks during 2x2 crafting (ms).

Notes:
- Settings are pushed on handshake; the client does not read local files or fall back to built-in defaults.
- Start with conservative values; tune based on world/server performance.

#### Recipe and planning data (required)
- `settings/skill_graph.json` (object):
  - `skills` (object): map of recipe id → { `op`: "craft"|"smelt", `consume`: {id:int}, `require`: {id:int}, `obtain`: {id:int} }.
- `settings/mineable_items.json` (array): list of item ids acquired from the world (mined/chopped/etc.).
- `settings/tool_tiers.json` (object): map of mineable id → ordered list of acceptable tool ids (lowest first).
- `settings/acquisition_map.json` (object): item id → Baritone target string (e.g., `iron_ore`).

---

### Integrations (Baritone and Wurst)

 - Baritone (chat `#` commands) – core we use
  - Core commands:
    - `#goto x y z` / `#goto block_type`
    - `#mine <block> [count]`
    - `#tunnel [w h d]`, `#explore`, `#follow ...`, `#stop`
  - Key settings: `autoTool=true`, `legitMine=true`, `allowBreak/allowPlace=true`, `rightClickContainerOnArrival=true`, `mineScanDroppedItems=true`, conservative path settings.
  - Action mapping:
    - acquire(item): blocks via `#mine`; contexts (`crafting_table_nearby`/`furnace_nearby`) via `#goto`.
    - navigate_to: `#goto ...`; tunnel/explore/follow as needed.
  - Don’t re-implement: pathfinding, mining, long-range exploration.
  - Keep mod-native: inventory ops (craft/smelt/transfer), precise placement, equipment management.
  - Operational notes: send only `#...` via chat bridge, rate-limit, apply settings on connect; use in-game `#help`.

 - Wurst7 (chat `.` commands) – optional complement
  - Useful commands: `.goto`, `.excavate`, `.follow`, `.drop`, `.throw`, `.viewnbt`; dangerous `.nuker` disabled by default.
  - Policy: prefer Baritone for navigation/mining; allow `.excavate` for straight dig tasks if it proves more reliable.
  - Mapping: tunnel/stripmine → prefer Baritone; follow → prefer Baritone; inventory/throw → mod-native first.
  - Operational notes: only when enabled by config and safe (SP vs server); continue to rate-limit.

 - Heartbeat & observability
  - Client telemetry heartbeat is controlled by config (`telemetry_interval_ms`) and applied via `settings_update` at handshake.

 - Optional tools (later): Litematica (schematics), JourneyMap (mapping), SeedcrackerX (seed research), Plan4MC (planner inspiration).

---

## Engineering practices and repo layout

Code organization (Java/Fabric)
- Use clear packages by responsibility: `modcore`, `net`, `telemetry`, `inventory`, `world`, `actions.chat`, `actions.native`, `util`.
- Separate event listeners from executors. Keep MC thread code minimal; push work to safe threads where applicable.
- Mod ID: lowercase 8–64 chars, letters/numbers/dash/underscore; consistent across `fabric.mod.json` and packages.

Error handling and logging
- Log4j (Fabric default) with structured fields (`player_uuid`, `request_id`, `action_id`).
- Guard MC calls with meaningful try/catch and short, actionable logs; no silent failures.
- Backend: structured logs (JSON preferred) with request/agent correlation.

Client–server trust boundaries
- Never trust the client: backend validates schemas, sizes, and rates; ignores unsafe requests.
- Mod sanitizes outbound chat; backend uses shared `password` in handshake.

Performance and profiling
- Keep telemetry cheap; avoid heavy NBT serialization every tick; honor debounce and size caps.
- Use Minecraft profiler/dev tools for client hotspots; Python: cProfile where needed.

Repository layout
- `fabric-mod/` (Gradle project)
- `backend/` (Python project)
- `docs/` (design)
- `data/` (runtime state; gitignored)
- `README.md`
- Root helper scripts (Windows): `run_build.ps1`, `run_backend.ps1`
