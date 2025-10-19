from __future__ import annotations

import unittest

from backend.intents import parse_command_text


class TestIntents(unittest.TestCase):
    def test_echo(self) -> None:
        self.assertEqual(parse_command_text("!echo hello"), {"type": "echo", "text": "hello"})

    def test_craft_normalization_simple(self) -> None:
        intent = parse_command_text("!craft 2 stick")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:stick", "count": 2})

    def test_craft_aliases(self) -> None:
        intent = parse_command_text("!craft 1 iron pick")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:iron_pickaxe", "count": 1})
        intent2 = parse_command_text("!craft 1 iron pickaxe")
        self.assertEqual(intent2, {"type": "craft_item", "item": "minecraft:iron_pickaxe", "count": 1})

    def test_craft_explicit_namespace(self) -> None:
        intent = parse_command_text("!craft 4 minecraft:torch")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:torch", "count": 4})

    def test_non_command_returns_none(self) -> None:
        self.assertIsNone(parse_command_text("hello"))


if __name__ == "__main__":
    unittest.main()


