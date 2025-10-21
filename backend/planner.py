from __future__ import annotations

"""Deterministic planner: expand craft/smelt goals into linear steps.

Purpose: Given an item id and count, expand via a tiny skill graph into a list
of steps the mod understands (acquire/craft/smelt), including minimal tool
gating for mining.

"""

from typing import Dict, List, Optional

from .skill_graph import SKILLS, MINEABLE_ITEMS, MINING_TOOL_REQUIREMENTS
from .state_service import StateService  # type: ignore


def _expand_with_inventory(target: str, required: int, inv_counts: Dict[str, int], steps: List[Dict[str, object]]) -> None:
    """Inventory-aware expansion: prune leaves/outputs using current inventory, emit only missing deltas."""
    if required <= 0:
        return
    skill = SKILLS.get(target)
    if skill is None:
        have = int(inv_counts.get(target, 0))
        if have >= required:
            inv_counts[target] = have - required
            return
        if have > 0:
            inv_counts[target] = 0
            required -= have
        steps.append({"op": "acquire", "item": target, "count": required})
        return

    # Satisfy from existing outputs first
    have_out = int(inv_counts.get(target, 0))
    if have_out >= required:
        inv_counts[target] = have_out - required
        return
    if have_out > 0:
        inv_counts[target] = 0
        required -= have_out

    obtain_per_craft = int(skill.obtain.get(target, 1)) if skill.obtain else 1
    crafts_needed = max(1, (required + obtain_per_craft - 1) // obtain_per_craft)

    # Expand inputs for total crafts
    for dep, qty in skill.consume.items():
        _expand_with_inventory(dep, int(qty) * crafts_needed, inv_counts, steps)

    # Ensure context
    for req, qty in skill.require.items():
        steps.append({"op": "acquire", "item": req, "count": int(qty)})

    steps.append({"op": "craft" if skill.op == "craft" else "smelt", "recipe": target, "count": crafts_needed})


def plan_craft(item_id: str, count: int, inventory_counts: Optional[Dict[str, int]] = None) -> List[Dict[str, object]]:
    """Plan using a tiny skill graph (Plan4MC-style), producing a linear step list.

    - Expands consume prerequisites recursively
    - Adds simple context requirements as acquire placeholders (e.g., furnace_nearby)
    - Leaves world acquisitions to dispatcher/chat-bridge (e.g., logs, ores)
    - Prunes leaves/outputs using provided inventory snapshot (if any)
    """
    steps: List[Dict[str, object]] = []
    inv_copy: Dict[str, int] = {k: int(v) for k, v in (inventory_counts or {}).items()}
    _expand_with_inventory(item_id, int(count), inv_copy, steps)

    # Coalesce adjacent identical acquires (keep order stable)
    coalesced: List[Dict[str, object]] = []
    for s in steps:
        if coalesced and s.get("op") == "acquire" and coalesced[-1].get("op") == "acquire" and coalesced[-1].get("item") == s.get("item"):
            coalesced[-1]["count"] = int(coalesced[-1].get("count", 1)) + int(s.get("count", 1))
        else:
            coalesced.append(s)
    steps = coalesced

    # Insert minimal tool gating for mineables: ensure a capable pickaxe appears before mining iron ore/cobblestone
    gated: List[Dict[str, object]] = []
    have_tools: Dict[str, int] = {}
    for s in steps:
        if s.get("op") == "craft" and isinstance(s.get("recipe"), str):
            tool = str(s["recipe"])  # type: ignore[index]
            have_tools[tool] = have_tools.get(tool, 0) + int(s.get("count", 1))
        if s.get("op") == "acquire" and s.get("item") in MINING_TOOL_REQUIREMENTS:
            required_any = MINING_TOOL_REQUIREMENTS[str(s["item"])]  # type: ignore[index]
            if not any(have_tools.get(t, 0) > 0 for t in required_any):
                # Craft the first acceptable tool we don't yet have (wooden -> stone -> iron)
                for candidate in required_any:
                    if have_tools.get(candidate, 0) == 0:
                        _expand_with_inventory(candidate, 1, inv_copy, gated)
                        have_tools[candidate] = 1
                        break
        gated.append(s)

    # Only concrete item ids; no generic id mapping here

    return gated
