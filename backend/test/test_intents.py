from __future__ import annotations

import unittest

from backend.intents import parse_command_text


class TestIntents(unittest.TestCase):
    def test_echo(self) -> None:
        self.assertEqual(parse_command_text("!echo hello"), {"type": "echo", "text": "hello"})

    def test_get_normalization_simple(self) -> None:
        intent = parse_command_text("!get stick 2")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:stick", "count": 2})

    def test_get_aliases(self) -> None:
        intent = parse_command_text("!get iron pick 1")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:iron_pickaxe", "count": 1})
        intent2 = parse_command_text("!get iron pickaxe 1")
        self.assertEqual(intent2, {"type": "craft_item", "item": "minecraft:iron_pickaxe", "count": 1})

    def test_get_explicit_namespace(self) -> None:
        intent = parse_command_text("!get minecraft:torch 4")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:torch", "count": 4})

    def test_get_planks_normalizes_to_oak_planks(self) -> None:
        intent = parse_command_text("!get planks 1")
        self.assertEqual(intent, {"type": "craft_item", "item": "minecraft:oak_planks", "count": 1})

    def test_non_command_returns_none(self) -> None:
        self.assertIsNone(parse_command_text("hello"))

    def test_help(self) -> None:
        self.assertEqual(parse_command_text("!help"), {"type": "help"})

    def test_echomulti_parse(self) -> None:
        intent = parse_command_text("!echomulti a,b !echo hi")
        self.assertEqual(intent, {"type": "multicast", "targets": ["a", "b"], "text": "hi"})
        intent2 = parse_command_text("!echomulti a,b #stop")
        self.assertEqual(intent2, {"type": "multicast", "targets": ["a", "b"], "text": "#stop"})

    def test_echoall_parse(self) -> None:
        intent = parse_command_text("!echoall !echo hi")
        self.assertEqual(intent, {"type": "broadcast", "text": "hi"})
        intent2 = parse_command_text("!echoall .say hi")
        self.assertEqual(intent2, {"type": "broadcast", "text": ".say hi"})

    def test_who_parse(self) -> None:
        self.assertEqual(parse_command_text("!who"), {"type": "who"})


if __name__ == "__main__":
    unittest.main()


