from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import GachaPool, GachaPoolItem
from .abstract_repository import AbstractGachaRepository


class MysqlGachaRepository(AbstractGachaRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _row_to_gacha_pool(self, row) -> Optional[GachaPool]:
        if not row:
            return None
        return GachaPool(**row)

    def _row_to_gacha_pool_item(self, row) -> Optional[GachaPoolItem]:
        if not row:
            return None
        return GachaPoolItem(**row)

    def get_pool_by_id(self, pool_id: int) -> Optional[GachaPool]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM gacha_pools WHERE gacha_pool_id = %s", (pool_id,)
                )
                pool_row = cursor.fetchone()
                if not pool_row:
                    return None
                pool = self._row_to_gacha_pool(pool_row)
                pool.items = self.get_pool_items(pool_id)
                return pool

    def get_pool_items(self, pool_id: int) -> List[GachaPoolItem]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT gacha_pool_item_id, gacha_pool_id, item_type, item_id, weight, quantity
                    FROM gacha_pool_items
                    WHERE gacha_pool_id = %s
                    """,
                    (pool_id,),
                )
                return [self._row_to_gacha_pool_item(row) for row in cursor.fetchall()]

    def get_all_pools(self) -> List[GachaPool]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM gacha_pools ORDER BY gacha_pool_id")
                rows = cursor.fetchall()
        pools = []
        for row in rows:
            pool = self._row_to_gacha_pool(row)
            if pool:
                pool.items = self.get_pool_items(pool.gacha_pool_id)
                pools.append(pool)
        return pools

    def get_free_pools(self) -> List[GachaPool]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM gacha_pools WHERE cost_coins = 0 AND cost_premium_currency = 0"
                )
                return [self._row_to_gacha_pool(row) for row in cursor.fetchall()]

    def add_pool_template(self, data: Dict[str, Any]) -> GachaPool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO gacha_pools (name, description, cost_coins, cost_premium_currency, is_limited_time, open_until)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("cost_coins", 0),
                        data.get("cost_premium_currency", 0),
                        1 if data.get("is_limited_time") in (True, "1", 1, "on") else 0,
                        data.get("open_until"),
                    ),
                )
                pool_id = cursor.lastrowid
            conn.commit()
        return self.get_pool_by_id(pool_id)

    def update_pool_template(self, pool_id: int, data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE gacha_pools SET
                        name = %s,
                        description = %s,
                        cost_coins = %s,
                        cost_premium_currency = %s,
                        is_limited_time = %s,
                        open_until = %s
                    WHERE gacha_pool_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("cost_coins", 0),
                        data.get("cost_premium_currency", 0),
                        1 if data.get("is_limited_time") in (True, "1", 1, "on") else 0,
                        data.get("open_until"),
                        pool_id,
                    ),
                )
            conn.commit()

    def delete_pool_template(self, pool_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM gacha_pools WHERE gacha_pool_id = %s", (pool_id,)
                )
            conn.commit()

    def copy_pool_template(self, pool_id: int) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM gacha_pools WHERE gacha_pool_id = %s", (pool_id,)
                )
                original_pool = cursor.fetchone()
                if not original_pool:
                    raise ValueError(f"Pool with ID {pool_id} not found")

                cursor.execute(
                    """
                    INSERT INTO gacha_pools (name, description, cost_coins, cost_premium_currency, is_limited_time, open_until)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        f"{original_pool['name']} (副本)",
                        original_pool["description"],
                        original_pool["cost_coins"],
                        original_pool["cost_premium_currency"],
                        original_pool.get("is_limited_time", 0),
                        original_pool.get("open_until"),
                    ),
                )
                new_pool_id = cursor.lastrowid

                cursor.execute(
                    "SELECT * FROM gacha_pool_items WHERE gacha_pool_id = %s",
                    (pool_id,),
                )
                items = cursor.fetchall()
                for item in items:
                    cursor.execute(
                        """
                        INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, quantity, weight)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            new_pool_id,
                            item["item_type"],
                            item["item_id"],
                            item["quantity"],
                            item["weight"],
                        ),
                    )
            conn.commit()
        return new_pool_id

    def add_item_to_pool(self, pool_id: int, data: Dict[str, Any]) -> GachaPoolItem:
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        item_full_id = data.get("item_full_id", "")
        if (not item_type or item_id is None) and item_full_id:
            parts = item_full_id.split("-")
            if len(parts) == 2:
                item_type, item_id = parts[0], parts[1]
        if not item_type or item_id is None:
            raise ValueError("Missing item_type/item_id for gacha pool item")

        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, quantity, weight)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        pool_id,
                        item_type,
                        int(item_id),
                        data.get("quantity", 1),
                        data.get("weight", 10),
                    ),
                )
                item_pool_id = cursor.lastrowid
            conn.commit()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT gacha_pool_item_id, gacha_pool_id, item_type, item_id, weight, quantity FROM gacha_pool_items WHERE gacha_pool_item_id = %s",
                    (item_pool_id,),
                )
                row = cursor.fetchone()
                return self._row_to_gacha_pool_item(row)

    def add_pool_item(self, pool_id: int, data: Dict[str, Any]):
        return self.add_item_to_pool(pool_id, data)

    def update_pool_item(self, item_pool_id: int, data: Dict[str, Any]) -> None:
        if not data:
            return
        updates = []
        params = []
        if "item_full_id" in data and data["item_full_id"]:
            item_full_id = data["item_full_id"].split("-")
            if len(item_full_id) == 2:
                updates.extend(["item_type = %s", "item_id = %s"])
                params.extend([item_full_id[0], item_full_id[1]])
        if "quantity" in data:
            updates.append("quantity = %s")
            params.append(data["quantity"])
        if "weight" in data:
            updates.append("weight = %s")
            params.append(data["weight"])
        if not updates:
            return
        params.append(item_pool_id)
        query = f"UPDATE gacha_pool_items SET {', '.join(updates)} WHERE gacha_pool_item_id = %s"
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
            conn.commit()

    def delete_pool_item(self, item_pool_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM gacha_pool_items WHERE gacha_pool_item_id = %s",
                    (item_pool_id,),
                )
            conn.commit()
