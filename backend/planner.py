from __future__ import annotations

from typing import Dict, List


# Minimal craft graph and recipes for v0
RECIPE_DEPENDENCIES: Dict[str, List[str]] = {
    "minecraft:stick": ["minecraft:planks"],
    "minecraft:crafting_table": ["minecraft:planks"],
    "minecraft:furnace": [],
    "minecraft:iron_ingot": ["minecraft:iron_ore"],  # smelt ore with fuel (omitted here)
    "minecraft:torch": ["minecraft:coal", "minecraft:stick"],
    "minecraft:iron_pickaxe": ["minecraft:iron_ingot", "minecraft:stick"],
}


def plan_craft(item_id: str, count: int) -> List[Dict[str, object]]:
    """Produce a simple linear plan to acquire dependencies and craft the target.

    This v0 implementation assumes missing prerequisites and outputs generic steps:
    - acquire for base resources
    - craft/smelt for derived outputs
    """
    steps: List[Dict[str, object]] = []

    def need(dep: str, qty: int) -> None:
        deps = RECIPE_DEPENDENCIES.get(dep, None)
        if deps is None:
            # Treat unknown as base acquisition
            steps.append({"op": "acquire", "item": dep, "count": qty})
            return
        if not deps:
            # base but known
            steps.append({"op": "acquire", "item": dep, "count": qty})
            return
        # Expand dependencies with a naive multiplier
        for sub in deps:
            need(sub, qty)
        # Decide operation type
        op = "smelt" if dep == "minecraft:iron_ingot" else "craft"
        steps.append({"op": op, "recipe": dep, "count": qty})

    # Expand for target item
    need(item_id, count)
    return steps
