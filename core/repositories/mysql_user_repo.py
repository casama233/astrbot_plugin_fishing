from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import List, Optional

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import User
from .abstract_repository import AbstractUserRepository


class MysqlUserRepository(AbstractUserRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _parse_datetime(self, dt_val):
        if isinstance(dt_val, datetime):
            return dt_val
        if isinstance(dt_val, str):
            try:
                return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(dt_val, fmt)
                    except ValueError:
                        pass
        return None

    def _row_to_user(self, row) -> Optional[User]:
        if not row:
            return None
        row_keys = row.keys()
        return User(
            user_id=row["user_id"],
            nickname=row["nickname"],
            coins=row["coins"],
            premium_currency=row["premium_currency"],
            total_fishing_count=row["total_fishing_count"],
            total_weight_caught=row["total_weight_caught"],
            total_coins_earned=row["total_coins_earned"],
            max_coins=row["max_coins"] if "max_coins" in row_keys else 0,
            consecutive_login_days=row["consecutive_login_days"],
            fish_pond_capacity=row["fish_pond_capacity"],
            aquarium_capacity=row["aquarium_capacity"]
            if "aquarium_capacity" in row_keys
            else 50,
            created_at=self._parse_datetime(row["created_at"]),
            equipped_rod_instance_id=row["equipped_rod_instance_id"],
            equipped_accessory_instance_id=row["equipped_accessory_instance_id"],
            current_title_id=row["current_title_id"],
            current_bait_id=row["current_bait_id"],
            bait_start_time=self._parse_datetime(row["bait_start_time"]),
            max_wipe_bomb_multiplier=row["max_wipe_bomb_multiplier"]
            if "max_wipe_bomb_multiplier" in row_keys
            else 0.0,
            min_wipe_bomb_multiplier=row["min_wipe_bomb_multiplier"]
            if "min_wipe_bomb_multiplier" in row_keys
            else None,
            auto_fishing_enabled=bool(row["auto_fishing_enabled"]),
            last_fishing_time=self._parse_datetime(row["last_fishing_time"]),
            last_wipe_bomb_time=self._parse_datetime(row["last_wipe_bomb_time"]),
            last_steal_time=self._parse_datetime(row["last_steal_time"]),
            last_electric_fish_time=self._parse_datetime(row["last_electric_fish_time"])
            if "last_electric_fish_time" in row_keys
            else None,
            last_login_time=self._parse_datetime(row["last_login_time"]),
            last_stolen_at=self._parse_datetime(row["last_stolen_at"]),
            wipe_bomb_forecast=row["wipe_bomb_forecast"],
            fishing_zone_id=row["fishing_zone_id"],
            wipe_bomb_attempts_today=row["wipe_bomb_attempts_today"]
            if "wipe_bomb_attempts_today" in row_keys
            else 0,
            last_wipe_bomb_date=row["last_wipe_bomb_date"]
            if "last_wipe_bomb_date" in row_keys
            else None,
            in_wheel_of_fate=bool(row["in_wheel_of_fate"])
            if "in_wheel_of_fate" in row_keys
            else False,
            wof_current_level=row["wof_current_level"]
            if "wof_current_level" in row_keys
            else 0,
            wof_current_prize=row["wof_current_prize"]
            if "wof_current_prize" in row_keys
            else 0,
            wof_entry_fee=row["wof_entry_fee"] if "wof_entry_fee" in row_keys else 0,
            last_wof_play_time=self._parse_datetime(row["last_wof_play_time"])
            if "last_wof_play_time" in row_keys
            else None,
            wof_last_action_time=self._parse_datetime(row["wof_last_action_time"])
            if "wof_last_action_time" in row_keys
            else None,
            wof_plays_today=row["wof_plays_today"]
            if "wof_plays_today" in row_keys
            else 0,
            last_wof_date=row["last_wof_date"] if "last_wof_date" in row_keys else None,
            last_sicbo_time=self._parse_datetime(row["last_sicbo_time"])
            if "last_sicbo_time" in row_keys
            else None,
            exchange_account_status=bool(row["exchange_account_status"])
            if "exchange_account_status" in row_keys
            else False,
            show_suggestions=bool(row["show_suggestions"])
            if "show_suggestions" in row_keys
            else True,
            zone_pass_expires_at=self._parse_datetime(row["zone_pass_expires_at"])
            if "zone_pass_expires_at" in row_keys
            else None,
        )

    def get_by_id(self, user_id: str) -> Optional[User]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                return self._row_to_user(cursor.fetchone())

    def check_exists(self, user_id: str) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM users WHERE user_id = %s", (user_id,)
                )
                return cursor.fetchone() is not None

    def add(self, user: User) -> None:
        fields = [f.name for f in dataclasses.fields(User)]
        columns_clause = ", ".join(fields)
        placeholders_clause = ", ".join(["%s"] * len(fields))
        values = [getattr(user, field) for field in fields]
        update_fields = [f for f in fields if f != "user_id"]
        update_clause = ", ".join([f"{f} = %s" for f in update_fields])
        sql = f"INSERT INTO users ({columns_clause}) VALUES ({placeholders_clause}) ON DUPLICATE KEY UPDATE {update_clause}"
        update_values = [getattr(user, f) for f in update_fields]
        all_values = tuple(values + update_values)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, all_values)
                conn.commit()

    def update(self, user: User) -> None:
        if user.coins > user.max_coins:
            user.max_coins = user.coins
        fields = [f.name for f in dataclasses.fields(User) if f.name != "user_id"]
        set_clause = ", ".join([f"{field} = %s" for field in fields])
        values = [getattr(user, field) for field in fields]
        values.append(user.user_id)
        sql = f"UPDATE users SET {set_clause} WHERE user_id = %s"
        if "show_suggestions" in fields:
            logger.debug(
                f"更新用戶 {user.user_id} 的 show_suggestions 為: {getattr(user, 'show_suggestions')}"
            )
        try:
            with self._connection_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, tuple(values))
                    if cursor.rowcount == 0:
                        logger.warning(
                            f"尝试更新不存在的用户 {user.user_id}，将转为添加操作。"
                        )
                        conn.rollback()
                        self.add(user)
                    else:
                        conn.commit()
        except Exception as exc:
            logger.error(f"更新用户 {user.user_id} 数据时发生数据库错误: {exc}")
            raise

    def get_all_user_ids(self, auto_fishing_only: bool = False) -> List[str]:
        query = "SELECT user_id FROM users"
        params = []
        if auto_fishing_only:
            query += " WHERE auto_fishing_enabled = 1"
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return [row["user_id"] for row in cursor.fetchall()]

    def _get_top_users_base_query(self, order_by_column: str, limit: int) -> List[User]:
        if order_by_column not in [
            "total_fishing_count",
            "coins",
            "total_weight_caught",
            "max_coins",
        ]:
            raise ValueError("Invalid order by column")
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM users ORDER BY {order_by_column} DESC LIMIT %s",
                    (limit,),
                )
                return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_top_users_by_fish_count(self, limit: int) -> List[User]:
        return self._get_top_users_base_query("total_fishing_count", limit)

    def get_top_users_by_coins(self, limit: int) -> List[User]:
        return self._get_top_users_base_query("coins", limit)

    def get_top_users_by_max_coins(self, limit: int) -> List[User]:
        return self._get_top_users_base_query("max_coins", limit)

    def get_top_users_by_weight(self, limit: int) -> List[User]:
        return self._get_top_users_base_query("total_weight_caught", limit)

    def get_high_value_users(self, threshold: int) -> List[User]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE coins >= %s", (threshold,))
                return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_users_count(self) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS cnt FROM users")
                return int((cursor.fetchone() or {}).get("cnt", 0))

    def search_users(
        self, keyword: str, limit: int = 50, offset: int = 0
    ) -> List[User]:
        like = f"%{keyword}%"
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM users
                    WHERE user_id LIKE %s OR nickname LIKE %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (like, like, limit, offset),
                )
                return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_search_users_count(self, keyword: str) -> int:
        like = f"%{keyword}%"
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE user_id LIKE %s OR nickname LIKE %s",
                    (like, like),
                )
                return int((cursor.fetchone() or {}).get("cnt", 0))

    def delete_user(self, user_id: str) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                deleted = cursor.rowcount > 0
            conn.commit()
        return deleted
