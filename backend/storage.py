from __future__ import annotations

"""Shared storage catalog for container inventories across agents.

Purpose: Track latest inventory snapshots by container key and provide simple
item count queries for planner/dispatcher decisions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple


ContainerKey = Tuple[str, Tuple[int, int, int]]  # (dim, pos)


@dataclass
class ContainerState:
    version: int
    slots: Dict[int, Dict[str, Any]]  # slot index -> {id, count, nbt?}


class StorageCatalog:
    def __init__(self) -> None:
        self._by_key: Dict[ContainerKey, ContainerState] = {}

    @staticmethod
    def _key_from_snapshot(snap: Dict[str, Any]) -> ContainerKey:
        pos = snap.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            key_pos = (int(pos[0]), int(pos[1]), int(pos[2]))
        else:
            raise ValueError("snapshot pos missing")
        dim = str(snap.get("dim"))
        return (dim, key_pos)

    def handle_snapshot(self, player_id: str, container: Dict[str, Any]) -> None:
        key = self._key_from_snapshot(container)
        version = int(container.get("version", 0))
        slots_raw = container.get("slots", [])
        slots: Dict[int, Dict[str, Any]] = {}
        for s in slots_raw:
            try:
                idx = int(s.get("slot"))
                iid = str(s.get("id"))
                cnt = int(s.get("count", 0))
                slots[idx] = {"id": iid, "count": cnt}
            except Exception:
                continue
        self._by_key[key] = ContainerState(version=version, slots=slots)

    def handle_diff(self, player_id: str, diff: Dict[str, Any]) -> None:
        ck = diff.get("container_key", {})
        dim = str(ck.get("dim"))
        pos = ck.get("pos")
        if not isinstance(pos, (list, tuple)) or len(pos) != 3:
            raise ValueError("diff container_key.pos invalid")
        key: ContainerKey = (dim, (int(pos[0]), int(pos[1]), int(pos[2])))
        state = self._by_key.get(key)
        if state is None:
            # ignore diffs with no baseline
            return
        # Apply removes
        for r in diff.get("removes", []) or []:
            try:
                idx = int(r.get("slot"))
                if idx in state.slots:
                    current = state.slots[idx]
                    current["count"] = max(0, int(current.get("count", 0)) - int(r.get("count", 0)))
                    if current["count"] <= 0:
                        state.slots.pop(idx, None)
            except Exception:
                continue
        # Apply adds
        for a in diff.get("adds", []) or []:
            try:
                idx = int(a.get("slot"))
                iid = str(a.get("id"))
                add = int(a.get("count", 0))
                cur = state.slots.get(idx, {"id": iid, "count": 0})
                # if id changes, replace
                if cur.get("id") != iid:
                    cur = {"id": iid, "count": 0}
                cur["count"] = int(cur.get("count", 0)) + add
                state.slots[idx] = cur
            except Exception:
                continue
        # Bump version if valid
        to_ver = diff.get("to_version")
        if isinstance(to_ver, int):
            state.version = to_ver

    def count_item(self, item_id: str) -> int:
        total = 0
        for state in self._by_key.values():
            for slot in state.slots.values():
                if slot.get("id") == item_id:
                    total += int(slot.get("count", 0))
        return total


