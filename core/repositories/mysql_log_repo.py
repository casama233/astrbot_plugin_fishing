from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import (
    FishingRecord,
    GachaRecord,
    TaxRecord,
    UserFishStat,
    WipeBombLog,
)
from .abstract_repository import AbstractLogRepository


class MysqlLogRepository(AbstractLogRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)
        self.UTC8 = timezone(timedelta(hours=8))

    def _row_to_fishing_record(self, row) -> Optional[FishingRecord]:
        if not row:
            return None
        data = dict(row)
        data["is_king_size"] = bool(data.get("is_king_size", 0))
        return FishingRecord(**data)

    def _row_to_user_fish_stat(self, row) -> Optional[UserFishStat]:
        return UserFishStat(**dict(row)) if row else None

    def _row_to_gacha_record(self, row) -> Optional[GachaRecord]:
        return GachaRecord(**dict(row)) if row else None

    def _row_to_wipe_bomb_log(self, row) -> Optional[WipeBombLog]:
        return WipeBombLog(**dict(row)) if row else None

    def _row_to_tax_record(self, row) -> Optional[TaxRecord]:
        return TaxRecord(**dict(row)) if row else None

    def add_fishing_record(self, record: FishingRecord) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO fishing_records (
                        user_id, fish_id, weight, value, rod_instance_id,
                        accessory_instance_id, bait_id, timestamp, is_king_size
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.user_id,
                        record.fish_id,
                        record.weight,
                        record.value,
                        record.rod_instance_id,
                        record.accessory_instance_id,
                        record.bait_id,
                        record.timestamp or datetime.now(self.UTC8),
                        1 if record.is_king_size else 0,
                    ),
                )
                now_ts = record.timestamp or datetime.now(self.UTC8)
                cursor.execute(
                    """
                    INSERT INTO user_fish_stats (
                        user_id, fish_id, first_caught_at, last_caught_at, max_weight, min_weight, total_caught, total_weight
                    ) VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        last_caught_at = VALUES(last_caught_at),
                        max_weight = GREATEST(max_weight, VALUES(max_weight)),
                        min_weight = LEAST(min_weight, VALUES(min_weight)),
                        total_caught = total_caught + 1,
                        total_weight = total_weight + VALUES(total_weight)
                    """,
                    (
                        record.user_id,
                        record.fish_id,
                        now_ts,
                        now_ts,
                        record.weight,
                        record.weight,
                        record.weight,
                    ),
                )
                cursor.execute(
                    """
                    DELETE fr FROM fishing_records fr
                    JOIN (
                        SELECT record_id FROM (
                            SELECT record_id FROM fishing_records
                            WHERE user_id = %s
                            ORDER BY timestamp DESC, record_id DESC
                            LIMIT 18446744073709551615 OFFSET 50
                        ) extra
                    ) stale ON fr.record_id = stale.record_id
                    """,
                    (record.user_id,),
                )
                cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
                cursor.execute(
                    "DELETE FROM fishing_records WHERE timestamp < %s", (cutoff_time,)
                )
            conn.commit()
            return True

    def get_unlocked_fish_ids(self, user_id: str) -> Dict[int, datetime]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT fish_id, MIN(timestamp) AS first_caught_time
                    FROM fishing_records
                    WHERE user_id = %s
                    GROUP BY fish_id
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                return {row["fish_id"]: row["first_caught_time"] for row in rows}

    def get_fishing_records(self, user_id: str, limit: int) -> List[FishingRecord]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fishing_records WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
        return [
            fr
            for row in cursor.fetchall()
            if row and (fr := self._row_to_fishing_record(row)) is not None
        ]

    def add_gacha_record(self, record: GachaRecord) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO gacha_records (
                        user_id, gacha_pool_id, item_type, item_id,
                        item_name, quantity, rarity, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.user_id,
                        record.gacha_pool_id,
                        record.item_type,
                        record.item_id,
                        record.item_name,
                        record.quantity,
                        record.rarity,
                        record.timestamp or datetime.now(self.UTC8),
                    ),
                )
                cursor.execute(
                    """
                    DELETE gr FROM gacha_records gr
                    JOIN (
                        SELECT record_id FROM (
                            SELECT record_id FROM gacha_records
                            WHERE user_id = %s
                            ORDER BY timestamp DESC, record_id DESC
                            LIMIT 18446744073709551615 OFFSET 50
                        ) extra
                    ) stale ON gr.record_id = stale.record_id
                    """,
                    (record.user_id,),
                )
                cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
                cursor.execute(
                    "DELETE FROM gacha_records WHERE timestamp < %s", (cutoff_time,)
                )
            conn.commit()

    def get_gacha_records(self, user_id: str, limit: int) -> List[GachaRecord]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM gacha_records WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
                return [
                    self._row_to_gacha_record(row) for row in cursor.fetchall() if row
                ]

    def add_wipe_bomb_log(self, log: WipeBombLog) -> None:
        timestamp = log.timestamp or datetime.now(self.UTC8)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=self.UTC8)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO wipe_bomb_log
                    (user_id, contribution_amount, reward_multiplier, reward_amount, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        log.user_id,
                        log.contribution_amount,
                        log.reward_multiplier,
                        log.reward_amount,
                        timestamp,
                    ),
                )
                cursor.execute(
                    """
                    DELETE wb FROM wipe_bomb_log wb
                    JOIN (
                        SELECT log_id FROM (
                            SELECT log_id FROM wipe_bomb_log
                            WHERE user_id = %s
                            ORDER BY timestamp DESC, log_id DESC
                            LIMIT 18446744073709551615 OFFSET 50
                        ) extra
                    ) stale ON wb.log_id = stale.log_id
                    """,
                    (log.user_id,),
                )
                cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
                cursor.execute(
                    "DELETE FROM wipe_bomb_log WHERE timestamp < %s", (cutoff_time,)
                )
            conn.commit()

    def get_wipe_bomb_log_count_today(self, user_id: str) -> int:
        today_start = datetime.now(self.UTC8).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = today_start + timedelta(days=1)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM wipe_bomb_log
                    WHERE user_id = %s AND timestamp >= %s AND timestamp < %s
                      AND contribution_amount > 0
                    """,
                    (user_id, today_start, today_end),
                )
                result = cursor.fetchone() or {}
                return int(result.get("cnt", 0))

    def add_check_in(self, user_id: str, check_in_date: date) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT IGNORE INTO check_ins (user_id, check_in_date) VALUES (%s, %s)",
                    (user_id, check_in_date),
                )
                cursor.execute(
                    """
                    DELETE ci FROM check_ins ci
                    JOIN (
                        SELECT user_id, check_in_date FROM (
                            SELECT user_id, check_in_date
                            FROM check_ins
                            WHERE user_id = %s
                            ORDER BY check_in_date DESC
                            LIMIT 18446744073709551615 OFFSET 50
                        ) extra
                    ) stale ON ci.user_id = stale.user_id AND ci.check_in_date = stale.check_in_date
                    """,
                    (user_id,),
                )
                cutoff_date = (datetime.now(self.UTC8) - timedelta(days=30)).date()
                cursor.execute(
                    "DELETE FROM check_ins WHERE check_in_date < %s", (cutoff_date,)
                )
            conn.commit()

    def has_checked_in(self, user_id: str, check_in_date: date) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM check_ins WHERE user_id = %s AND check_in_date = %s",
                    (user_id, check_in_date),
                )
                return cursor.fetchone() is not None

    def add_tax_record(self, record: TaxRecord) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO taxes
                        (user_id, tax_amount, tax_rate, original_amount, balance_after, tax_type, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.user_id,
                        record.tax_amount,
                        record.tax_rate,
                        record.original_amount,
                        record.balance_after,
                        record.tax_type,
                        record.timestamp or datetime.now(self.UTC8),
                    ),
                )
                cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
                cursor.execute(
                    """
                    DELETE t FROM taxes t
                    LEFT JOIN (
                        SELECT tax_id FROM taxes
                        WHERE user_id = %s AND tax_type = '每日资产税' AND timestamp >= %s
                        UNION
                        SELECT tax_id FROM (
                            SELECT tax_id FROM taxes
                            WHERE user_id = %s AND tax_type != '每日资产税'
                            ORDER BY timestamp DESC, tax_id DESC
                            LIMIT 50
                        ) keep_other
                    ) keep_ids ON t.tax_id = keep_ids.tax_id
                    WHERE t.user_id = %s AND keep_ids.tax_id IS NULL
                    """,
                    (record.user_id, cutoff_time, record.user_id, record.user_id),
                )
                cursor.execute("DELETE FROM taxes WHERE timestamp < %s", (cutoff_time,))
            conn.commit()

    def get_wipe_bomb_logs(self, user_id: str, limit: int = 10) -> List[WipeBombLog]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM wipe_bomb_log WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
                return [
                    self._row_to_wipe_bomb_log(row) for row in cursor.fetchall() if row
                ]

    def get_tax_records(self, user_id: str, limit: int = 10) -> List[TaxRecord]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM taxes WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (user_id, limit),
                )
                return [
                    self._row_to_tax_record(row) for row in cursor.fetchall() if row
                ]

    def has_user_daily_tax_today(self, user_id: str, reset_hour: int = 0) -> bool:
        from ..utils import get_last_reset_time

        last_reset = get_last_reset_time(reset_hour)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM taxes
                    WHERE user_id = %s AND tax_type = '每日资产税' AND timestamp >= %s
                    """,
                    (user_id, last_reset),
                )
                result = cursor.fetchone() or {}
                return int(result.get("cnt", 0)) > 0

    def get_max_wipe_bomb_multiplier(self, user_id: str) -> float:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(reward_multiplier) AS max_value FROM wipe_bomb_log WHERE user_id = %s",
                    (user_id,),
                )
                result = cursor.fetchone() or {}
                value = result.get("max_value")
                return float(value) if value is not None else 0.0

    def get_min_wipe_bomb_multiplier(self, user_id: str) -> Optional[float]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MIN(reward_multiplier) AS min_value FROM wipe_bomb_log WHERE user_id = %s",
                    (user_id,),
                )
                result = cursor.fetchone() or {}
                value = result.get("min_value")
                return float(value) if value is not None else None

    def get_gacha_records_count_today(self, user_id: str, gacha_pool_id: int) -> int:
        today_start_utc8 = datetime.now(self.UTC8).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end_utc8 = today_start_utc8 + timedelta(days=1)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM gacha_records
                    WHERE user_id = %s AND gacha_pool_id = %s AND timestamp >= %s AND timestamp < %s
                    """,
                    (user_id, gacha_pool_id, today_start_utc8, today_end_utc8),
                )
                result = cursor.fetchone() or {}
                return int(result.get("cnt", 0))

    def add_log(self, user_id: str, log_type: str, message: str) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO wipe_bomb_log (user_id, contribution_amount, reward_multiplier, reward_amount, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, 0, 0.0, 0, datetime.now()),
                )
            conn.commit()

    def get_user_fish_stats(self, user_id: str) -> List[UserFishStat]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, fish_id, first_caught_at, last_caught_at,
                           max_weight, min_weight, total_caught, total_weight
                    FROM user_fish_stats
                    WHERE user_id = %s
                    ORDER BY last_caught_at DESC
                    """,
                    (user_id,),
                )
                return [
                    self._row_to_user_fish_stat(row) for row in cursor.fetchall() if row
                ]

    def get_user_fish_stat(self, user_id: str, fish_id: int) -> Optional[UserFishStat]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, fish_id, first_caught_at, last_caught_at,
                           max_weight, min_weight, total_caught, total_weight
                    FROM user_fish_stats
                    WHERE user_id = %s AND fish_id = %s
                    LIMIT 1
                    """,
                    (user_id, fish_id),
                )
                row = cursor.fetchone()
                return self._row_to_user_fish_stat(row) if row else None
