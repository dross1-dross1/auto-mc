from __future__ import annotations

"""Deterministic planner: expand craft/smelt goals into linear steps.

Purpose: Given an item id and count, expand via a tiny skill graph into a list
of steps the mod understands (acquire/craft/smelt), including minimal tool
gating for mining.
"""

from typing import Dict, List

from .skill_graph import SKILLS, MINEABLE_ITEMS, MINING_TOOL_REQUIREMENTS


def _expand_skill(target: str, count: int, steps: List[Dict[str, object]]) -> None:
    # If target is produced via a skill, expand its parents; otherwise mark acquire
    skill = SKILLS.get(target)
    if skill is None:
        # Acquire from world
        steps.append({"op": "acquire", "item": target, "count": count})
        return

    # Expand consume dependencies
    for dep, qty in skill.consume.items():
        _expand_skill(dep, qty * count, steps)

    # Ensure required context (furnace/crafting table nearby) via simple acquire placeholders
    for req, qty in skill.require.items():
        steps.append({"op": "acquire", "item": req, "count": qty})

    # Emit operation
    op = "smelt" if skill.op == "smelt" else "craft"
    steps.append({"op": op, "recipe": target, "count": count})


def plan_craft(item_id: str, count: int) -> List[Dict[str, object]]:
    """Plan using a tiny skill graph (Plan4MC-style), producing a linear step list.

    - Expands consume prerequisites recursively
    - Adds simple context requirements as acquire placeholders (e.g., furnace_nearby)
    - Leaves world acquisitions to dispatcher/chat-bridge (e.g., logs, ores)
    - Does not deduplicate or check inventory yet (future step)
    """
    steps: List[Dict[str, object]] = []
    _expand_skill(item_id, count, steps)

    # Simple coalescing of consecutive identical acquires to avoid duplicate chat-bridge commands
    coalesced: List[Dict[str, object]] = []
    for s in steps:
        if coalesced and s.get("op") == "acquire" and coalesced[-1].get("op") == "acquire" and coalesced[-1].get("item") == s.get("item"):
            prev = coalesced[-1]
            prev["count"] = int(prev.get("count", 1)) + int(s.get("count", 1))
            continue
        coalesced.append(s)

    # Insert minimal tool gating for mineables: ensure a capable pickaxe appears before mining iron ore/cobblestone
    gated: List[Dict[str, object]] = []
    have_tools: Dict[str, int] = {}
    for s in coalesced:
        if s.get("op") == "craft" and isinstance(s.get("recipe"), str):
            tool = str(s["recipe"])  # type: ignore[index]
            have_tools[tool] = have_tools.get(tool, 0) + int(s.get("count", 1))
        if s.get("op") == "acquire" and s.get("item") in MINING_TOOL_REQUIREMENTS:
            required_any = MINING_TOOL_REQUIREMENTS[str(s["item"])]  # type: ignore[index]
            if not any(have_tools.get(t, 0) > 0 for t in required_any):
                # Prepend a stone_pickaxe craft before this acquire if not present in history
                if have_tools.get("minecraft:stone_pickaxe", 0) == 0:
                    _expand_skill("minecraft:stone_pickaxe", 1, gated)
                    have_tools["minecraft:stone_pickaxe"] = 1
        gated.append(s)

    return gated
