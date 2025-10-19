# Wurst Capabilities and AutoMC Usage

Wurst exposes a large set of `.commands` and togglable hacks. We will selectively leverage Wurst where it cleanly complements Baritone. Where features overlap, we prioritize Baritone.

## Useful Commands (selected)
- `.goto <x> <z>`
  - Navigate to coordinates. AutoMC: prefer Baritone `#goto`, keep as fallback.
- `.excavate`
  - Automated tunneling/excavation. AutoMC: alternative to Baritone `#tunnel` for straight dig tasks; gated by config.
- `.follow [player|entity]`
  - Follow targets. AutoMC: Baritone `#follow` preferred; Wurst fallback.
- `.drop`, `.throw`
  - Manage item drops/throws. AutoMC: may use for simple disposal; mod-native preferred for precise inventory control.
- `.viewnbt`, `.viewcomp`
  - Inspect NBT / components. AutoMC: developer tooling.
- `.nuker`
  - Mass block breaking. AutoMC: dangerous on servers; disabled by default.
- `.search`, `.path`
  - Utilities for finding and pathing. AutoMC: Baritone preferred.
- `.protect`, `.autoarmor`, `.autoeat`
  - Survival helpers. AutoMC: optional, gated by config; useful in survival scenarios.

## Prioritization and Policy
- Navigation/Mining: Baritone first (`#goto`, `#mine`, `#explore`, `#tunnel`).
- Bulk dig/strip operations: Baritone `#tunnel`; consider `.excavate` if it proves more reliable for specific tasks.
- Combat/survival helpers: allow per-config; not used by default.
- Dangerous ops (e.g., `.nuker`): disabled.

## AutoMC Mapping
- tunnel/stripmine: prefer `#tunnel`; optionally allow `.excavate`.
- follow: prefer `#follow`; optional `.follow`.
- inventory/throw: mod-native first; `.drop`/`.throw` optional for convenience tasks.

## Operational Notes
- Only send `.commands` when explicitly enabled by config and safe for the environment (SP vs. server).
- Continue to rate-limit chat sends; co-exist with Baritone commands.
