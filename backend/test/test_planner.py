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
    def test_planks_yield_respected(self) -> None:
        steps = plan_craft("minecraft:planks", 4)
        # Expect a single craft step for planks with count 1 because recipe yields 4
        crafts = [s for s in steps if s.get("op") == "craft" and s.get("recipe") == "minecraft:planks"]
        self.assertTrue(crafts, "no craft for planks")
        self.assertEqual(int(crafts[-1].get("count", 0)), 1)

    def test_plan_iron_pickaxe_contains_key_steps_and_gating_order(self) -> None:
        steps = plan_craft("minecraft:iron_pickaxe", 1)
        idx_furnace_req = find_first_index(steps, lambda s: s.get("op") == "acquire" and s.get("item") == "furnace_nearby")
        idx_smelt_ingot = find_first_index(steps, lambda s: s.get("op") == "smelt" and s.get("recipe") == "minecraft:iron_ingot")
        idx_final_craft = find_first_index(steps, lambda s: s.get("op") == "craft" and s.get("recipe") == "minecraft:iron_pickaxe")
        self.assertNotEqual(idx_furnace_req, -1)
        self.assertNotEqual(idx_smelt_ingot, -1)
        self.assertNotEqual(idx_final_craft, -1)
        self.assertLess(idx_furnace_req, idx_smelt_ingot)
        self.assertLess(idx_smelt_ingot, idx_final_craft)

        idx_acq_iron_ore = find_first_index(steps, lambda s: s.get("op") == "acquire" and s.get("item") == "minecraft:iron_ore")
        idx_craft_stone = find_first_index(steps, lambda s: s.get("op") == "craft" and s.get("recipe") == "minecraft:stone_pickaxe")
        self.assertNotEqual(idx_acq_iron_ore, -1)
        self.assertNotEqual(idx_craft_stone, -1)
        self.assertLess(idx_craft_stone, idx_acq_iron_ore)


if __name__ == "__main__":
    unittest.main()


