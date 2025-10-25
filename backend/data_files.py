from __future__ import annotations

"""Runtime data file loaders (JSON).

Purpose: Centralize loading of external JSON mappings that control acquisition
and tool tier requirements, keeping code free of hardcoded tables.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


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


def load_skill_graph() -> Dict[str, Dict[str, Any]]:
    """Return mapping of recipe_id -> skill dict {op, consume, require, obtain}.

    File: settings/skill_graph.json with shape: { "skills": { <id>: { ... } } }
    """
    data = _load_required(Path("settings/skill_graph.json"))
    if not isinstance(data, dict) or "skills" not in data or not isinstance(data["skills"], dict):
        raise ValueError("skill_graph.json must contain top-level 'skills' object")
    skills_in = data["skills"]
    out: Dict[str, Dict[str, Any]] = {}
    for rid, skill in skills_in.items():
        if not isinstance(rid, str) or not isinstance(skill, dict):
            raise ValueError("invalid skill entry in skill_graph.json")
        # Basic shape validation
        op = skill.get("op")
        consume = skill.get("consume", {})
        require = skill.get("require", {})
        obtain = skill.get("obtain", {})
        if op not in ("craft", "smelt"):
            raise ValueError(f"skill '{rid}' has invalid op")
        if not isinstance(consume, dict) or not isinstance(require, dict) or not isinstance(obtain, dict):
            raise ValueError(f"skill '{rid}' fields must be objects")
        out[rid] = {
            "op": op,
            "consume": {str(k): int(v) for k, v in consume.items()},
            "require": {str(k): int(v) for k, v in require.items()},
            "obtain": {str(k): int(v) for k, v in obtain.items()},
        }
    return out


def load_mineable_items() -> List[str]:
    """Return list of item ids that are acquired from world mining.

    File: settings/mineable_items.json (array of strings).
    """
    data = _load_required(Path("settings/mineable_items.json"))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ValueError("mineable_items.json must be an array of strings")
    return list(data)

