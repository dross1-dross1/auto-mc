# AutoMinecraft

A Minecraft Java Edition project that lets you type high-level commands in chat and have an in-game agent do the work for you. It uses a Fabric mod for in-game I/O and Baritone/Wurst for movement/building, plus a small Python service for planning and control.

This file is the working plan: what to build, the outcomes to hit, and how to do it.

---

## What you will have when this works

- Type commands like `!get minecraft:stone_pickaxe 1` and watch the agent do it end-to-end (from resource gathering to hierarchical automatic component crafting), survival-safe.
- Multiplayer-ready: multiple agents (clients) connect to one central Python backend (can be remote) with auth.
- Chat-bridge control for Baritone/Wurst; mod-native actions only for ensure-context and minimal UI interactions; settings can be broadcast/overridden centrally.
- Deterministic planner, shared storage catalog persist, pause and resume.
- Planner bootstrap: ensure prerequisites (e.g., craft planks from logs before crafting crafting table, or ensure raw material (diamonds for `diamond_pickaxe`) can be mined with tools the player currently has (`iron_pickaxe` or better)).

---

## How it fits together (simple flow)

chat `!get ...` → mod sends JSON → backend parses → planner makes step tree(graph) → backend streams actions from list → mod executes via chat bridge (Baritone/Wurst) or mod-native actions → mod emits telemetry and chat events → backend updates progress → done.

---

## Architecture

### Scope
Small, deterministic system to accept chat commands, produce explicit plans, and execute via chat bridge or minimal mod-native actions. Stateless client; single-source `config.json`; JSON-only persistence.

### Contracts (wire protocol + actions)

Wire protocol (selected messages)
- handshake
  - { type, seq, player_uuid, password, client_version, capabilities }
- settings_update / settings_broadcast
  - { type, seq, settings: { telemetry_interval_ms, rate_limit_chat, baritone: {...}, wurst: {...} } }
- task_assign
  - { type, seq, request_id, player_uuid, intent | plan }
- handoff
  - { type, seq, from_player_uuid, to_player_uuid, chest: { dim,pos }, items: [{ id, count, nbt? }] }
- progress_update (extend)
  - { type, seq, action_id, status, note?, eta_ms? }

Action table (excerpt)
- navigate_to: pre near-free path; post within tolerance; timeout dynamic by distance.
- mine: pre tool available and target known; post items collected or target absent; retries with new tool if policy.
- place: pre has blocks; post block at pos; rollback if occupied by wrong block (policy).
- craft_item: pre materials available or sub-goals queued; post item count increased; timeout per recipe.
- open_container/deposit/withdraw: pre in range and LOS; post inventory deltas match; emits `inventory_diff`.
- chat_send: pre rate-limit; post chat echo observed or fallback to telemetry confirmation.

### Boundaries & ownership

#### Fabric mod
Components
- Fabric mod: input (`!` chat), telemetry, chat bridge, minimal mod-native actions (explicit interact/craft/smelt), small persistence, shared storage catalog.
- Baritone/Wurst: movement/building/mining/combat via chat commands; no tight API coupling.
- Python backend: WebSocket server, intent parsing, deterministic planner, dispatcher, per-agent state, progress/resume.

Interfaces
- Inbound: player types `!command` → mod sends `{type:"command"}` → backend converts to intent → planner emits plan → dispatcher sends actions.
- Execution: mod executes actions either by sending chat (`#`, `.`) to offload to Baritone/Wurst or via minimal mod-native operations (ensure/open/interact for crafting/smelting UI).
- Feedback: mod emits `progress_update`, `telemetry_update`, and forwards filtered `chat_event` lines.

### Identifiers & sequencing
- Correlate with ids and sequence numbers: `request_id`, `plan_id`, `action_id`, `seq`.
### Reliability
- Acks/timeouts/retries: each `action_request` expects a `progress_update` with `status` in `{ok, fail, skipped, cancelled}` within a timeout; backend may retry with bounded attempts/backoff or cancel; resume on reconnect supported.

State & persistence
- Backend: last telemetry per agent, active requests, plan/step pointer, shared storage catalog (merged across agents), simple area claims (see below), small JSON store only.
- Mod: config, last active `request_id`, minimal resume data, and a local cache of discovered containers and their observed contents/locations.

Failure semantics
- Timeouts: backend marks action `fail_timeout` and proceeds by policy (retry/backoff/skip/cancel).
- Idempotence: actions are designed to be safe when retried (e.g., re-check state before act).
- Cancellation: backend can send `cancel` to stop current action chain; mod sends `ok` when halted.

Multi-agent
- One WebSocket per `player_uuid`; dispatcher per agent.
- Shared claims: rectangular areas and scarce resources have simple leases; collisions avoided by deny-and-retry.
- Fairness: round-robin step dispatch across active agents.

Security & observability
- Sanitize/escape outbound chat; never echo arbitrary backend input to public chat.
- Structured logs with `request_id`, `action_id`, `player_uuid`; lightweight metrics for Requests/Errors/Duration.
- Auth: shared `password` in `handshake`.
 - Rate limits: configurable max chat sends/sec and message size caps.

---

#### Fabric mod (modules)
 - Mod Core
  - Responsibilities: lifecycle, config load, WebSocket client, handshake/auth, seq numbers, reconnect/resume.
  - Key types: Config, ConnectionState, MessageEnvelope { type, seq, request_id?, action_id? }.
  - Threads: main game thread for MC events; IO thread for WebSocket.
- Event Bus Adapters
  - ChatListener: `!` command capture; `chat_event` filter/forwarder.
  - TelemetryCollector: heartbeat assembly; on-demand `state_response`.
  - InventoryWatcher: container open/close/slot updates → `inventory_snapshot`/`inventory_diff`.
- Action Executor
  - ChatBridgeExecutor: formats Baritone/Wurst commands; rate-limits sends; parses minimal confirmations from chat echo.
  - NativeExecutor: place/break/interact/craft/smelt/container ops/hotbar/eat/sleep/collect_drops; pre/post checks; timeouts; retries. Navigation to containers is offloaded to Baritone; no client fallback for ensure-context.
  
- Storage Cache (client)
  - Map containers by (dim,pos) with version/hash; deduped; debounced; prepared payload slicing if oversized.

#### Backend (modules)
 - Gateway Server
  - WebSocket endpoints; per-agent session with seq tracking.
  - Health and optional Web UI (monitor agents, plans, actions; broadcast settings).
- State Service
  - Agent registry; last telemetry; connection health; settings to apply.
  - Shared storage catalog indexed by (dim,pos) with version/hash; Ender chest per player.
  - Simple area claims (JSON): rectangular regions marked reserved by an agent to avoid collisions; first-come, expires after timeout.
- Planner
  - Deterministic expander using vanilla recipes; pre/post checks; resource policy.
  - Cost model hooks (nearest vs allowed zones), durability thresholds, auto-tool crafting.
 - Dispatcher
  - Plan to actions; per-action timeout; bounded retries with backoff; pause/cancel; resume on reconnect.
  - Multi-agent scheduler (round-robin with priorities later); claims; handoffs to chests; `task_assign`.
  - Chat bridge mapping for `acquire` → Baritone commands (e.g., `#mine coal_ore`, `#mine oak_log`).
  - Context placeholders like `crafting_table_nearby` and `furnace_nearby`:
    - Send chat `#set rightClickContainerOnArrival true`, optionally `#find <container>`, then `#goto <container>`.
    - No client fallback; if not found/unreachable, the attempt fails loudly.
- Settings Service
  - Broadcast `settings_update` to agents (e.g., Baritone/Wurst settings, telemetry interval, rate limits).
- Persistence
  - Storage: JSON files only; persists storage catalog, agent settings, active requests, last steps.

Wire protocol (selected messages)
- handshake
  - { type, seq, player_uuid, password, client_version, capabilities }
- settings_update / settings_broadcast
  - { type, seq, settings: { telemetry_interval_ms, rate_limit_chat, baritone: {...}, wurst: {...} } }
- task_assign
  - { type, seq, request_id, player_uuid, intent | plan }
- handoff
  - { type, seq, from_player_uuid, to_player_uuid, chest: { dim,pos }, items: [{ id, count, nbt? }] }
- progress_update (extend)
  - { type, seq, action_id, status, note?, eta_ms? }

Action table (excerpt)
- navigate_to: pre near-free path; post within tolerance; timeout dynamic by distance.
- mine: pre tool available and target known; post items collected or target absent; retries with new tool if policy.
- place: pre has blocks; post block at pos; rollback if occupied by wrong block (policy).
- craft_item: pre materials available or sub-goals queued; post item count increased; timeout per recipe.
 - open_container/deposit/withdraw: pre in range and LOS; post inventory deltas match; emits `inventory_diff`.
 - chat_send: pre rate-limit; post chat echo observed or fallback to telemetry confirmation.

Persistence layout (suggested)
 - data/
  - agents.json
  - storage_catalog.json
  - requests.json (active + history)
  - settings.json

Timing and reliability
- Defaults: heartbeat 500 ms; 3 retries; 500 ms backoff; per-action timeouts with sane caps.
- Resume: on reconnect, backend resends last pending action; agent replays last `progress_update`.

Security
- Shared password in handshake; message size caps; rate limits; strict schema validation server-side.

---

## What to build (checklists + how)

### 1) Fabric mod (Java)

Outcome: The game sends and receives JSON, executes actions via Baritone/Wurst, persists small bits of state, and prints clear progress.

Build this:
- Chat intake
  - Listen for chat starting with `!`.
  - Consume (don’t broadcast) the message; send a JSON payload to the backend.
- Telemetry and state
  - Heartbeat: periodically send telemetry (health, hunger, air, position/dimension, yaw/pitch, biome, time, status effects, inventory, equipment, tool durability, looking_at, selected_hotbar, xp).
  - On-demand: handle `state_request` from the backend and reply with `state_response` using the same snapshot builder as telemetry (supports selector slices).
  - Use Minecraft’s stats for counts (e.g., blocks mined) rather than bespoke dirt/grass trackers.
  - Shared storage catalog:
    - Listen for container open/close and slot changed events (chests, barrels, shulkers, furnaces, etc.).
    - On open/close or meaningful change, emit `inventory_snapshot` (location, type, slots, items with ids/count/nbt) and update local cache.
    - Deduplicate by container position + dimension; include hash/version to allow backend diffs.
- Networking
  - Keep a single connection to the backend (WebSocket is easiest). Reconnect if it drops.
  - Message types: `command`, `action_request`, `progress_update`, `telemetry_update`, `state_request`, `state_response`, `inventory_snapshot`, `inventory_diff`, `chat_send`, `chat_event`, `cancel`, `settings_update` (applied client-side at runtime).
  - Rate/spacing: backend spaces action sends (`DEFAULT_ACTION_SPACING_MS`), client rate-limits chat bridge sends.
- Action executor
  - Chat bridge actions (send to chat):
    - navigate_to (pos) → `#goto x y z`
    - mine (block type/pos) → `#mine <block>` or `#mine x y z`
    - follow_entity (type/name) → `#follow entity <type>`
    - stop/pause/resume → `#stop`, `#pause`, `#resume`
    - baritone_setting (key,value) → `#set key value`
    - Prefer Baritone/Wurst where possible to avoid re-implementing:
      - navigate_to → `#goto x y z` or `#goto block_type` (e.g., crafting_table, furnace)
      - mine → `#mine <block>` or `#mine <block> <count>`; enable `autoTool` and `legitMine` as needed
      - explore → `#explore`
      - tunneling → `#tunnel` (or Wurst `.excavate` when acceptable)
      - follow → `#follow player <name>` / `#follow entity <type>`
    - tunnel/stripmine → `.tunnel ...` (Wurst) or `#tunnel ...` (if supported)
    - combat toggles (if allowed) → `.killaura on|off`, `.autoarmor on|off`, `.autoeat on|off`
    - explore (radius) → `#explore <radius>` (if supported)
  - Mod-native actions (no chat; direct interaction):
    - place (block id/pos), break (pos), interact (pos), use_item (item)
    - craft_item (recipe id, count), smelt (inputs, fuel)
    - open_container/deposit/withdraw, equip, eat, sleep, drop
    - wait (ms), set_hotbar (slot)
    - collect_drops (radius), throw (item,count), sneak/sprint toggles
    - build_from_schematic (worldedit .schem via Baritone builder; Litematica optional future integration)
  - Confirm each action with a success/fail and a short note. Initial implementation supports 2x2 crafting for `minecraft:oak_planks`, `minecraft:stick`, and `minecraft:crafting_table` using client inventory interactions.
  
- Persistence
  - No local config files; runtime settings updates adjust telemetry interval, echo policy, and chat rate limit; Baritone settings applied via `#set`.

Notes:
- Keep code small and clear. Prefer early returns. Only log what helps.
- If an action is requested that you can’t perform, say so in the progress message and skip it.
 - Sanitize outbound chat to prevent unintended command injection.

### 2) Python backend

Outcome: A small service that speaks JSON with the mod, turns requests into steps, streams actions, and tracks progress.

Build this:
- Server
  - WebSocket endpoint for bidirectional, concurrent messaging (one connection per agent).
  - Health check (simple HTTP or a ping message).
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
  - Stream steps one at a time to the mod, wait for confirmation, then send the next.
  - On fail, either retry or emit a clear message about what is missing; support `cancel`, `pause`, and `resume`.
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
{ "type": "action_request", "action_id": "uuid", "op": "move_to", "pos": [x, y, z], "tolerance": 1.0 }
```

Progress from mod:
```json
{ "type": "progress_update", "action_id": "uuid", "status": "ok", "note": "arrived" }
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
{ "type": "action_request", "action_id": "uuid", "mode": "chat_bridge", "chat_text": "#goto 100 70 100" }
```
Action to mod (mod-native):
```json
{ "type": "action_request", "action_id": "uuid", "mode": "mod_native", "op": "craft", "recipe": "minecraft:iron_pickaxe", "count": 1 }
```
Semantics:
- For `mode=chat_bridge`, the client sends the `chat_text` and immediately replies with `progress_update {status: ok|skipped}` based on local rate limit.
- For `mode=mod_native`:
  - `craft` supports 2x2-only recipes initially (`minecraft:planks`, `minecraft:stick`, `minecraft:crafting_table`).
  - If a 3x3 context is required and not present (no crafting table UI open), the client replies with `progress_update {status: skipped, note: "awaiting crafting table context"}`. The backend ensures context via Baritone (`#set rightClickContainerOnArrival true` then `#goto crafting_table` and optional `#eta`).
  - If unimplemented or inputs missing, the client replies with `progress_update {status: skipped|fail, note}`.
  - Future: add ensure-context (`crafting_table_nearby`, `furnace_nearby`) and full 3x3 crafting/smelting with placement/interact.

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
- Acquire coalescing: consecutive duplicate acquires are coalesced to reduce repeated `#mine` sends; future: inventory-aware planning to skip already-satisfied items.
- Context ensure: `crafting_table_nearby`/`furnace_nearby` use Baritone navigation (`#goto <container>`) with auto-open enabled; fallback to mod-native placement + explicit interact when none found or unreachable.
- Telemetry/state: client now sends heartbeats; backend pretty-prints `data/state.json`.

### 5) Multi-agent

Outcome: Run two or more agents concurrently without tripping over each other, including handoffs.

- Give each agent a unique id and separate progress files.
- Share a simple "claims" map (areas/resources). If claimed, deny and retry elsewhere.
- Support `handoff` via chest drop/pick and `task_assign` targeting specific agents.

---

### Inventory-aware planning
- The planner expands a dependency tree and prunes leaves/outputs using the current inventory snapshot before emitting steps (no heuristic conversions like “planks to logs”).
- The dispatcher skips only on exact targets or clear variants (e.g., any `*_log` for logs), not by converting materials.

---

### Configuration

Use a single `settings/config.json` for the backend and runtime client settings (flattened). No environment variables or per-client mod config files are used.

Backend: `settings/config.json` (single source of truth, required)
- `host`, `port`, `log_level`, `password`
- `max_chat_sends_per_sec`, `default_action_spacing_ms`, `acquire_poll_interval_ms`
- flattened client settings applied at handshake via `settings_update` (e.g., `telemetry_interval_ms`, `chat_bridge_enabled`, `chat_bridge_rate_limit_per_sec`, `command_prefix`, `echo_public_default`, `ack_on_command`, `feedback_prefix`, `message_pump_max_per_tick`, `message_pump_queue_cap`, `inventory_diff_debounce_ms`, `chat_max_length`, `crafting_click_delay_ms`)
Policy: No hardcoded defaults or fallbacks in code. Missing required keys cause startup errors.

Mod: stateless; runtime behavior is controlled by the backend `settings_update` messages.

No secrets in the repo.

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
  - Client telemetry heartbeat is controlled by config (`telemetry_interval_ms`), default 500 ms; the server does not override it at handshake.

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
