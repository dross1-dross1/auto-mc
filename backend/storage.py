from __future__ import annotations

"""Shared storage catalog for container inventories across agents.

Purpose: Track latest inventory snapshots by container key and provide simple
item count queries for planner/dispatcher decisions.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Tuple


ContainerKey = Tuple[str, Tuple[int, int, int]]  # (dim, pos)


@dataclass
class ContainerState:
    version: int
    container_type: str
    ts_iso: str
    slots: Dict[int, Dict[str, Any]]  # slot index -> {id, count, nbt?}


class StorageCatalog:
    def __init__(self, path: Path | str = Path("data/storage_catalog.json")) -> None:
        self._by_key: Dict[ContainerKey, ContainerState] = {}
        self._path: Path = Path(path)
        self._load()

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
        ctype = str(container.get("container_type", ""))
        ts_iso = str(container.get("ts_iso", ""))
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
        self._by_key[key] = ContainerState(version=version, container_type=ctype, ts_iso=ts_iso, slots=slots)
        self._save()

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
        self._save()

    def count_item(self, item_id: str) -> int:
        total = 0
        for state in self._by_key.values():
            for slot in state.slots.values():
                if slot.get("id") == item_id:
                    total += int(slot.get("count", 0))
        return total

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            serial: Dict[str, Any] = {}
            for (dim, pos), st in self._by_key.items():
                key = f"{dim}@{pos[0]},{pos[1]},{pos[2]}"
                serial[key] = {
                    "version": st.version,
                    "container_type": st.container_type,
                    "ts_iso": st.ts_iso,
                    "slots": st.slots,
                }
            self._path.write_text(json.dumps(serial, indent=2), encoding="utf-8")
        except Exception:
            # best-effort persistence
            pass

    def _load(self) -> None:
        try:
            if not self._path.exists():
                return
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            out: Dict[ContainerKey, ContainerState] = {}
            for key, data in raw.items():
                try:
                    dim, pos_s = key.split("@", 1)
                    x, y, z = [int(p) for p in pos_s.split(",", 3)]
                    version = int(data.get("version", 0))
                    container_type = str(data.get("container_type", ""))
                    ts_iso = str(data.get("ts_iso", ""))
                    slots_in = data.get("slots", {}) or {}
                    slots: Dict[int, Dict[str, Any]] = {int(k): v for k, v in slots_in.items()} if isinstance(slots_in, dict) else {}
                    out[(dim, (x, y, z))] = ContainerState(version=version, container_type=container_type, ts_iso=ts_iso, slots=slots)
                except Exception:
                    continue
            self._by_key = out
        except Exception:
            # ignore load errors
            self._by_key = {}
