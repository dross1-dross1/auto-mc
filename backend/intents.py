from __future__ import annotations

"""Parse chat commands into deterministic intents.

Purpose: Translate a small set of '!'-prefixed commands into explicit intent
dicts for the planner/dispatcher.

Supported patterns:
- !echo <text>
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

    if text.startswith("!echo "):
        # Normalize nested echo forms by stripping repeated '!echo ' prefixes
        payload = text[len("!echo ") :].strip()
        while payload.startswith("!echo "):
            payload = payload[len("!echo ") :].strip()
        return {"type": "echo", "text": payload}

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
