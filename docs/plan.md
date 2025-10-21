# AutoMinecraft

A Minecraft Java Edition project that lets you type high-level commands in chat and have an in-game agent do the work for you. It uses a Fabric mod for in-game I/O and Baritone/Wurst for movement/building, plus a small Python service for planning and control.

This file is the working plan: what to build, the outcomes to hit, and how to do it.

## Versions and compatibility
- Minecraft Java Edition: 1.21.8+
- Fabric Loader: latest compatible with 1.21.8+
- Fabric API: latest compatible with 1.21.8+
- Wurst: latest compatible with 1.21.8+
- Baritone: latest compatible with 1.21.8+
- Control strategy: send chat commands to Baritone (`#...`) and Wurst (`.`) to reduce tight coupling. Parse chat output and combine with telemetry for feedback.

---

## What you will have when this works

- Type commands like `!get minecraft:iron_pickaxe 1` and watch the agent do it end-to-end (from resource gathering to hierarchical automatic component crafting), survival-safe.
- Multiplayer-ready: multiple agents (clients) connect to one central Python backend (can be remote) with auth.
- Chat-bridge control for Baritone/Wurst; mod-native actions only for ensure-context and minimal UI interactions; settings can be broadcast/overridden centrally.
- Deterministic planner, shared storage catalog persist, pause and resume.
- Planner bootstrap: ensure prerequisites (e.g., craft planks from logs before crafting crafting table, or ensure raw material (diamonds for `diamond_pickaxe`) can be mined with tools the player currently has (`iron_pickaxe` or better)).

---

## How it fits together (simple flow)

chat `!get ...` → mod sends JSON → backend parses → planner makes step tree(graph) → backend streams actions from list → mod executes via chat bridge (Baritone/Wurst) or mod-native actions → mod emits telemetry and chat events → backend updates progress → done.

---

## Architecture (high-level)

Components
- Fabric mod: input (`!` chat), telemetry, chat bridge, minimal mod-native actions (explicit interact/craft/smelt), small persistence, shared storage catalog.
- Baritone/Wurst: movement/building/mining/combat via chat commands; no tight API coupling.
- Python backend: WebSocket server, intent parsing, deterministic planner, dispatcher, per-agent state, progress/resume.

Data flow
- Inbound: player types `!command` → mod sends `{type:"command"}` → backend converts to intent → planner emits plan → dispatcher sends actions.
- Execution: mod executes actions either by sending chat (`#`, `.`) to offload to Baritone/Wurst or via minimal mod-native operations (ensure/open/interact for crafting/smelting UI).
- Feedback: mod emits `progress_update`, `telemetry_update`, and forwards filtered `chat_event` lines.

Contracts (summary)
- Correlate with ids and sequence numbers: `request_id`, `plan_id`, `action_id`, `seq`.
- Messages: `handshake`, `command`, `plan`, `action_request`, `progress_update`, `telemetry_update`, `state_request`, `state_response`, `inventory_snapshot`, `inventory_diff`, `world_discovery`, `chat_send`, `chat_event`, `cancel`.
 - Messages: `handshake`, `command`, `plan`, `action_request`, `progress_update`, `telemetry_update`, `state_request`, `state_response`, `inventory_snapshot`, `inventory_diff`, `world_discovery`, `chat_send`, `chat_event`, `cancel`, `chat_broadcast` (planned).
- Acks/timeouts/retries: each `action_request` expects a `progress_update` with `status` in `{ok, fail, skipped, cancelled}` within a timeout; backend may retry with bounded attempts/backoff or cancel; resume on reconnect supported.

State & persistence
- Backend: last telemetry per agent, active requests, plan/step pointer, shared storage catalog (merged across agents), minimal world model (claims), small JSON/DB store.
- Mod: config, last active `request_id`, minimal resume data, and a local cache of discovered containers and their observed contents/locations.

Failure semantics
- Timeouts: backend marks action `fail_timeout` and proceeds by policy (retry/backoff/skip/cancel).
- Idempotence: actions are designed to be safe when retried (e.g., re-check state before act).
- Cancellation: backend can send `cancel` to stop current action chain; mod sends `ok` when halted.

Multi-agent
- One WebSocket per `player_id`; dispatcher per agent.
- Shared claims: rectangular areas and scarce resources have simple leases; collisions avoided by deny-and-retry.
- Fairness: round-robin step dispatch across active agents.

Security & observability
- Sanitize/escape outbound chat; never echo arbitrary backend input to public chat.
- Structured logs with `request_id`, `action_id`, `player_id`; lightweight metrics for Requests/Errors/Duration.
 - Auth & remote: optional shared `auth_token` in `handshake` for non-local connections; allow remote by config; optional TLS when backend is remote.
 - Rate limits: configurable max chat sends/sec and message size caps.

---

## Architecture (low-level)

Modules (Fabric mod)
- Mod Core
  - Responsibilities: lifecycle, config load, WebSocket client, handshake/auth, seq numbers, reconnect/resume.
  - Key types: Config, ConnectionState, MessageEnvelope { type, seq, request_id?, action_id? }.
  - Threads: main game thread for MC events; IO thread for WebSocket.
- Event Bus Adapters
  - ChatListener: `!` command capture; `chat_event` filter/forwarder.
  - TelemetryCollector: heartbeat assembly; on-demand `state_response`.
  - InventoryWatcher: container open/close/slot updates → `inventory_snapshot`/`inventory_diff`.
  - WorldDiscovery: portal/gateway/waypoint detection → `world_discovery`.
- Action Executor
  - ChatBridgeExecutor: formats Baritone/Wurst commands; rate-limits sends; parses minimal confirmations from chat echo.
  - NativeExecutor: place/break/interact/craft/smelt/container ops/hotbar/eat/sleep/collect_drops; pre/post checks; timeouts; retries. Navigation to containers is offloaded to Baritone; no client fallback for ensure-context.
  - DimensionTravel: portal registry lookup; navigate; cross; validate new dim; optional portal creation policy.
- Portal Registry (client cache)
  - Map by (dim,pos) with target_dim and last_seen; synced from/backend via `world_discovery` merge.
- Storage Cache (client)
  - Map containers by (dim,pos) with version/hash; deduped; debounced; prepared payload slicing if oversized.

Modules (Python backend)
- Gateway Server
  - WebSocket endpoints; auth token validation; TLS optional; per-agent session with seq tracking.
  - Health and optional Web UI (monitor agents, plans, actions; broadcast settings).
- State Service
  - Agent registry; last telemetry; connection health; settings to apply.
  - Shared storage catalog indexed by (dim,pos) with version/hash; Ender chest per player.
  - Portal/waypoint registry; dimension pairings; timestamps; pruning.
- Planner
  - Deterministic expander using vanilla recipes; pre/post checks; dimension-aware steps; resource policy.
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
  - Storage: JSON or SQLite (configurable); persists portal registry, storage catalog, agent settings, active requests, last steps.

Wire protocol (selected messages)
- handshake
  - { type, seq, player_id, auth_token?, client_version, capabilities }
- settings_update / settings_broadcast
  - { type, seq, player_id? (optional for all), settings: { telemetry_interval_ms, rate_limit_chat, baritone: {...}, wurst: {...} } }
- task_assign
  - { type, seq, request_id, player_id, intent | plan }
- handoff
  - { type, seq, from_player_id, to_player_id, chest: { dim,pos }, items: [{ id, count, nbt? }] }
- progress_update (extend)
  - { type, seq, action_id, status, note?, eta_ms? }

Action table (v0 excerpt)
- navigate_to: pre near-free path; post within tolerance; timeout dynamic by distance.
- mine: pre tool available and target known; post items collected or target absent; retries with new tool if policy.
- place: pre has blocks; post block at pos; rollback if occupied by wrong block (policy).
- craft_item: pre materials available or sub-goals queued; post item count increased; timeout per recipe.
- open_container/deposit/withdraw: pre in range and LOS; post inventory deltas match; emits `inventory_diff`.
- dimension_travel: pre portal known or policy allows creation; post `dim` changed and safe area check.
- chat_send: pre rate-limit; post chat echo observed or fallback to telemetry confirmation.

Persistence layout (suggested)
- db/ (or data/)
  - agents.json (or agents.sqlite)
  - storage_catalog.json (or sqlite tables: containers, slots)
  - portals.json (or sqlite table portals)
  - requests.json (active + history)
  - settings.json

Timing and reliability
- Defaults: heartbeat 500 ms; 3 retries; 500 ms backoff; per-action timeouts with sane caps.
- Resume: on reconnect, backend resends last pending action; agent replays last `progress_update`.

Security
- Auth token required for non-local connections; TLS optional but recommended for remote.
- Message size caps; rate limits; strict schema validation server-side.

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
    - dimension_travel (target_dim) → use portal registry to navigate to portal and cross; fallback to create portal if policy allows
  - Mod-native actions (no chat; direct interaction):
    - place (block id/pos), break (pos), interact (pos), use_item (item)
    - craft_item (recipe id, count), smelt (inputs, fuel)
    - open_container/deposit/withdraw, equip, eat, sleep, drop
    - wait (ms), set_hotbar (slot)
    - collect_drops (radius), throw (item,count), sneak/sprint toggles
    - build_from_schematic (worldedit .schem via Baritone builder; Litematica optional future integration)
  - Confirm each action with a success/fail and a short note. v0 implements 2x2 crafting for `minecraft:oak_planks`, `minecraft:stick`, and `minecraft:crafting_table` using client inventory interactions.
  - Dimension travel support
    - Maintain a portal registry: known Nether portals and End gateways by `(dim,pos)` with last-seen timestamp; allow backend sync.
    - When `dimension_travel` is requested: path to nearest suitable portal (Baritone `#goto`), trigger cross (approach/use), then confirm new `dim` via telemetry.
    - If no portal known and policy allows: gather resources, place obsidian and flint/steel to create portal, light, and cross; record both sides.
    - End travel: locate stronghold/end portal if allowed (long operation); optional defer until needed.
- Persistence
  - Save a small JSON for config (`backend_url`, telemetry interval), last active `request_id`, and minimal resume data. Runtime settings updates can adjust telemetry interval, echo policy, and chat rate limit; Baritone settings applied via `#set`.

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
  - Dimension-aware plans: if target or required resources are in another dimension, include `dimension_travel` steps via portal registry, and post-travel sanity checks (spawn safety, bed/respawn policy).
- Dispatcher
  - Stream steps one at a time to the mod, wait for confirmation, then send the next.
  - On fail, either retry or emit a clear message about what is missing; support `cancel`, `pause`, and `resume`.
 - Multi-agent
  - One controller per `player_id`; concurrent connections; shared world model with simple claims and fair scheduling.
- Progress + resume
  - Keep a lightweight record (e.g., a JSON file) for request status, current step, and inventory snapshot. v0 server correlates `action_id` with `{request_id, step}` for logs and basic bookkeeping.

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
  "player_id": "player-1"
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
  "player_id": "<uuid>",
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
{ "type": "state_request", "request_id": "uuid", "player_id": "player-1", "selector": ["inventory","equipment"] }
```
```json
{ "type": "state_response", "request_id": "uuid", "player_id": "player-1", "state": { "inventory": [], "equipment": {} } }
```

Chat bridge:
```json
{ "type": "chat_send", "request_id": "uuid", "player_id": "player-1", "text": "#mine iron_ore" }
```
```json
{ "type": "chat_event", "player_id": "player-1", "text": "[Baritone] Mining iron_ore...", "ts": "2025-10-18T12:35:00Z" }
```

World discovery (portals, waypoints):
```json
{
  "type": "world_discovery",
  "player_id": "player-1",
  "discoveries": [
    { "kind": "portal", "dim": "minecraft:overworld", "pos": [120, 63, -32], "target_dim": "minecraft:the_nether", "last_seen": "2025-10-18T12:40:00Z" },
    { "kind": "gateway", "dim": "minecraft:the_end", "pos": [0, 64, 80], "target_dim": "minecraft:the_end", "last_seen": "2025-10-18T12:41:00Z" }
  ]
}
```

Action to mod (chat bridge):
```json
{ "type": "action_request", "action_id": "uuid", "mode": "chat_bridge", "chat_text": "#goto 100 70 100" }
```
Action to mod (mod-native):
```json
{ "type": "action_request", "action_id": "uuid", "mode": "mod_native", "op": "craft", "recipe": "minecraft:iron_pickaxe", "count": 1 }
```
Semantics in v0:
- For `mode=chat_bridge`, the client sends the `text` to chat and immediately replies with `progress_update {status: ok|skipped}` based on local rate limit.
- For `mode=mod_native`:
  - `craft` supports 2x2-only recipes initially (`minecraft:planks`, `minecraft:stick`, `minecraft:crafting_table`).
  - If unimplemented or inputs missing, the client replies with `progress_update {status: skipped|fail, note}`.
  - Future: add ensure-context (`crafting_table_nearby`, `furnace_nearby`) and full 3x3 crafting/smelting with placement/interact.

Shared storage: container inventory snapshot
```json
{
  "type": "inventory_snapshot",
  "player_id": "player-1",
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
  "player_id": "player-1",
  "container_key": { "dim": "minecraft:overworld", "pos": [123,64,-45] },
  "from_version": 7,
  "to_version": 8,
  "adds": [ { "slot": 2, "id": "minecraft:stick", "count": 4 } ],
  "removes": [ { "slot": 1, "id": "minecraft:coal", "count": 1 } ],
  "moves": []
}
```

### 4) Deterministic planner (what it must cover first)

Outcome: From a small set of goals you care about now, produce reliable step lists.

Start with:
- Craft graph for: sticks, planks, crafting_table, furnace, iron_ingot (smelt), torches, iron_pickaxe.
- Checks: do we already have enough? If yes, skip.
- Acquisition: if missing, choose "mine" + "smelt" + "craft" as needed.
- Output: a linear list of clear steps your mod understands.

Small, correct, and boring beats clever here.

Known gaps and next steps (v0):
- Recipe ingestion: ingest vanilla JSON recipes/tags to avoid hardcoding in `backend/skill_graph.py`; generate skill nodes for craft/smelt and use tags (e.g., logs) for interchangeable inputs.
- 2x2 vs 3x3 separation: client currently only acknowledges 2x2 `craft` ops; full 3x3 crafting and smelting will require mod-native UI logic after ensure via Baritone navigate (`#goto`).
- Acquire coalescing: consecutive duplicate acquires are coalesced to reduce repeated `#mine` sends; future: inventory-aware planning to skip already-satisfied items.
- Context ensure: `crafting_table_nearby`/`furnace_nearby` use Baritone navigation (`#goto <container>`) with auto-open enabled; fallback to mod-native placement + explicit interact when none found or unreachable.
- Telemetry/state: client now sends heartbeats; backend pretty-prints `data/state.json`.

### 5) Multi-agent (v0)

Outcome: Run two or more agents concurrently without tripping over each other, including handoffs.

- Give each agent a unique id and separate progress files.
- Share a simple "claims" map (areas/resources). If claimed, deny and retry elsewhere.
- Support `handoff` via chest drop/pick and `task_assign` targeting specific agents.

---

## Configuration (keep it simple)

Use a `.env` file for the backend and a small JSON config file for the mod.

Backend (`.env`):
- `HOST` (e.g., 127.0.0.1)
- `PORT` (e.g., 8765)
- `LOG_LEVEL` (e.g., INFO)
 - `AUTH_TOKEN` (shared secret for non-local agents)
 - `ALLOW_REMOTE` (true|false)
 - `TLS_ENABLED` (true|false) and `TLS_CERT_FILE`, `TLS_KEY_FILE` if enabled
 - `MAX_CHAT_SENDS_PER_SEC` (e.g., 5)
 - `DEFAULT_RETRY_ATTEMPTS` (e.g., 3), `DEFAULT_RETRY_BACKOFF_MS` (e.g., 500)
 - `DEFAULT_ACTION_TIMEOUT_MS` (per-op override supported)
 - `DEFAULT_ACTION_SPACING_MS` (ms between action sends)
 - `IDLE_SHUTDOWN_SECONDS` (idle auto-shutdown; 0 disables)

Mod (`autominecraft.json` in the game’s config folder):
- `backend_url` (e.g., ws://127.0.0.1:8765)
- `telemetry_interval_ms` (e.g., 1000)
- `chat_bridge_enabled` (true|false)
- `chat_bridge_rate_limit_per_sec` (e.g., 2)
- `command_prefix` (e.g., `!`)
- `echo_public_default` (true|false)
- `auth_token` (if backend requires it)

No secrets in the repo.

---

## How to run (once code exists)

1) Start the backend
- Load `.env`.
- Run the WebSocket server: on Windows use `./run_backend.ps1`; on macOS/Linux `python -m backend` (after venv + requirements install).
- Watch logs for: "listening on HOST:PORT".

2) Start Minecraft with Fabric + Baritone + Wurst + this mod
- Confirm the mod connects to the backend.

Optional: Backend UI
- The backend may expose a simple console or web UI to monitor agents (telemetry, plans, actions) and broadcast settings.

3) Try small things first
- Watch telemetry updates arrive automatically (interval set in config; default 500 ms).
- Type `!echo hello` and see a reply.
- Trigger a simple navigation via the backend that sends `#goto x y z` and watch movement.

4) Try a real goal
- Type: `!get iron pickaxe 1`.
- Watch the planner emit steps and the mod execute them.

Developer testing helpers (Windows):
- `./run_tests.ps1` runs Java and Python tests (`backend/test`).

---

## External integrations (context)

- Baritone: automated pathfinding and automation (chat `#` commands). Repo: https://github.com/cabaletta/baritone
  - Use: navigation, mining, some building; settings via `#set`.
  - Limits: multi-dimension travel handled at higher layer; noisy chat output.
  - See usage (`usage.md`) and in-game `#help`.
  - Settings are applied on-demand via chat commands; the client does not force global defaults on connect.

Inventory-aware planning (v0)
- Planner expands a dependency tree and prunes leaves/outputs using the current inventory snapshot before emitting steps (no heuristic conversions like “planks to logs”).
- Dispatcher skips only on exact targets or clear variants (e.g., any `*_log` for logs), not by converting materials.

Heartbeat & observability
- Client telemetry heartbeat is controlled by config (`telemetry_interval_ms`), default 500 ms; the server does not override it at handshake.
  - Full capability map and AutoMC usage: see `docs/baritone_capabilities.md`.
  - Capability mapping: `#goto`, `#goal`+`#path`, `#mine <block> [count]`, `#tunnel`, `#explore`, `#wp`, `#follow`, `rightClickContainerOnArrival`.
  - Settings commonly tuned: `autoTool`, `legitMine`, `allowPlace`, `allowBreak`, `avoidance`, `mineScanDroppedItems`.

- Wurst7: Fabric client with automation modules (chat `.` commands). Repo: https://github.com/Wurst-Imperium/Wurst7
  - Use: optional helper modules like AutoEat/AutoArmor/tunneling.
  - Limits: treat as optional; gate risky features behind config.
  - See in-game `.help` for commands and modules.
  - Capability summary and AutoMC usage: see `docs/wurst_capabilities.md`.
  - Useful commands: `.goto`, `.excavate`, `.follow`, `.drop`, `.throw`, `.viewnbt`, `.nuker` (gated).

Baritone/Wurst usage
- Ensure-context: `#set rightClickContainerOnArrival true`; optional `#find <container>`; `#goto <container>`. No client fallback.
- Exploration/mining/tunneling: prefer Baritone (`#mine`, `#explore`, `#tunnel`).
- Settings are controlled via chat commands only (no settings_update reliance).

- Litematica (optional, later): schematic planning/visualization; potential for integration or printer support (if feasible via text/API).

- JourneyMap (optional, later): world mapping/waypoints to aid discovery/registry.

- SeedcrackerX (optional, later): recover world seed to enable seed-based structure/biome queries. Repo: https://github.com/19MisterX98/SeedcrackerX

- Plan4MC (research): RL+planning for long-horizon tasks; inspiration for planner design. Site: https://sites.google.com/view/plan4mc Repo: https://github.com/PKU-RL/Plan4MC
  - Concepts to adapt: hierarchical goals, state estimation, long-horizon decomposition.

---

## Engineering practices and repo layout

Code organization (Java/Fabric)
- Use clear packages by responsibility: `modcore`, `net`, `telemetry`, `inventory`, `world`, `actions.chat`, `actions.native`, `portal`, `util`.
- Separate event listeners from executors. Keep MC thread code minimal; push work to safe threads where applicable.
- Mod ID: lowercase 8–64 chars, letters/numbers/dash/underscore; consistent across `fabric.mod.json` and packages.

Error handling and logging
- Log4j (Fabric default) with structured fields (`player_id`, `request_id`, `action_id`).
- Guard MC calls with meaningful try/catch and short, actionable logs; no silent failures.
- Backend: structured logs (JSON preferred) with request/agent correlation.

Client–server trust boundaries
- Never trust the client: backend validates schemas, sizes, and rates; ignores unsafe requests.
- Mod sanitizes outbound chat; backend requires `auth_token` for remote; optional TLS.

Performance and profiling
- Keep telemetry cheap; avoid heavy NBT serialization every tick; honor debounce and size caps.
- Use Minecraft profiler/dev tools for client hotspots; Python: cProfile where needed.

Version control and workflow
- Git with conventional commits; branches: `main`, `dev`, feature branches.
- Tag releases with versioned mod jar/backend builds.

Repository layout (proposed)
- `fabric-mod/` (Gradle project)
- `backend/` (Python project)
- `docs/` (design and diagrams)
- `data/` (runtime state; gitignored)
- `README.md`
- Root helper scripts (Windows): `build_mod.ps1`, `run_backend.ps1`, `run_tests.ps1`

## Troubleshooting (plain fixes)

- Mod won’t connect → check `backend_url`, firewall, correct port, and that the backend is running.
- Baritone won’t move → verify the action payload and that Baritone commands work manually.
- Plans stall → print the current step and last progress note; if stuck, skip and continue.
- Restarts lose progress → confirm the progress file path and write permissions.
- Chat sends but nothing happens → verify `chat_bridge_enabled`, correct prefixes (`#` Baritone, `.` Wurst), and that both mods are loaded/compatible.

---

## Scope guardrails (to keep this shippable)

- Fewer features, rock-solid basics.
- Deterministic only; explicit chat commands and schemas (no LLM).
- Clear messages over clever abstractions.
- Safe to run twice; don’t depend on lucky timing.

---

## Short glossary (zero jargon)

- Plan: a list of steps like "go here, mine this, craft that."
- Step: one small action the mod can actually do.
- Progress: a short status after each step.
