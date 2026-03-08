from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import (
    AquariumUpgrade,
    FishingZone,
    UserAccessoryInstance,
    UserAquariumItem,
    UserFishInventoryItem,
    UserRodInstance,
)
from .abstract_repository import AbstractInventoryRepository


class InsufficientFishQuantityError(Exception):
    pass


class MysqlInventoryRepository(AbstractInventoryRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _row_to_fish_item(self, row) -> Optional[UserFishInventoryItem]:
        if not row:
            return None
        return UserFishInventoryItem(
            user_id=row["user_id"],
            fish_id=row["fish_id"],
            quality_level=row["quality_level"],
            quantity=row["quantity"],
        )

    def _row_to_aquarium_item(self, row) -> Optional[UserAquariumItem]:
        if not row:
            return None
        return UserAquariumItem(
            user_id=row["user_id"],
            fish_id=row["fish_id"],
            quality_level=row["quality_level"],
            quantity=row["quantity"],
            added_at=row.get("added_at"),
        )

    def _row_to_aquarium_upgrade(self, row) -> Optional[AquariumUpgrade]:
        return AquariumUpgrade(**row) if row else None

    def _row_to_rod_instance(self, row) -> Optional[UserRodInstance]:
        if not row:
            return None
        return UserRodInstance(
            rod_instance_id=row["rod_instance_id"],
            user_id=row["user_id"],
            rod_id=row["rod_id"],
            is_equipped=bool(row["is_equipped"]),
            obtained_at=row["obtained_at"],
            refine_level=row.get("refine_level", 1),
            current_durability=row.get("current_durability"),
            is_locked=bool(row.get("is_locked", 0)),
        )

    def _row_to_accessory_instance(self, row) -> Optional[UserAccessoryInstance]:
        if not row:
            return None
        return UserAccessoryInstance(
            accessory_instance_id=row["accessory_instance_id"],
            user_id=row["user_id"],
            accessory_id=row["accessory_id"],
            is_equipped=bool(row["is_equipped"]),
            obtained_at=row["obtained_at"],
            refine_level=row.get("refine_level", 1),
            is_locked=bool(row.get("is_locked", 0)),
        )

    def get_fish_inventory(self, user_id: str) -> List[UserFishInventoryItem]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, fish_id, quality_level, quantity FROM user_fish_inventory WHERE user_id = %s AND quantity > 0",
                    (user_id,),
                )
                return [self._row_to_fish_item(row) for row in cursor.fetchall() if row]

    def get_fish_inventory_value(
        self, user_id: str, rarity: Optional[int] = None
    ) -> int:
        query = """
            SELECT SUM(f.base_value * ufi.quantity * (1 + ufi.quality_level)) AS total_value
            FROM user_fish_inventory ufi
            JOIN fish f ON ufi.fish_id = f.fish_id
            WHERE ufi.user_id = %s
        """
        params: List[Any] = [user_id]
        if rarity is not None:
            query += " AND f.rarity = %s"
            params.append(rarity)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                result = cursor.fetchone() or {}
                return int(result.get("total_value") or 0)

    def add_fish_to_inventory(
        self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (user_id, fish_id, quality_level, quantity),
                )
            conn.commit()

    def clear_fish_inventory(self, user_id: str, rarity: Optional[int] = None) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if rarity is None:
                    cursor.execute(
                        "DELETE FROM user_fish_inventory WHERE user_id = %s", (user_id,)
                    )
                else:
                    cursor.execute(
                        """
                        DELETE ufi FROM user_fish_inventory ufi
                        JOIN fish f ON ufi.fish_id = f.fish_id
                        WHERE ufi.user_id = %s AND f.rarity = %s
                        """,
                        (user_id, rarity),
                    )
            conn.commit()

    def update_fish_quantity(
        self, user_id: str, fish_id: int, delta: int, quality_level: int = 0
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if delta >= 0:
                    cursor.execute(
                        """
                        INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = GREATEST(0, quantity + VALUES(quantity))
                        """,
                        (user_id, fish_id, quality_level, delta),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE user_fish_inventory
                        SET quantity = GREATEST(0, quantity + %s)
                        WHERE user_id = %s AND fish_id = %s AND quality_level = %s
                        """,
                        (delta, user_id, fish_id, quality_level),
                    )
                cursor.execute(
                    "DELETE FROM user_fish_inventory WHERE user_id = %s AND quantity <= 0",
                    (user_id,),
                )
            conn.commit()

    def get_aquarium_inventory(self, user_id: str) -> List[UserAquariumItem]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, fish_id, quality_level, quantity, added_at FROM user_aquarium WHERE user_id = %s AND quantity > 0",
                    (user_id,),
                )
                return [
                    self._row_to_aquarium_item(row) for row in cursor.fetchall() if row
                ]

    def get_aquarium_inventory_value(
        self, user_id: str, rarity: Optional[int] = None
    ) -> int:
        query = """
            SELECT SUM(f.base_value * ua.quantity * (1 + ua.quality_level)) AS total_value
            FROM user_aquarium ua
            JOIN fish f ON ua.fish_id = f.fish_id
            WHERE ua.user_id = %s
        """
        params: List[Any] = [user_id]
        if rarity is not None:
            query += " AND f.rarity = %s"
            params.append(rarity)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                result = cursor.fetchone() or {}
                return int(result.get("total_value") or 0)

    def add_fish_to_aquarium(
        self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_aquarium (user_id, fish_id, quality_level, quantity, added_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (user_id, fish_id, quality_level, quantity),
                )
            conn.commit()

    def remove_fish_from_aquarium(
        self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_aquarium
                    SET quantity = quantity - %s
                    WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity >= %s
                    """,
                    (quantity, user_id, fish_id, quality_level, quantity),
                )
                if cursor.rowcount == 0:
                    raise InsufficientFishQuantityError(
                        f"用户 {user_id} 水族箱中没有足够的鱼类 {fish_id}（品质等级 {quality_level}）来移除 {quantity} 个"
                    )
                cursor.execute(
                    "DELETE FROM user_aquarium WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity <= 0",
                    (user_id, fish_id, quality_level),
                )
            conn.commit()

    def update_aquarium_fish_quantity(
        self, user_id: str, fish_id: int, delta: int, quality_level: int = 0
    ) -> None:
        if delta > 0:
            self.add_fish_to_aquarium(user_id, fish_id, delta, quality_level)
        elif delta < 0:
            self.remove_fish_from_aquarium(user_id, fish_id, -delta, quality_level)

    def clear_aquarium_inventory(
        self, user_id: str, rarity: Optional[int] = None
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if rarity is None:
                    cursor.execute(
                        "DELETE FROM user_aquarium WHERE user_id = %s", (user_id,)
                    )
                else:
                    cursor.execute(
                        """
                        DELETE ua FROM user_aquarium ua
                        JOIN fish f ON ua.fish_id = f.fish_id
                        WHERE ua.user_id = %s AND f.rarity = %s
                        """,
                        (user_id, rarity),
                    )
            conn.commit()

    def get_aquarium_total_count(self, user_id: str) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT SUM(quantity) AS total FROM user_aquarium WHERE user_id = %s",
                    (user_id,),
                )
                result = cursor.fetchone() or {}
                return int(result.get("total") or 0)

    def get_user_total_fish_count(self, user_id: str, fish_id: int) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COALESCE(SUM(quantity), 0) AS total FROM user_fish_inventory WHERE user_id = %s AND fish_id = %s",
                    (user_id, fish_id),
                )
                pond_count = int((cursor.fetchone() or {}).get("total") or 0)
                cursor.execute(
                    "SELECT COALESCE(SUM(quantity), 0) AS total FROM user_aquarium WHERE user_id = %s AND fish_id = %s",
                    (user_id, fish_id),
                )
                aquarium_count = int((cursor.fetchone() or {}).get("total") or 0)
                return pond_count + aquarium_count

    def deduct_fish_smart(
        self, user_id: str, fish_id: int, quantity: int, quality_level: int = 0
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT quantity FROM user_fish_inventory WHERE user_id = %s AND fish_id = %s AND quality_level = %s",
                    (user_id, fish_id, quality_level),
                )
                pond_row = cursor.fetchone()
                pond_count = int((pond_row or {}).get("quantity") or 0)
                remaining_qty = quantity
                if pond_count > 0:
                    deduct_from_pond = min(pond_count, remaining_qty)
                    if deduct_from_pond > 0:
                        cursor.execute(
                            """
                            UPDATE user_fish_inventory
                            SET quantity = quantity - %s
                            WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity >= %s
                            """,
                            (
                                deduct_from_pond,
                                user_id,
                                fish_id,
                                quality_level,
                                deduct_from_pond,
                            ),
                        )
                        cursor.execute(
                            "DELETE FROM user_fish_inventory WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity <= 0",
                            (user_id, fish_id, quality_level),
                        )
                        remaining_qty -= deduct_from_pond
                if remaining_qty > 0:
                    cursor.execute(
                        """
                        UPDATE user_aquarium
                        SET quantity = quantity - %s
                        WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity >= %s
                        """,
                        (remaining_qty, user_id, fish_id, quality_level, remaining_qty),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError(
                            f"逻辑错误：用户 {user_id} 的鱼类 {fish_id} (品质 {quality_level}) 总数不足以扣除 {quantity}"
                        )
                    cursor.execute(
                        "DELETE FROM user_aquarium WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity <= 0",
                        (user_id, fish_id, quality_level),
                    )
            conn.commit()

    def transfer_fish_to_aquarium(
        self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0
    ) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_fish_inventory
                    SET quantity = quantity - %s
                    WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity >= %s
                    """,
                    (quantity, user_id, fish_id, quality_level, quantity),
                )
                if cursor.rowcount == 0:
                    conn.rollback()
                    return False
                cursor.execute(
                    "DELETE FROM user_fish_inventory WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity <= 0",
                    (user_id, fish_id, quality_level),
                )
                cursor.execute(
                    """
                    INSERT INTO user_aquarium (user_id, fish_id, quality_level, quantity, added_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (user_id, fish_id, quality_level, quantity),
                )
            conn.commit()
            return True

    def transfer_fish_from_aquarium(
        self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0
    ) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_aquarium
                    SET quantity = quantity - %s
                    WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity >= %s
                    """,
                    (quantity, user_id, fish_id, quality_level, quantity),
                )
                if cursor.rowcount == 0:
                    conn.rollback()
                    return False
                cursor.execute(
                    "DELETE FROM user_aquarium WHERE user_id = %s AND fish_id = %s AND quality_level = %s AND quantity <= 0",
                    (user_id, fish_id, quality_level),
                )
                cursor.execute(
                    """
                    INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """,
                    (user_id, fish_id, quality_level, quantity),
                )
            conn.commit()
            return True

    def get_aquarium_upgrades(self) -> List[AquariumUpgrade]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT upgrade_id, level, capacity, cost_coins, cost_premium, description, created_at FROM aquarium_upgrades ORDER BY level"
                )
                return [
                    self._row_to_aquarium_upgrade(row)
                    for row in cursor.fetchall()
                    if row
                ]

    def get_aquarium_upgrade_by_level(self, level: int) -> Optional[AquariumUpgrade]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT upgrade_id, level, capacity, cost_coins, cost_premium, description, created_at FROM aquarium_upgrades WHERE level = %s",
                    (level,),
                )
                return self._row_to_aquarium_upgrade(cursor.fetchone())

    def sell_fish_keep_one(self, user_id: str) -> int:
        sold_value = 0
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ufi.fish_id, ufi.quantity, f.base_value
                    FROM user_fish_inventory ufi
                    JOIN fish f ON ufi.fish_id = f.fish_id
                    WHERE ufi.user_id = %s AND ufi.quantity > 1
                    """,
                    (user_id,),
                )
                items_to_sell = cursor.fetchall()
                if not items_to_sell:
                    return 0
                for item in items_to_sell:
                    sold_qty = item["quantity"] - 1
                    sold_value += sold_qty * item["base_value"]
                cursor.execute(
                    "UPDATE user_fish_inventory SET quantity = 1 WHERE user_id = %s AND quantity > 1",
                    (user_id,),
                )
            conn.commit()
        return sold_value

    def get_user_bait_inventory(self, user_id: str) -> Dict[int, int]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT bait_id, quantity FROM user_bait_inventory WHERE user_id = %s",
                    (user_id,),
                )
                return {row["bait_id"]: row["quantity"] for row in cursor.fetchall()}

    def get_random_bait(self, user_id: str) -> Optional[int]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT bait_id FROM user_bait_inventory WHERE user_id = %s AND quantity > 0 ORDER BY RAND() LIMIT 1",
                    (user_id,),
                )
                row = cursor.fetchone()
                return row["bait_id"] if row else None

    def update_bait_quantity(self, user_id: str, bait_id: int, delta: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if delta >= 0:
                    cursor.execute(
                        """
                        INSERT INTO user_bait_inventory (user_id, bait_id, quantity)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = GREATEST(0, quantity + VALUES(quantity))
                        """,
                        (user_id, bait_id, delta),
                    )
                else:
                    cursor.execute(
                        "UPDATE user_bait_inventory SET quantity = GREATEST(0, quantity + %s) WHERE user_id = %s AND bait_id = %s",
                        (delta, user_id, bait_id),
                    )
                cursor.execute(
                    "DELETE FROM user_bait_inventory WHERE user_id = %s AND quantity <= 0",
                    (user_id,),
                )
            conn.commit()

    def get_user_item_inventory(self, user_id: str) -> Dict[int, int]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT item_id, quantity FROM user_items WHERE user_id = %s",
                    (user_id,),
                )
                return {row["item_id"]: row["quantity"] for row in cursor.fetchall()}

    def update_item_quantity(self, user_id: str, item_id: int, delta: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if delta >= 0:
                    cursor.execute(
                        """
                        INSERT INTO user_items (user_id, item_id, quantity)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = GREATEST(0, quantity + VALUES(quantity))
                        """,
                        (user_id, item_id, delta),
                    )
                else:
                    cursor.execute(
                        "UPDATE user_items SET quantity = GREATEST(0, quantity + %s) WHERE user_id = %s AND item_id = %s",
                        (delta, user_id, item_id),
                    )
                cursor.execute(
                    "DELETE FROM user_items WHERE user_id = %s AND quantity <= 0",
                    (user_id,),
                )
            conn.commit()

    def add_item_to_user(self, user_id: str, item_id: int, quantity: int):
        self.update_item_quantity(user_id, item_id, quantity)

    def increase_item_quantity(self, user_id: str, item_id: int, quantity: int):
        self.update_item_quantity(user_id, item_id, quantity)

    def decrease_item_quantity(self, user_id: str, item_id: int, quantity: int):
        self.update_item_quantity(user_id, item_id, -quantity)

    def get_user_rod_instances(self, user_id: str) -> List[UserRodInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM user_rods WHERE user_id = %s", (user_id,))
                return [
                    self._row_to_rod_instance(row) for row in cursor.fetchall() if row
                ]

    def add_rod_instance(
        self,
        user_id: str,
        rod_id: int,
        durability: Optional[int],
        refine_level: int = 1,
    ) -> UserRodInstance:
        now = datetime.now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO user_rods (user_id, rod_id, current_durability, obtained_at, refine_level, is_equipped, is_locked) VALUES (%s, %s, %s, %s, %s, 0, 0)",
                    (user_id, rod_id, durability, now, refine_level),
                )
                instance_id = cursor.lastrowid
            conn.commit()
        return UserRodInstance(
            rod_instance_id=int(instance_id),
            user_id=user_id,
            rod_id=rod_id,
            is_equipped=False,
            obtained_at=now,
            current_durability=durability,
            refine_level=refine_level,
            is_locked=False,
        )

    def delete_rod_instance(self, rod_instance_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_rods WHERE rod_instance_id = %s",
                    (rod_instance_id,),
                )
            conn.commit()

    def get_user_equipped_rod(self, user_id: str) -> Optional[UserRodInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_rods WHERE user_id = %s AND is_equipped = 1",
                    (user_id,),
                )
                return self._row_to_rod_instance(cursor.fetchone())

    def get_user_rod_instance_by_id(
        self, user_id: str, rod_instance_id: int
    ) -> Optional[UserRodInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_rods WHERE user_id = %s AND rod_instance_id = %s",
                    (user_id, rod_instance_id),
                )
                return self._row_to_rod_instance(cursor.fetchone())

    def clear_user_rod_instances(self, user_id: str) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE ur FROM user_rods ur
                    JOIN rods r ON ur.rod_id = r.rod_id
                    WHERE ur.user_id = %s AND ur.is_equipped = 0 AND r.rarity < 5
                    """,
                    (user_id,),
                )
            conn.commit()

    def clear_user_accessory_instances(self, user_id: str) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE ua FROM user_accessories ua
                    JOIN accessories a ON ua.accessory_id = a.accessory_id
                    WHERE ua.user_id = %s AND ua.is_equipped = 0 AND a.rarity < 5
                    """,
                    (user_id,),
                )
            conn.commit()

    def get_user_accessory_instance_by_id(
        self, user_id: str, accessory_instance_id: int
    ) -> Optional[UserAccessoryInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_accessories WHERE user_id = %s AND accessory_instance_id = %s",
                    (user_id, accessory_instance_id),
                )
                return self._row_to_accessory_instance(cursor.fetchone())

    def get_user_equipped_accessory(
        self, user_id: str
    ) -> Optional[UserAccessoryInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_accessories WHERE user_id = %s AND is_equipped = 1",
                    (user_id,),
                )
                return self._row_to_accessory_instance(cursor.fetchone())

    def set_equipment_status(
        self,
        user_id: str,
        rod_instance_id: Optional[int] = None,
        accessory_instance_id: Optional[int] = None,
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_rods SET is_equipped = 0 WHERE user_id = %s",
                    (user_id,),
                )
                cursor.execute(
                    "UPDATE user_accessories SET is_equipped = 0 WHERE user_id = %s",
                    (user_id,),
                )
                if rod_instance_id is not None:
                    cursor.execute(
                        "UPDATE user_rods SET is_equipped = 1 WHERE rod_instance_id = %s AND user_id = %s",
                        (rod_instance_id, user_id),
                    )
                if accessory_instance_id is not None:
                    cursor.execute(
                        "UPDATE user_accessories SET is_equipped = 1 WHERE accessory_instance_id = %s AND user_id = %s",
                        (accessory_instance_id, user_id),
                    )
            conn.commit()

    def get_user_disposable_baits(self, user_id: str) -> Dict[int, int]:
        return self.get_user_bait_inventory(user_id)

    def get_user_titles(self, user_id: str) -> List[int]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT title_id FROM user_titles WHERE user_id = %s", (user_id,)
                )
                return [row["title_id"] for row in cursor.fetchall()]

    def get_user_accessory_instances(self, user_id: str) -> List[UserAccessoryInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_accessories WHERE user_id = %s", (user_id,)
                )
                return [
                    self._row_to_accessory_instance(row)
                    for row in cursor.fetchall()
                    if row
                ]

    def add_accessory_instance(
        self, user_id: str, accessory_id: int, refine_level: int = 1
    ) -> UserAccessoryInstance:
        now = datetime.now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO user_accessories (user_id, accessory_id, obtained_at, refine_level, is_equipped, is_locked) VALUES (%s, %s, %s, %s, 0, 0)",
                    (user_id, accessory_id, now, refine_level),
                )
                instance_id = cursor.lastrowid
            conn.commit()
        return UserAccessoryInstance(
            accessory_instance_id=int(instance_id),
            user_id=user_id,
            accessory_id=accessory_id,
            is_equipped=False,
            obtained_at=now,
            refine_level=refine_level,
            is_locked=False,
        )

    def delete_accessory_instance(self, accessory_instance_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_accessories WHERE accessory_instance_id = %s",
                    (accessory_instance_id,),
                )
            conn.commit()

    def get_zone_by_id(self, zone_id: int) -> FishingZone:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM fishing_zones WHERE id = %s", (zone_id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"钓鱼区域ID {zone_id} 不存在。")
                row_dict = dict(row)
                if "configs" in row_dict and isinstance(row_dict["configs"], str):
                    row_dict["configs"] = json.loads(row_dict["configs"])
                for key in ("available_from", "available_until"):
                    val = row_dict.get(key)
                    if isinstance(val, str) and val.strip():
                        try:
                            dt = datetime.fromisoformat(val)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                            row_dict[key] = dt
                        except Exception:
                            row_dict[key] = None
                    elif val is None:
                        row_dict[key] = None
                zone = FishingZone(**row_dict)
                zone.specific_fish_ids = self.get_specific_fish_ids_for_zone(zone.id)
                return zone

    def update_fishing_zone(self, zone: FishingZone) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE fishing_zones SET name = %s, description = %s, daily_rare_fish_quota = %s, rare_fish_caught_today = %s WHERE id = %s",
                    (
                        zone.name,
                        zone.description,
                        zone.daily_rare_fish_quota,
                        zone.rare_fish_caught_today,
                        zone.id,
                    ),
                )
            conn.commit()

    def get_all_zones(self) -> List[FishingZone]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM fishing_zones")
                rows = cursor.fetchall()
        zones = []
        for row in rows:
            row_dict = dict(row)
            if "configs" in row_dict and isinstance(row_dict["configs"], str):
                row_dict["configs"] = json.loads(row_dict["configs"])
            for key in ("available_from", "available_until"):
                val = row_dict.get(key)
                if isinstance(val, str) and val.strip():
                    try:
                        dt = datetime.fromisoformat(val)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                        row_dict[key] = dt
                    except Exception:
                        row_dict[key] = None
                elif val is None:
                    row_dict[key] = None
            zone = FishingZone(**row_dict)
            zone.specific_fish_ids = self.get_specific_fish_ids_for_zone(zone.id)
            zones.append(zone)
        return zones

    def update_zone_configs(self, zone_id: int, configs: str) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE fishing_zones SET configs = %s WHERE id = %s",
                    (configs, zone_id),
                )
            conn.commit()

    def create_zone(self, zone_data: Dict[str, Any]) -> FishingZone:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO fishing_zones (id, name, description, daily_rare_fish_quota, configs, is_active, available_from, available_until, required_item_id, requires_pass, fishing_cost)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        zone_data["id"],
                        zone_data["name"],
                        zone_data["description"],
                        zone_data["daily_rare_fish_quota"],
                        json.dumps(zone_data.get("configs", {})),
                        zone_data.get("is_active", True),
                        zone_data.get("available_from"),
                        zone_data.get("available_until"),
                        zone_data.get("required_item_id"),
                        zone_data.get("requires_pass", False),
                        zone_data.get("fishing_cost", 10),
                    ),
                )
            conn.commit()
        return self.get_zone_by_id(zone_data["id"])

    def update_zone(self, zone_id: int, zone_data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE fishing_zones
                    SET name = %s, description = %s, daily_rare_fish_quota = %s, configs = %s, is_active = %s, available_from = %s, available_until = %s, required_item_id = %s, requires_pass = %s, fishing_cost = %s
                    WHERE id = %s
                    """,
                    (
                        zone_data["name"],
                        zone_data["description"],
                        zone_data["daily_rare_fish_quota"],
                        json.dumps(zone_data.get("configs", {})),
                        zone_data.get("is_active", True),
                        zone_data.get("available_from"),
                        zone_data.get("available_until"),
                        zone_data.get("required_item_id"),
                        zone_data.get("requires_pass", False),
                        zone_data.get("fishing_cost", 10),
                        zone_id,
                    ),
                )
            conn.commit()

    def delete_zone(self, zone_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM fishing_zones WHERE id = %s", (zone_id,))
            conn.commit()

    def get_specific_fish_ids_for_zone(self, zone_id: int) -> List[int]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT fish_id FROM zone_fish_mapping WHERE zone_id = %s",
                    (zone_id,),
                )
                return [row["fish_id"] for row in cursor.fetchall()]

    def update_specific_fish_for_zone(self, zone_id: int, fish_ids: List[int]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM zone_fish_mapping WHERE zone_id = %s", (zone_id,)
                )
                if fish_ids:
                    cursor.executemany(
                        "INSERT INTO zone_fish_mapping (zone_id, fish_id) VALUES (%s, %s)",
                        [(zone_id, fish_id) for fish_id in fish_ids],
                    )
            conn.commit()

    def update_rod_instance(self, instance):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_rods SET rod_id = %s, is_equipped = %s, current_durability = %s, refine_level = %s, is_locked = %s WHERE rod_instance_id = %s AND user_id = %s",
                    (
                        instance.rod_id,
                        instance.is_equipped,
                        instance.current_durability,
                        instance.refine_level,
                        instance.is_locked,
                        instance.rod_instance_id,
                        instance.user_id,
                    ),
                )
            conn.commit()

    def transfer_rod_instance_ownership(
        self, rod_instance_id: int, new_user_id: str
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM users WHERE user_id = %s", (new_user_id,)
                )
                if cursor.fetchone() is None:
                    if new_user_id == "MARKET":
                        cursor.execute(
                            "INSERT INTO users (user_id, nickname, coins, premium_currency, created_at) VALUES (%s, %s, %s, %s, %s)",
                            (new_user_id, "[系统-市场托管]", 0, 0, datetime.now()),
                        )
                        logger.info(f"自动创建系统用户: {new_user_id}")
                    else:
                        raise ValueError(f"目标用户 {new_user_id} 不存在")
                cursor.execute(
                    "UPDATE user_rods SET user_id = %s, is_equipped = 0 WHERE rod_instance_id = %s",
                    (new_user_id, rod_instance_id),
                )
            conn.commit()

    def update_accessory_instance(self, instance):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_accessories SET accessory_id = %s, is_equipped = %s, refine_level = %s, is_locked = %s WHERE accessory_instance_id = %s AND user_id = %s",
                    (
                        instance.accessory_id,
                        instance.is_equipped,
                        instance.refine_level,
                        instance.is_locked,
                        instance.accessory_instance_id,
                        instance.user_id,
                    ),
                )
            conn.commit()

    def transfer_accessory_instance_ownership(
        self, accessory_instance_id: int, new_user_id: str
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 AS present FROM users WHERE user_id = %s", (new_user_id,)
                )
                if cursor.fetchone() is None:
                    if new_user_id == "MARKET":
                        cursor.execute(
                            "INSERT INTO users (user_id, nickname, coins, premium_currency, created_at) VALUES (%s, %s, %s, %s, %s)",
                            (new_user_id, "[系统-市场托管]", 0, 0, datetime.now()),
                        )
                        logger.info(f"自动创建系统用户: {new_user_id}")
                    else:
                        raise ValueError(f"目标用户 {new_user_id} 不存在")
                cursor.execute(
                    "UPDATE user_accessories SET user_id = %s, is_equipped = 0 WHERE accessory_instance_id = %s",
                    (new_user_id, accessory_instance_id),
                )
            conn.commit()

    def get_same_rod_instances(self, user_id, rod_id) -> List[UserRodInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_rods WHERE user_id = %s AND rod_id = %s",
                    (user_id, rod_id),
                )
                return [
                    self._row_to_rod_instance(row) for row in cursor.fetchall() if row
                ]

    def get_same_accessory_instances(
        self, user_id, accessory_id
    ) -> List[UserAccessoryInstance]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM user_accessories WHERE user_id = %s AND accessory_id = %s",
                    (user_id, accessory_id),
                )
                return [
                    self._row_to_accessory_instance(row)
                    for row in cursor.fetchall()
                    if row
                ]

    def get_user_fish_counts_in_bulk(
        self, user_id: str, fish_ids: Set[int]
    ) -> Dict[int, int]:
        if not fish_ids:
            return {}
        placeholders = ",".join(["%s"] * len(fish_ids))
        query = f"""
            SELECT fish_id, SUM(quantity) AS total_count
            FROM (
                SELECT fish_id, quantity FROM user_fish_inventory WHERE user_id = %s AND fish_id IN ({placeholders})
                UNION ALL
                SELECT fish_id, quantity FROM user_aquarium WHERE user_id = %s AND fish_id IN ({placeholders})
            ) merged
            GROUP BY fish_id
        """
        params = [user_id] + list(fish_ids) + [user_id] + list(fish_ids)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                results = {
                    row["fish_id"]: row["total_count"] for row in cursor.fetchall()
                }
        for fish_id in fish_ids:
            results.setdefault(fish_id, 0)
        return results
