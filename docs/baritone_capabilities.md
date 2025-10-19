# Baritone Capabilities and AutoMC Usage

## Overview
Baritone provides chat-driven automation for navigation, mining, building, selection operations, and more. We favor invoking Baritone via chat bridge (`#...`) rather than re-implementing similar behaviors in our mod. This file consolidates the most relevant commands and settings and maps them to AutoMC use cases.

## Core Commands (with notes)
- `#goto x y z` / `#goto x z` / `#goto y`
  - Go to coordinates immediately. AutoMC: general navigation action, dimension-aware at planner level.
- `#goal ...` then `#path`
  - Set a goal then path. AutoMC: rarely needed; `#goto` preferred.
- `#goto block_type` (e.g., `#goto crafting_table`, `#goto ender_chest`)
  - Navigate to nearest matching block; combine with setting `rightClickContainerOnArrival` to auto-open. AutoMC: ensure-context first choice for crafting/smelting before placement.
- `#mine <block> [count]`
  - Mine target blocks; respects `autoTool`, `legitMine`, and other settings. AutoMC: acquisition for logs, coal, iron ore, etc.
- `#tunnel [w h d]`
  - Carve tunnels; deviates only for safety/obstacles. AutoMC: strip mining or access corridors; alternative to bespoke tunneling.
- `#explore [x z]`
  - Explore towards unseen chunks. AutoMC: scouting or world discovery.
- `#follow player <name>` / `#follow players` / `#follow entities` / `#follow entity <type>`
  - Follow targets. AutoMC: escort or rendezvous behaviors.
- `#wp ...`
  - Waypoints (save/goal). AutoMC: optional; planner may store POIs separately.
- `#build <schem> [x y z]`
  - Build schematics. AutoMC: future building tasks; not v0 focus.
- `#stop` / `#cancel` / `#forcecancel`
  - Halt current action. AutoMC: used as cancel primitive.

## Settings (selected) and rationale
- `autoTool=true`
  - Automatically selects the best tool. AutoMC: reduces micro-management when mining.
- `legitMine=true`
  - Only mine visible ores. AutoMC: avoids suspicious behavior on servers.
- `allowBreak=true`, `allowPlace=true`
  - Permit breaking/placing. AutoMC: enable as needed; placement may be mod-native for precision.
- `allowParkour=false`, `allowDiagonalAscend=false`, `assumeWalkOnWater=false`, `freeLook=false`
  - Conservative defaults to avoid risky paths and anti-cheat flags. AutoMC: set on connect.
- `primaryTimeoutMS=4000`
  - Ensure quicker replans on bad paths. AutoMC: reduces long stalls.
- `mineScanDroppedItems=true`
  - Path to dropped items of target type. AutoMC: improves collection completeness.
- `rightClickContainerOnArrival=true`
  - Auto-open target containers after `#goto <container>`. AutoMC: simplifies ensure/open.
- `avoidance` and related radii
  - Avoid mobs/spawners. AutoMC: enable for survival safety (configurable).
- `censorRanCommands`, `censorCoordinates`
  - Reduce leakage of sensitive info. AutoMC: optional in multi-user contexts.

## AutoMC Action Mapping
- acquire(item):
  - Blocks (logs/ores): `#mine <block> [count]`
  - Contexts (crafting_table_nearby/furnace_nearby): `#goto crafting_table|furnace` first; fallback to placement if not found.
- navigate_to(pos/block): `#goto ...`
- explore: `#explore`
- tunnel/stripmine: `#tunnel ...`
- follow: `#follow ...`
- stop/pause/resume: `#stop` (pause/resume via future policy)

## Don’t Re-Implement (use Baritone)
- Pathfinding across terrain, obstacle avoidance, staircase building, trenching.
- General mining of known block types and collection of drops.
- Long-range exploration and waypointing.

## Keep Mod-Native
- Inventory operations (crafting UI, smelting UI, container transfer), precise block placement alignment, equipment management, anti-cheat-friendly interaction timing/LOS checks.

## Operational Notes
- Only send `#...` commands via chat bridge to avoid public broadcast of plain text.
- Rate-limit chat sends; space actions from backend.
- Configure defaults on connect; allow backend overrides via settings updates.
