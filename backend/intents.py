from __future__ import annotations

"""Parse chat commands into deterministic intents.

Purpose: Translate a small set of '!'-prefixed commands into explicit intent
dicts for the planner/dispatcher, avoiding LLM dependence in v0.

Supported patterns:
- !echo <text>
- !craft <count> <item words>

"""

import re
from typing import Dict, Optional


def parse_command_text(text: str) -> Optional[Dict[str, object]]:
    text = text.strip()
    if not text.startswith("!"):
        return None

    if text == "!help" or text.startswith("!help "):
        return {"type": "help"}

    if text == "!who" or text.startswith("!who "):
        return {"type": "who"}

    if text.startswith("!echo "):
        return {"type": "echo", "text": text[len("!echo ") :].strip()}

    m = re.match(r"^!craft\s+(\d+)\s+(.+)$", text)
    if m:
        count = int(m.group(1))
        item_words = m.group(2).strip().lower().replace(" ", "_")
        # Naive normalization of common items
        item_map = {
            "iron_pickaxe": "minecraft:iron_pickaxe",
            "iron_pick": "minecraft:iron_pickaxe",
            "stick": "minecraft:stick",
            "sticks": "minecraft:stick",
            "planks": "minecraft:planks",
            "crafting_table": "minecraft:crafting_table",
            "furnace": "minecraft:furnace",
            "torch": "minecraft:torch",
            "torches": "minecraft:torch",
        }
        item_id = item_map.get(item_words, item_words if ":" in item_words else f"minecraft:{item_words}")
        return {"type": "craft_item", "item": item_id, "count": count}

    # !echomulti name1,name2 <message|#cmd|.cmd>
    m2 = re.match(r"^!echomulti\s+([^\s]+)\s+(.+)$", text)
    if m2:
        targets_csv = m2.group(1).strip()
        payload = m2.group(2).strip()
        # Interpret '!echo X' as plain text X
        if payload.startswith("!echo "):
            payload = payload[len("!echo ") :].strip()
        # Pass through commands like '#...' or '. ...'
        targets = [t.strip() for t in targets_csv.split(",") if t.strip()]
        return {"type": "multicast", "targets": targets, "text": payload}

    # !echoall <message|#cmd|.cmd>
    m3 = re.match(r"^!echoall\s+(.+)$", text)
    if m3:
        payload = m3.group(1).strip()
        if payload.startswith("!echo "):
            payload = payload[len("!echo ") :].strip()
        return {"type": "broadcast", "text": payload}

    return None
