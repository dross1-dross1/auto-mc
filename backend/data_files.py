from __future__ import annotations

"""Runtime data file loaders (JSON).

Purpose: Centralize loading of external JSON mappings that control acquisition
and tool tier requirements, keeping code free of hardcoded tables.
"""

import json
from pathlib import Path
from typing import Any, Dict


_CACHE: Dict[str, Any] = {}


def _load_required(path: Path) -> Any:
    key = str(path.resolve())
    if key in _CACHE:
        return _CACHE[key]
    if not path.exists():
        raise FileNotFoundError(f"required data file missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"failed to parse {path}: {e}")
    _CACHE[key] = data
    return data


def load_acquisition_map() -> Dict[str, str]:
    """Return mapping of item_id -> baritone target string (e.g., iron_ore)."""
    data = _load_required(Path("settings/acquisition_map.json"))
    if not isinstance(data, dict):
        raise ValueError("acquisition_map.json must be an object of {item_id: target}")
    # Normalize keys/values to strings
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("acquisition_map contains non-string key/value")
        out[k] = v
    return out


def load_tool_tiers() -> Dict[str, list[str]]:
    """Return mapping of mineable item_id -> ordered list of acceptable tool ids."""
    data = _load_required(Path("settings/tool_tiers.json"))
    if not isinstance(data, dict):
        raise ValueError("tool_tiers.json must be an object of {item_id: [tools...]}\n")
    out: Dict[str, list[str]] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ValueError("tool_tiers contains invalid entry")
        out[k] = list(v)
    return out


def load_aliases() -> Dict[str, str]:
    """Return mapping of alias -> canonical item_id (e.g., iron_pick -> minecraft:iron_pickaxe)."""
    data = _load_required(Path("settings/aliases.json"))
    if not isinstance(data, dict):
        raise ValueError("aliases.json must be an object of {alias: canonical_id}")
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("aliases.json contains invalid entry")
        out[k.strip().lower()] = v.strip()
    return out

