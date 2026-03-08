from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from .abstract_repository import AbstractShopRepository


class MysqlShopRepository(AbstractShopRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _normalize_row(self, row) -> Dict[str, Any]:
        if not row:
            return {}
        data = dict(row)
        for key in ("is_active",):
            if key in data and isinstance(data[key], int):
                data[key] = bool(data[key])
        for key in ("created_at", "updated_at", "timestamp"):
            if key in data and data[key] and isinstance(data[key], str):
                try:
                    data[key] = datetime.fromisoformat(data[key].replace("Z", "+00:00"))
                except Exception:
                    pass
        for key in ("start_time", "end_time"):
            if key in data and data[key] and hasattr(data[key], "strftime"):
                data[key] = data[key].strftime("%Y-%m-%d %H:%M:%S")
        for key in ("daily_start_time", "daily_end_time"):
            if key in data and data[key]:
                if isinstance(data[key], str) and data[key].count(":") == 2:
                    data[key] = data[key][:5]
                elif hasattr(data[key], "strftime"):
                    data[key] = data[key].strftime("%H:%M")
                else:
                    data[key] = str(data[key])
        return data

    def get_active_shops(self, shop_type: Optional[str] = None) -> List[Dict[str, Any]]:
        where = ["is_active = 1"]
        params: List[Any] = []
        now = datetime.now().isoformat(sep=" ")
        where.append("(start_time IS NULL OR start_time <= %s)")
        where.append("(end_time IS NULL OR end_time >= %s)")
        params.extend([now, now])
        current_time = datetime.now().time().strftime("%H:%M")
        where.append(
            "(daily_start_time IS NULL OR daily_end_time IS NULL OR (daily_start_time <= daily_end_time AND daily_start_time <= %s AND daily_end_time >= %s) OR (daily_start_time > daily_end_time AND (daily_start_time <= %s OR daily_end_time >= %s)))"
        )
        params.extend([current_time, current_time, current_time, current_time])
        if shop_type:
            where.append("shop_type = %s")
            params.append(shop_type)
        sql = f"SELECT * FROM shops WHERE {' AND '.join(where)} ORDER BY sort_order ASC, shop_id ASC"
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def get_all_shops(self) -> List[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM shops ORDER BY sort_order ASC, shop_id ASC"
                )
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def get_shop_by_id(self, shop_id: int) -> Optional[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM shops WHERE shop_id = %s", (shop_id,))
                row = cursor.fetchone()
                return self._normalize_row(row) if row else None

    def create_shop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shops (
                        name, description, shop_type, is_active,
                        start_time, end_time, daily_start_time, daily_end_time, sort_order
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data["name"],
                        data.get("description"),
                        data.get("shop_type", "normal"),
                        1 if data.get("is_active", True) else 0,
                        data.get("start_time"),
                        data.get("end_time"),
                        data.get("daily_start_time"),
                        data.get("daily_end_time"),
                        data.get("sort_order", 100),
                    ),
                )
                shop_id = cursor.lastrowid
            conn.commit()
        return self.get_shop_by_id(shop_id)

    def update_shop(self, shop_id: int, data: Dict[str, Any]) -> None:
        fields = []
        params: List[Any] = []
        for key in [
            "name",
            "description",
            "shop_type",
            "is_active",
            "start_time",
            "end_time",
            "daily_start_time",
            "daily_end_time",
            "sort_order",
        ]:
            if key in data:
                fields.append(f"{key} = %s")
                value = data[key]
                if key == "is_active":
                    value = 1 if value else 0
                params.append(value)
        if not fields:
            return
        params.append(shop_id)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE shops SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE shop_id = %s",
                    tuple(params),
                )
            conn.commit()

    def delete_shop(self, shop_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM shops WHERE shop_id = %s", (shop_id,))
            conn.commit()

    def get_shop_items(self, shop_id: int) -> List[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM shop_items WHERE shop_id = %s ORDER BY sort_order ASC, item_id ASC",
                    (shop_id,),
                )
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def get_shop_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM shop_items WHERE item_id = %s", (item_id,)
                )
                row = cursor.fetchone()
                return self._normalize_row(row) if row else None

    def create_shop_item(
        self, shop_id: int, item_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shop_items (
                        shop_id, name, description, category,
                        stock_total, stock_sold, per_user_limit, per_user_daily_limit,
                        is_active, start_time, end_time, sort_order
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        shop_id,
                        item_data["name"],
                        item_data.get("description"),
                        item_data.get("category", "general"),
                        item_data.get("stock_total"),
                        item_data.get("stock_sold", 0),
                        item_data.get("per_user_limit"),
                        item_data.get("per_user_daily_limit"),
                        1 if item_data.get("is_active", True) else 0,
                        item_data.get("start_time"),
                        item_data.get("end_time"),
                        item_data.get("sort_order", 100),
                    ),
                )
                item_id = cursor.lastrowid
            conn.commit()
        return self.get_shop_item_by_id(item_id)

    def update_shop_item(self, item_id: int, data: Dict[str, Any]) -> None:
        fields = []
        params: List[Any] = []
        for key in [
            "name",
            "description",
            "category",
            "is_active",
            "start_time",
            "end_time",
            "stock_total",
            "stock_sold",
            "per_user_limit",
            "per_user_daily_limit",
            "sort_order",
        ]:
            if key in data:
                fields.append(f"{key} = %s")
                value = data[key]
                if key == "is_active":
                    value = 1 if value else 0
                params.append(value)
        if not fields:
            return
        params.append(item_id)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE shop_items SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE item_id = %s",
                    tuple(params),
                )
            conn.commit()

    def delete_shop_item(self, item_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM shop_items WHERE item_id = %s", (item_id,))
            conn.commit()

    def increase_item_sold(self, item_id: int, delta: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE shop_items SET stock_sold = COALESCE(stock_sold, 0) + %s, updated_at = CURRENT_TIMESTAMP WHERE item_id = %s",
                    (delta, item_id),
                )
            conn.commit()

    def get_item_costs(self, item_id: int) -> List[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT *, quality_level FROM shop_item_costs WHERE item_id = %s ORDER BY group_id ASC, cost_id ASC",
                    (item_id,),
                )
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def add_item_cost(self, item_id: int, cost_data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shop_item_costs (
                        item_id, cost_type, cost_amount, cost_item_id,
                        cost_relation, group_id, quality_level
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item_id,
                        cost_data["cost_type"],
                        cost_data["cost_amount"],
                        cost_data.get("cost_item_id"),
                        cost_data.get("cost_relation", "and"),
                        cost_data.get("group_id"),
                        cost_data.get("quality_level", 0),
                    ),
                )
            conn.commit()

    def update_item_cost(self, cost_id: int, data: Dict[str, Any]) -> None:
        fields = []
        params: List[Any] = []
        for key in [
            "cost_type",
            "cost_amount",
            "cost_item_id",
            "cost_relation",
            "group_id",
            "quality_level",
        ]:
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data[key])
        if not fields:
            return
        params.append(cost_id)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE shop_item_costs SET {', '.join(fields)} WHERE cost_id = %s",
                    tuple(params),
                )
            conn.commit()

    def delete_item_cost(self, cost_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM shop_item_costs WHERE cost_id = %s", (cost_id,)
                )
            conn.commit()

    def get_item_rewards(self, item_id: int) -> List[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT *, quality_level FROM shop_item_rewards WHERE item_id = %s ORDER BY reward_id ASC",
                    (item_id,),
                )
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def add_item_reward(self, item_id: int, reward_data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shop_item_rewards (
                        item_id, reward_type, reward_item_id, reward_quantity, reward_refine_level, quality_level
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item_id,
                        reward_data["reward_type"],
                        reward_data.get("reward_item_id"),
                        reward_data.get("reward_quantity", 1),
                        reward_data.get("reward_refine_level"),
                        reward_data.get("quality_level", 0),
                    ),
                )
            conn.commit()

    def update_item_reward(self, reward_id: int, data: Dict[str, Any]) -> None:
        fields = []
        params: List[Any] = []
        for key in [
            "reward_type",
            "reward_item_id",
            "reward_quantity",
            "reward_refine_level",
            "quality_level",
        ]:
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data[key])
        if not fields:
            return
        params.append(reward_id)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE shop_item_rewards SET {', '.join(fields)} WHERE reward_id = %s",
                    tuple(params),
                )
            conn.commit()

    def delete_item_reward(self, reward_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM shop_item_rewards WHERE reward_id = %s", (reward_id,)
                )
            conn.commit()

    def add_purchase_record(self, user_id: str, item_id: int, quantity: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO shop_purchase_records (user_id, item_id, quantity) VALUES (%s, %s, %s)",
                    (user_id, item_id, quantity),
                )
            conn.commit()

    def get_user_purchased_count(
        self, user_id: str, item_id: int, since: Optional[datetime] = None
    ) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if since is None:
                    cursor.execute(
                        "SELECT COALESCE(SUM(quantity), 0) AS total FROM shop_purchase_records WHERE user_id = %s AND item_id = %s",
                        (user_id, item_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COALESCE(SUM(quantity), 0) AS total
                        FROM shop_purchase_records
                        WHERE user_id = %s AND item_id = %s AND timestamp >= %s
                        """,
                        (user_id, item_id, since),
                    )
                row = cursor.fetchone() or {}
                return int(row.get("total", 0) or 0)

    def get_user_purchase_history(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT spr.*, si.name AS item_name, s.name AS shop_name
                    FROM shop_purchase_records spr
                    JOIN shop_items si ON spr.item_id = si.item_id
                    JOIN shops s ON si.shop_id = s.shop_id
                    WHERE spr.user_id = %s
                    ORDER BY spr.timestamp DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def get_active_offers(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        where = ["si.is_active = 1"]
        params: List[Any] = []
        now = datetime.now().isoformat(sep=" ")
        where.append("(si.start_time IS NULL OR si.start_time <= %s)")
        where.append("(si.end_time IS NULL OR si.end_time >= %s)")
        params.extend([now, now])
        if category:
            where.append("si.category = %s")
            params.append(category)
        sql = f"""
        SELECT si.*, s.name AS shop_name, s.shop_type
        FROM shop_items si
        JOIN shops s ON si.shop_id = s.shop_id
        WHERE {" AND ".join(where)}
        ORDER BY si.sort_order ASC, si.item_id ASC
        """
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return [self._normalize_row(r) for r in cursor.fetchall()]

    def get_offer_by_id(self, offer_id: int) -> Optional[Dict[str, Any]]:
        return self.get_shop_item_by_id(offer_id)
