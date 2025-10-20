from __future__ import annotations

"""Skill graph and mining constraints used by the deterministic planner.

Purpose: Provide minimal craft/smelt dependencies and context requirements for
early goals (e.g., iron_pickaxe), and define world-acquired items and tool
gating rules for mining.

Engineering notes: Use concrete item ids (e.g., minecraft:oak_log) rather than
ambiguous placeholders. Keep the graph small and explicit; avoid speculative
abstractions.
"""

from dataclasses import dataclass
from typing import Dict, List, Mapping


@dataclass(frozen=True)
class Skill:
    consume: Mapping[str, int]
    require: Mapping[str, int]
    obtain: Mapping[str, int]
    op: str  # craft | smelt


# Minimal skill graph (Plan4MC-style) sufficient for v0 goals
SKILLS: Dict[str, Skill] = {
    # 2x2 crafting (use concrete item ids to mirror game naming)
    "minecraft:oak_planks": Skill(
        consume={"minecraft:oak_log": 1},
        require={},
        obtain={"minecraft:oak_planks": 4},
        op="craft",
    ),
    "minecraft:stick": Skill(
        consume={"minecraft:oak_planks": 2},
        require={},
        obtain={"minecraft:stick": 4},
        op="craft",
    ),
    "minecraft:crafting_table": Skill(
        consume={"minecraft:oak_planks": 4},
        require={},
        obtain={"minecraft:crafting_table": 1},
        op="craft",
    ),

    # Crafting table recipes
    "minecraft:wooden_pickaxe": Skill(
        consume={"minecraft:planks": 3, "minecraft:stick": 2},
        require={"crafting_table_nearby": 1},
        obtain={"minecraft:wooden_pickaxe": 1},
        op="craft",
    ),
    "minecraft:stone_pickaxe": Skill(
        consume={"minecraft:cobblestone": 3, "minecraft:stick": 2},
        require={"crafting_table_nearby": 1},
        obtain={"minecraft:stone_pickaxe": 1},
        op="craft",
    ),
    "minecraft:furnace": Skill(
        consume={"minecraft:cobblestone": 8},
        require={"crafting_table_nearby": 1},
        obtain={"minecraft:furnace": 1},
        op="craft",
    ),

    # Smelting
    "minecraft:iron_ingot": Skill(
        consume={"minecraft:iron_ore": 1, "minecraft:oak_planks": 1},  # simple fuel for v0
        require={"furnace_nearby": 1},
        obtain={"minecraft:iron_ingot": 1},
        op="smelt",
    ),

    # Final tool
    "minecraft:iron_pickaxe": Skill(
        consume={"minecraft:iron_ingot": 3, "minecraft:stick": 2},
        require={"crafting_table_nearby": 1},
        obtain={"minecraft:iron_pickaxe": 1},
        op="craft",
    ),
}


# Items we "acquire" from the world (chat-bridge via Baritone)
MINEABLE_ITEMS: List[str] = [
    "minecraft:oak_log",
    "minecraft:cobblestone",
    "minecraft:iron_ore",
    "minecraft:coal",
]

# Minimal tool gating for mineables
MINING_TOOL_REQUIREMENTS: Dict[str, List[str]] = {
    "minecraft:cobblestone": ["minecraft:wooden_pickaxe", "minecraft:stone_pickaxe", "minecraft:iron_pickaxe"],
    "minecraft:iron_ore": ["minecraft:stone_pickaxe", "minecraft:iron_pickaxe"],
}
