from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger("automc.state")


class StateService:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._save_lock = asyncio.Lock()
        self._last_telemetry: Dict[str, Dict[str, Any]] = {}

    def load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._last_telemetry = data.get("telemetry", {})
        except Exception as exc:
            logger.warning("failed to load state: %s", exc)

    async def update_telemetry(self, player_id: str, ts: str, state: Dict[str, Any]) -> None:
        self._last_telemetry[player_id] = {"ts": ts, "state": state}
        await self._save()

    def get_player_state(self, player_id: str) -> Optional[Dict[str, Any]]:
        return self._last_telemetry.get(player_id)

    def select_state(self, player_state: Dict[str, Any], selector: Optional[List[str]]) -> Dict[str, Any]:
        if not selector:
            return player_state.get("state", {})
        full = player_state.get("state", {})
        return {k: full.get(k) for k in selector if k in full}

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with self._save_lock:
            try:
                data = {"telemetry": self._last_telemetry}
                # offload writing to avoid blocking the event loop
                await asyncio.to_thread(self._path.write_text, json.dumps(data, separators=(",", ":")), "utf-8")
            except Exception as exc:
                logger.warning("failed to save state: %s", exc)


