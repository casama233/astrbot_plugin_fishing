from __future__ import annotations

import sqlite3
import sys
import tempfile
import types

from datetime import datetime


# Provide a lightweight astrbot.api.logger stub for unit tests.
class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    api_module.logger = _DummyLogger()
    astrbot_module.api = api_module
    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module

from core.repositories.sqlite_inventory_repo import SqliteInventoryRepository


def _create_minimal_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE fish (
                fish_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                rarity INTEGER NOT NULL,
                base_value INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE user_fish_inventory (
                user_id TEXT NOT NULL,
                fish_id INTEGER NOT NULL,
                quality_level INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY (user_id, fish_id, quality_level)
            )
            """
        )


def test_sell_fish_keep_one_counts_quality_value():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _create_minimal_db(tmp.name)
        repo = SqliteInventoryRepository(tmp.name)

        with sqlite3.connect(tmp.name) as conn:
            conn.execute(
                "INSERT INTO fish (fish_id, name, rarity, base_value) VALUES (?, ?, ?, ?)",
                (1, "TestFish", 2, 100),
            )
            conn.execute(
                "INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity) VALUES (?, ?, ?, ?)",
                ("u1", 1, 0, 3),
            )
            conn.execute(
                "INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity) VALUES (?, ?, ?, ?)",
                ("u1", 1, 1, 2),
            )
            conn.commit()

        sold_value = repo.sell_fish_keep_one("u1")

        assert sold_value == 400

        with sqlite3.connect(tmp.name) as conn:
            rows = conn.execute(
                "SELECT quality_level, quantity FROM user_fish_inventory WHERE user_id = ? ORDER BY quality_level",
                ("u1",),
            ).fetchall()
            assert rows == [(0, 1), (1, 1)]
