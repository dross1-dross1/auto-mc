from __future__ import annotations

"""Parse chat commands into deterministic intents.

Purpose: Translate a small set of '!'-prefixed commands into explicit intent
dicts for the planner/dispatcher.

Supported patterns:
- !say <text|!command|#cmd|.cmd>
- !saymulti <name1,name2,...> <text|!command|#cmd|.cmd>
- !sayall <text|!command|#cmd|.cmd>
- !get <item words> <count>

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

    if text == "!stop":
        return {"type": "stop"}

    # !say <payload>
    if text == "!say" or text.startswith("!say "):
        if text == "!say":
            return {"type": "usage", "cmd": "say"}
        payload = text[len("!say ") :].strip()
        return {"type": "say", "text": payload}

    m = re.match(r"^!get\s+(.+)\s+(\d+)$", text)
    if m:
        item_words = m.group(1).strip().lower().replace(" ", "_")
        count = int(m.group(2))
        # Normalization: resolve aliases from data file first, else assume minecraft: namespace
        try:
            from .data_files import load_aliases  # lazy import
            aliases = load_aliases()
        except Exception:
            aliases = {}
        base = aliases.get(item_words, item_words)
        item_id = base if ":" in base else f"minecraft:{base}"
        return {"type": "craft_item", "item": item_id, "count": count}
    if text == "!get" or text.startswith("!get "):
        return {"type": "usage", "cmd": "get"}

    # !saymulti name1,name2 <message|#cmd|.cmd|!command>
    m2 = re.match(r"^!saymulti\s+([^\s]+)\s+(.+)$", text)
    if m2:
        targets_csv = m2.group(1).strip()
        payload = m2.group(2).strip()
        # Pass through commands like '#...' or '. ...'
        targets = [t.strip() for t in targets_csv.split(",") if t.strip()]
        return {"type": "saymulti", "targets": targets, "text": payload}
    if text == "!saymulti" or text.startswith("!saymulti ") and not re.match(r"^!saymulti\s+[^\s]+\s+.+$", text):
        return {"type": "usage", "cmd": "saymulti"}

    # !sayall <message|#cmd|.cmd|!command>
    m3 = re.match(r"^!sayall\s+(.+)$", text)
    if m3:
        payload = m3.group(1).strip()
        return {"type": "sayall", "text": payload}
    if text == "!sayall":
        return {"type": "usage", "cmd": "sayall"}

    return None
