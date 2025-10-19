from __future__ import annotations

import unittest
from typing import Dict, List

from backend.planner import plan_craft


def find_first_index(steps: List[Dict[str, object]], pred) -> int:
    for i, s in enumerate(steps):
        try:
            if pred(s):
                return i
        except Exception:
            continue
    return -1


class TestPlanner(unittest.TestCase):
    def test_plan_iron_pickaxe_contains_key_steps_and_gating_order(self) -> None:
        steps = plan_craft("minecraft:iron_pickaxe", 1)
        # Must contain ensure-context for furnace and a smelt for iron ingot and final craft
        idx_furnace_req = find_first_index(steps, lambda s: s.get("op") == "acquire" and s.get("item") == "furnace_nearby")
        idx_smelt_ingot = find_first_index(steps, lambda s: s.get("op") == "smelt" and s.get("recipe") == "minecraft:iron_ingot")
        idx_final_craft = find_first_index(steps, lambda s: s.get("op") == "craft" and s.get("recipe") == "minecraft:iron_pickaxe")
        self.assertNotEqual(idx_furnace_req, -1, "missing furnace ensure placeholder")
        self.assertNotEqual(idx_smelt_ingot, -1, "missing smelt iron_ingot step")
        self.assertNotEqual(idx_final_craft, -1, "missing final craft iron_pickaxe step")
        self.assertLess(idx_furnace_req, idx_smelt_ingot)
        self.assertLess(idx_smelt_ingot, idx_final_craft)

        # Gating: ensure a capable pickaxe is crafted before acquiring iron_ore specifically
        idx_acq_iron_ore = find_first_index(steps, lambda s: s.get("op") == "acquire" and s.get("item") == "minecraft:iron_ore")
        idx_craft_stone = find_first_index(steps, lambda s: s.get("op") == "craft" and s.get("recipe") == "minecraft:stone_pickaxe")
        self.assertNotEqual(idx_acq_iron_ore, -1, "iron_ore acquire not found")
        self.assertNotEqual(idx_craft_stone, -1, "stone_pickaxe craft not inserted before iron mining")
        self.assertLess(idx_craft_stone, idx_acq_iron_ore, "stone pick should precede iron ore mining")


if __name__ == "__main__":
    unittest.main()
