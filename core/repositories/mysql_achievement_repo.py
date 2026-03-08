from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import Achievement
from .abstract_repository import AbstractAchievementRepository, UserAchievementProgress


class MysqlAchievementRepository(AbstractAchievementRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _row_to_achievement(self, row) -> Optional[Achievement]:
        if not row:
            return None
        data = dict(row)
        data["is_repeatable"] = bool(data.get("is_repeatable", 0))
        return Achievement(**data)

    def get_all_achievements(self) -> List[Achievement]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM achievements ORDER BY achievement_id")
                return [
                    self._row_to_achievement(row) for row in cursor.fetchall() if row
                ]

    def get_user_progress(self, user_id: str) -> UserAchievementProgress:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT achievement_id, current_progress, completed_at FROM user_achievement_progress WHERE user_id = %s",
                    (user_id,),
                )
                rows = cursor.fetchall()
                progress = {}
                for row in rows:
                    achievement_id = row["achievement_id"]
                    progress[achievement_id] = {
                        "progress": row["current_progress"],
                        "completed_at": row["completed_at"],
                    }
                return progress

    def update_user_progress(
        self,
        user_id: str,
        achievement_id: int,
        progress: int,
        completed_at: Optional[datetime],
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT completed_at FROM user_achievement_progress WHERE user_id = %s AND achievement_id = %s",
                    (user_id, achievement_id),
                )
                record = cursor.fetchone()
                if record:
                    db_completed_at = record["completed_at"]
                    final_completed_at = (
                        db_completed_at if db_completed_at else completed_at
                    )
                    cursor.execute(
                        "UPDATE user_achievement_progress SET current_progress = %s, completed_at = %s WHERE user_id = %s AND achievement_id = %s",
                        (progress, final_completed_at, user_id, achievement_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO user_achievement_progress (user_id, achievement_id, current_progress, completed_at) VALUES (%s, %s, %s, %s)",
                        (user_id, achievement_id, progress, completed_at),
                    )
            conn.commit()

    def grant_title_to_user(self, user_id: str, title_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT IGNORE INTO user_titles (user_id, title_id, unlocked_at) VALUES (%s, %s, %s)",
                    (user_id, title_id, datetime.now()),
                )
            conn.commit()

    def revoke_title_from_user(self, user_id: str, title_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_titles WHERE user_id = %s AND title_id = %s",
                    (user_id, title_id),
                )
            conn.commit()

    def get_user_unique_fish_count(self, user_id: str) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(DISTINCT fish_id) AS cnt FROM user_fish_inventory WHERE user_id = %s",
                    (user_id,),
                )
                result = cursor.fetchone() or {}
                return int(result.get("cnt", 0))

    def get_user_garbage_count(self, user_id: str) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT SUM(ufi.quantity) AS total FROM user_fish_inventory ufi
                    JOIN fish f ON ufi.fish_id = f.fish_id
                    WHERE ufi.user_id = %s AND f.rarity = 1 AND f.base_value <= 2
                    """,
                    (user_id,),
                )
                result = cursor.fetchone() or {}
                return int(result.get("total") or 0)

    def has_caught_heavy_fish(self, user_id: str, weight: int) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM fishing_records WHERE user_id = %s AND weight >= %s LIMIT 1",
                    (user_id, weight),
                )
                return cursor.fetchone() is not None

    def has_wipe_bomb_multiplier(self, user_id: str, multiplier: float) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM wipe_bomb_log WHERE user_id = %s AND reward_multiplier >= %s LIMIT 1",
                    (user_id, multiplier),
                )
                return cursor.fetchone() is not None

    def has_item_of_rarity(self, user_id: str, item_type: str, rarity: int) -> bool:
        query = ""
        if item_type == "rod":
            query = "SELECT 1 AS present FROM user_rods ur JOIN rods r ON ur.rod_id = r.rod_id WHERE ur.user_id = %s AND r.rarity = %s LIMIT 1"
        elif item_type == "accessory":
            query = "SELECT 1 AS present FROM user_accessories ua JOIN accessories a ON ua.accessory_id = a.accessory_id WHERE ua.user_id = %s AND a.rarity = %s LIMIT 1"
        else:
            return False
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (user_id, rarity))
                return cursor.fetchone() is not None

    def get_user_caught_fish_names(self, user_id: str) -> Set[str]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT f.name FROM user_fish_inventory ufi
                    JOIN fish f ON ufi.fish_id = f.fish_id
                    WHERE ufi.user_id = %s
                    """,
                    (user_id,),
                )
                return {row["name"] for row in cursor.fetchall()}
