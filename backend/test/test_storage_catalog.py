from __future__ import annotations

import unittest


class TestStorageCatalog(unittest.TestCase):
    def test_snapshot_and_query_counts(self) -> None:
        from backend.storage import StorageCatalog  # to be implemented

        cat = StorageCatalog()
        snapshot = {
            "dim": "minecraft:overworld",
            "pos": (123, 64, -45),
            "container_type": "minecraft:chest",
            "version": 7,
            "hash": "b1c2",
            "slots": [
                {"slot": 0, "id": "minecraft:iron_ingot", "count": 12},
                {"slot": 1, "id": "minecraft:coal", "count": 8},
            ],
        }
        cat.handle_snapshot("p1", snapshot)
        self.assertEqual(cat.count_item("minecraft:iron_ingot"), 12)
        self.assertEqual(cat.count_item("minecraft:coal"), 8)

    def test_diff_updates_counts(self) -> None:
        from backend.storage import StorageCatalog

        cat = StorageCatalog()
        key = {"dim": "minecraft:overworld", "pos": (123, 64, -45)}
        snapshot = {
            "dim": key["dim"],
            "pos": key["pos"],
            "container_type": "minecraft:chest",
            "version": 7,
            "hash": "b1c2",
            "slots": [
                {"slot": 0, "id": "minecraft:iron_ingot", "count": 12},
                {"slot": 1, "id": "minecraft:coal", "count": 8},
            ],
        }
        cat.handle_snapshot("p1", snapshot)
        diff = {
            "container_key": key,
            "from_version": 7,
            "to_version": 8,
            "adds": [{"slot": 2, "id": "minecraft:stick", "count": 4}],
            "removes": [{"slot": 1, "id": "minecraft:coal", "count": 1}],
            "moves": [],
        }
        cat.handle_diff("p1", diff)
        self.assertEqual(cat.count_item("minecraft:iron_ingot"), 12)
        self.assertEqual(cat.count_item("minecraft:coal"), 7)
        self.assertEqual(cat.count_item("minecraft:stick"), 4)


if __name__ == "__main__":
    unittest.main()


