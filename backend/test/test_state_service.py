from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.state_service import StateService


class TestStateService(unittest.TestCase):
    def test_persist_and_select(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            svc = StateService(path)
            svc.load()
            self.assertIsNone(svc.get_player_state("p1"))

            import asyncio

            asyncio.get_event_loop().run_until_complete(
                svc.update_telemetry("p1", "2025-10-19T00:00:00Z", {"inventory": [1], "equipment": {}})
            )
            self.assertIsNotNone(svc.get_player_state("p1"))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("telemetry", data)

            full = svc.get_player_state("p1")
            sel = svc.select_state(full or {}, ["equipment"])  # type: ignore[arg-type]
            self.assertEqual(sel, {"equipment": {}})


if __name__ == "__main__":
    unittest.main()


