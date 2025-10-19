from __future__ import annotations

import re
from typing import Dict, Optional


def parse_command_text(text: str) -> Optional[Dict[str, object]]:
    """Parse chat text to a deterministic intent dict.

    Supported patterns:
    - !echo <text>
    - !craft <count> <item words>
    """
    text = text.strip()
    if not text.startswith("!"):
        return None

    if text.startswith("!echo "):
        return {"type": "echo", "text": text[len("!echo ") :].strip()}

    m = re.match(r"^!craft\s+(\d+)\s+(.+)$", text)
    if m:
        count = int(m.group(1))
        item_words = m.group(2).strip().lower().replace(" ", "_")
        # naive normalization of common items
        item_map = {
            "iron_pickaxe": "minecraft:iron_pickaxe",
            "iron_pick": "minecraft:iron_pickaxe",
            "stick": "minecraft:stick",
            "sticks": "minecraft:stick",
            "planks": "minecraft:oak_planks",  # generic
            "crafting_table": "minecraft:crafting_table",
            "furnace": "minecraft:furnace",
            "torch": "minecraft:torch",
            "torches": "minecraft:torch",
        }
        item_id = item_map.get(item_words, item_words if ":" in item_words else f"minecraft:{item_words}")
        return {"type": "craft_item", "item": item_id, "count": count}

    return None
