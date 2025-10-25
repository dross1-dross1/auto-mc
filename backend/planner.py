from __future__ import annotations

"""Deterministic planner: expand craft/smelt goals into linear steps.

Purpose: Given an item id and count, expand via a tiny skill graph into a list
of steps the mod understands (acquire/craft/smelt), including minimal tool
gating for mining.

"""

from typing import Dict, List, Optional

from .data_files import load_tool_tiers, load_skill_graph, load_mineable_items
from .state_service import StateService  # type: ignore


def _expand_with_inventory(target: str, required: int, inv_counts: Dict[str, int], steps: List[Dict[str, object]]) -> None:
    """Inventory-aware expansion: prune leaves/outputs using current inventory, emit only missing deltas."""
    if required <= 0:
        return
    skills = load_skill_graph()
    skill = skills.get(target)
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

    obtain_per_craft = int((skill.get("obtain") or {}).get(target, 1))
    crafts_needed = max(1, (required + obtain_per_craft - 1) // obtain_per_craft)

    # Expand inputs for total crafts
    for dep, qty in (skill.get("consume") or {}).items():
        _expand_with_inventory(dep, int(qty) * crafts_needed, inv_counts, steps)

    # Ensure context
    for req, qty in (skill.get("require") or {}).items():
        steps.append({"op": "acquire", "item": req, "count": int(qty)})
    # Account for outputs produced by this craft/smelt so downstream expansions can reuse them
    produced_total = crafts_needed * obtain_per_craft
    inv_counts[target] = int(inv_counts.get(target, 0)) + produced_total
    # Consume the required amount from the produced/available pool, leaving any extra available
    have_after = int(inv_counts.get(target, 0))
    if have_after >= required:
        inv_counts[target] = have_after - required
    else:
        inv_counts[target] = 0

    steps.append({"op": "craft" if skill.get("op") == "craft" else "smelt", "recipe": target, "count": crafts_needed})


def plan_craft(item_id: str, count: int, inventory_counts: Optional[Dict[str, int]] = None) -> List[Dict[str, object]]:
    """Produce a linear step list based on a small skill graph.

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
    try:
        tool_tiers = load_tool_tiers()
    except Exception:
        tool_tiers = {}
    for s in steps:
        if s.get("op") == "craft" and isinstance(s.get("recipe"), str):
            tool = str(s["recipe"])  # type: ignore[index]
            have_tools[tool] = have_tools.get(tool, 0) + int(s.get("count", 1))
        if s.get("op") == "acquire" and str(s.get("item")) in tool_tiers:
            required_any = tool_tiers[str(s["item"])]  # type: ignore[index]
            if not any(have_tools.get(t, 0) > 0 for t in required_any):
                # Craft the first acceptable tool we don't yet have (wooden -> stone -> iron)
                for candidate in required_any:
                    if have_tools.get(candidate, 0) == 0:
                        _expand_with_inventory(candidate, 1, inv_copy, gated)
                        have_tools[candidate] = 1
                        break
        gated.append(s)

    # Reorder for context: if the root craft requires a context (e.g., crafting_table_nearby),
    # aggregate world acquisitions (logs/ores) up-front, then ensure context, then do conversions/crafts.
    skills = load_skill_graph()
    root_skill = skills.get(item_id)
    requires_ctx = set((root_skill.get("require") or {}).keys()) if root_skill else set()
    ctx_items = {r for r in requires_ctx if r in {"crafting_table_nearby", "furnace_nearby"}}
    if not ctx_items:
        return gated

    skill_keys = set(skills.keys())
    world_set = set(load_mineable_items())
    world_counts: Dict[str, int] = {}
    post_steps: List[Dict[str, object]] = []
    need_ctx: Dict[str, int] = {}
    for s in gated:
        if s.get("op") == "acquire":
            item = str(s.get("item", ""))
            if item in {"crafting_table_nearby", "furnace_nearby"}:
                need_ctx[item] = 1
                continue
            if (item in world_set) or (item not in skill_keys):
                world_counts[item] = world_counts.get(item, 0) + int(s.get("count", 1))
                continue
        # Annotate conversions with required context when present
        if s.get("op") in {"craft", "smelt"}:
            if "crafting_table_nearby" in ctx_items:
                s = {**s, "context": "crafting_table"}
            if "furnace_nearby" in ctx_items and s.get("op") == "smelt":
                s = {**s, "context": "furnace"}
        post_steps.append(s)

    reordered: List[Dict[str, object]] = []
    for it, c in world_counts.items():
        reordered.append({"op": "acquire", "item": it, "count": int(c)})
    # Ensure context once (if required)
    for ctx in ("crafting_table_nearby", "furnace_nearby"):
        if ctx in ctx_items:
            reordered.append({"op": "acquire", "item": ctx, "count": 1})
    # Then perform conversions/crafts/smelts
    reordered.extend(post_steps)
    return reordered
