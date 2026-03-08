from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import Accessory, Bait, Fish, Item, Rod, Title
from .abstract_repository import AbstractItemTemplateRepository


class MysqlItemTemplateRepository(AbstractItemTemplateRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _row_to_fish(self, row) -> Optional[Fish]:
        return Fish(**row) if row else None

    def _row_to_rod(self, row) -> Optional[Rod]:
        return Rod(**row) if row else None

    def _row_to_bait(self, row) -> Optional[Bait]:
        return Bait(**row) if row else None

    def _row_to_accessory(self, row) -> Optional[Accessory]:
        return Accessory(**row) if row else None

    def _row_to_title(self, row) -> Optional[Title]:
        return Title(**row) if row else None

    def _row_to_item(self, row) -> Optional[Item]:
        return Item(**row) if row else None

    def _to_domain(self, row) -> Item:
        return Item(
            item_id=row["item_id"],
            name=row["name"],
            description=row["description"],
            rarity=row["rarity"],
            effect_description=row["effect_description"],
            cost=row["cost"],
            is_consumable=bool(row["is_consumable"]),
            icon_url=row["icon_url"],
            effect_type=row.get("effect_type"),
            effect_payload=row.get("effect_payload"),
        )

    def add(self, item: Item):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO items (name, description, rarity, effect_description, cost, is_consumable, icon_url, effect_type, effect_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item.name,
                        item.description,
                        item.rarity,
                        item.effect_description,
                        item.cost,
                        item.is_consumable,
                        item.icon_url,
                        item.effect_type,
                        item.effect_payload,
                    ),
                )
            conn.commit()

    def get_by_id(self, item_id: int) -> Optional[Item]:
        return self.get_item_by_id(item_id)

    def get_all(self) -> List[Item]:
        return self.get_all_items()

    def get_by_name(self, name: str) -> Optional[Item]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT item_id, name, description, rarity, effect_description, cost, is_consumable, icon_url, effect_type, effect_payload FROM items WHERE name = %s",
                    (name,),
                )
                row = cursor.fetchone()
                return self._to_domain(row) if row else None

    def update(self, item: Item):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE items
                    SET name = %s, description = %s, rarity = %s, effect_description = %s, cost = %s, is_consumable = %s, icon_url = %s, effect_type = %s, effect_payload = %s
                    WHERE item_id = %s
                    """,
                    (
                        item.name,
                        item.description,
                        item.rarity,
                        item.effect_description,
                        item.cost,
                        item.is_consumable,
                        item.icon_url,
                        item.effect_type,
                        item.effect_payload,
                        item.item_id,
                    ),
                )
            conn.commit()

    def get_fish_by_id(self, fish_id: int) -> Optional[Fish]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM fish WHERE fish_id = %s", (fish_id,))
                return self._row_to_fish(cursor.fetchone())

    def get_all_fish(self) -> List[Fish]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fish ORDER BY rarity DESC, base_value DESC"
                )
                return [self._row_to_fish(row) for row in cursor.fetchall() if row]

    def get_random_fish(self, rarity: Optional[int] = None) -> Optional[Fish]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                if rarity is not None:
                    cursor.execute(
                        "SELECT * FROM fish WHERE rarity = %s ORDER BY RAND() LIMIT 1",
                        (rarity,),
                    )
                else:
                    cursor.execute("SELECT * FROM fish ORDER BY RAND() LIMIT 1")
                row = cursor.fetchone()
                return self._row_to_fish(row) if row else None

    def get_fishes_by_rarity(self, rarity: int) -> List[Fish]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM fish WHERE rarity = %s", (rarity,))
                return [self._row_to_fish(row) for row in cursor.fetchall() if row]

    def get_rod_by_id(self, rod_id: int) -> Optional[Rod]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM rods WHERE rod_id = %s", (rod_id,))
                return self._row_to_rod(cursor.fetchone())

    def get_all_rods(self) -> List[Rod]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM rods ORDER BY rarity DESC")
                return [self._row_to_rod(row) for row in cursor.fetchall() if row]

    def get_bait_by_id(self, bait_id: int) -> Optional[Bait]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM baits WHERE bait_id = %s", (bait_id,))
                return self._row_to_bait(cursor.fetchone())

    def get_all_baits(self) -> List[Bait]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM baits ORDER BY rarity DESC")
                return [self._row_to_bait(row) for row in cursor.fetchall() if row]

    def get_accessory_by_id(self, accessory_id: int) -> Optional[Accessory]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM accessories WHERE accessory_id = %s",
                    (accessory_id,),
                )
                return self._row_to_accessory(cursor.fetchone())

    def get_all_accessories(self) -> List[Accessory]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM accessories ORDER BY rarity DESC")
                return [self._row_to_accessory(row) for row in cursor.fetchall() if row]

    def get_title_by_id(self, title_id: int) -> Optional[Title]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM titles WHERE title_id = %s", (title_id,))
                return self._row_to_title(cursor.fetchone())

    def get_all_titles(self) -> List[Title]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM titles ORDER BY title_id")
                return [self._row_to_title(row) for row in cursor.fetchall() if row]

    def get_title_by_name(self, name: str) -> Optional[Title]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM titles WHERE name = %s", (name,))
                return self._row_to_title(cursor.fetchone())

    def get_item_by_id(self, item_id: int) -> Optional[Item]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM items WHERE item_id = %s", (item_id,))
                return self._row_to_item(cursor.fetchone())

    def get_all_items(self) -> List[Item]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM items ORDER BY rarity DESC, cost DESC")
                return [self._row_to_item(row) for row in cursor.fetchall() if row]

    def add_fish_template(self, data: Dict[str, Any]) -> Fish:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO fish (name, description, rarity, base_value, min_weight, max_weight, icon_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("base_value"),
                        data.get("min_weight"),
                        data.get("max_weight"),
                        data.get("icon_url"),
                    ),
                )
                fish_id = cursor.lastrowid
            conn.commit()
        fish = self.get_fish_by_id(int(fish_id)) if fish_id is not None else None
        if fish is None:
            raise RuntimeError("Failed to create fish template")
        return fish

    def update_fish_template(self, fish_id: int, data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE fish SET
                        name = %s, description = %s, rarity = %s,
                        base_value = %s, min_weight = %s,
                        max_weight = %s, icon_url = %s
                    WHERE fish_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("base_value"),
                        data.get("min_weight"),
                        data.get("max_weight"),
                        data.get("icon_url"),
                        fish_id,
                    ),
                )
            conn.commit()

    def delete_fish_template(self, fish_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM fish WHERE fish_id = %s", (fish_id,))
            conn.commit()

    def add_rod_template(self, data: Dict[str, Any]) -> Rod:
        durability_value = data.get("durability")
        if durability_value == "":
            durability_value = None
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rods (name, description, rarity, source, purchase_cost,
                                      bonus_fish_quality_modifier, bonus_fish_quantity_modifier,
                                      bonus_rare_fish_chance, durability, icon_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("source"),
                        data.get("purchase_cost") or None,
                        data.get("bonus_fish_quality_modifier"),
                        data.get("bonus_fish_quantity_modifier"),
                        data.get("bonus_rare_fish_chance"),
                        durability_value,
                        data.get("icon_url"),
                    ),
                )
                rod_id = cursor.lastrowid
            conn.commit()
        rod = self.get_rod_by_id(int(rod_id)) if rod_id is not None else None
        if rod is None:
            raise RuntimeError("Failed to create rod template")
        return rod

    def update_rod_template(self, rod_id: int, data: Dict[str, Any]) -> None:
        durability_value = data.get("durability")
        if durability_value == "":
            durability_value = None
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE rods SET
                        name = %s, description = %s, rarity = %s, source = %s,
                        purchase_cost = %s, bonus_fish_quality_modifier = %s,
                        bonus_fish_quantity_modifier = %s,
                        bonus_rare_fish_chance = %s, durability = %s,
                        icon_url = %s
                    WHERE rod_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("source"),
                        data.get("purchase_cost") or None,
                        data.get("bonus_fish_quality_modifier"),
                        data.get("bonus_fish_quantity_modifier"),
                        data.get("bonus_rare_fish_chance"),
                        durability_value,
                        data.get("icon_url"),
                        rod_id,
                    ),
                )
            conn.commit()

    def delete_rod_template(self, rod_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM rods WHERE rod_id = %s", (rod_id,))
            conn.commit()

    def add_bait_template(self, data: Dict[str, Any]) -> Bait:
        params = {
            "name": data.get("name"),
            "description": data.get("description"),
            "rarity": data.get("rarity", 1),
            "effect_description": data.get("effect_description"),
            "duration_minutes": data.get("duration_minutes", 0),
            "cost": data.get("cost", 0),
            "required_rod_rarity": data.get("required_rod_rarity", 0),
            "success_rate_modifier": data.get("success_rate_modifier", 0.0),
            "rare_chance_modifier": data.get("rare_chance_modifier", 0.0),
            "garbage_reduction_modifier": data.get("garbage_reduction_modifier", 0.0),
            "value_modifier": data.get("value_modifier", 1.0),
            "quantity_modifier": data.get("quantity_modifier", 1.0),
            "weight_modifier": data.get("weight_modifier", 1.0),
            "is_consumable": 1 if data.get("is_consumable") else 0,
        }
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO baits (
                        name, description, rarity, effect_description, duration_minutes, cost, required_rod_rarity,
                        success_rate_modifier, rare_chance_modifier, garbage_reduction_modifier,
                        value_modifier, quantity_modifier, weight_modifier, is_consumable
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        params["name"],
                        params["description"],
                        params["rarity"],
                        params["effect_description"],
                        params["duration_minutes"],
                        params["cost"],
                        params["required_rod_rarity"],
                        params["success_rate_modifier"],
                        params["rare_chance_modifier"],
                        params["garbage_reduction_modifier"],
                        params["value_modifier"],
                        params["quantity_modifier"],
                        params["weight_modifier"],
                        params["is_consumable"],
                    ),
                )
                bait_id = cursor.lastrowid
            conn.commit()
        bait = self.get_bait_by_id(int(bait_id)) if bait_id is not None else None
        if bait is None:
            raise RuntimeError("Failed to create bait template")
        return bait

    def update_bait_template(self, bait_id: int, data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE baits SET
                        name = %s, description = %s, rarity = %s,
                        effect_description = %s, duration_minutes = %s,
                        cost = %s, required_rod_rarity = %s,
                        success_rate_modifier = %s, rare_chance_modifier = %s,
                        garbage_reduction_modifier = %s, value_modifier = %s,
                        quantity_modifier = %s, weight_modifier = %s, is_consumable = %s
                    WHERE bait_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity", 1),
                        data.get("effect_description"),
                        data.get("duration_minutes", 0),
                        data.get("cost", 0),
                        data.get("required_rod_rarity", 0),
                        data.get("success_rate_modifier", 0.0),
                        data.get("rare_chance_modifier", 0.0),
                        data.get("garbage_reduction_modifier", 0.0),
                        data.get("value_modifier", 1.0),
                        data.get("quantity_modifier", 1.0),
                        data.get("weight_modifier", 1.0),
                        1 if data.get("is_consumable") else 0,
                        bait_id,
                    ),
                )
            conn.commit()

    def delete_bait_template(self, bait_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM baits WHERE bait_id = %s", (bait_id,))
            conn.commit()

    def add_accessory_template(self, data: Dict[str, Any]) -> Accessory:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO accessories (name, description, rarity, slot_type, bonus_fish_quality_modifier,
                                             bonus_fish_quantity_modifier, bonus_rare_fish_chance,
                                             bonus_coin_modifier, other_bonus_description, icon_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("slot_type"),
                        data.get("bonus_fish_quality_modifier"),
                        data.get("bonus_fish_quantity_modifier"),
                        data.get("bonus_rare_fish_chance"),
                        data.get("bonus_coin_modifier"),
                        data.get("other_bonus_description"),
                        data.get("icon_url"),
                    ),
                )
                accessory_id = cursor.lastrowid
            conn.commit()
        accessory = (
            self.get_accessory_by_id(int(accessory_id))
            if accessory_id is not None
            else None
        )
        if accessory is None:
            raise RuntimeError("Failed to create accessory template")
        return accessory

    def update_accessory_template(
        self, accessory_id: int, data: Dict[str, Any]
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE accessories SET
                        name = %s, description = %s, rarity = %s, slot_type = %s,
                        bonus_fish_quality_modifier = %s,
                        bonus_fish_quantity_modifier = %s,
                        bonus_rare_fish_chance = %s,
                        bonus_coin_modifier = %s,
                        other_bonus_description = %s, icon_url = %s
                    WHERE accessory_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("slot_type"),
                        data.get("bonus_fish_quality_modifier"),
                        data.get("bonus_fish_quantity_modifier"),
                        data.get("bonus_rare_fish_chance"),
                        data.get("bonus_coin_modifier"),
                        data.get("other_bonus_description"),
                        data.get("icon_url"),
                        accessory_id,
                    ),
                )
            conn.commit()

    def delete_accessory_template(self, accessory_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM accessories WHERE accessory_id = %s", (accessory_id,)
                )
            conn.commit()

    def add_item_template(self, data: Dict[str, Any]) -> Item:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO items (name, description, rarity, effect_description, cost, is_consumable, icon_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("effect_description"),
                        data.get("cost"),
                        1 if data.get("is_consumable") else 0,
                        data.get("icon_url"),
                    ),
                )
                item_id = cursor.lastrowid
            conn.commit()
        item = self.get_item_by_id(int(item_id)) if item_id is not None else None
        if item is None:
            raise RuntimeError("Failed to create item template")
        return item

    def update_item_template(self, item_id: int, data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE items SET
                        name = %s, description = %s, rarity = %s,
                        effect_description = %s,
                        cost = %s, is_consumable = %s, icon_url = %s
                    WHERE item_id = %s
                    """,
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("rarity"),
                        data.get("effect_description"),
                        data.get("cost"),
                        1 if data.get("is_consumable") else 0,
                        data.get("icon_url"),
                        item_id,
                    ),
                )
            conn.commit()

    def delete_item_template(self, item_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM items WHERE item_id = %s", (item_id,))
            conn.commit()

    def add_title_template(self, data: Dict[str, Any]) -> Title:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO titles (title_id, name, description, display_format) VALUES (%s, %s, %s, %s)",
                    (
                        data.get("title_id"),
                        data.get("name"),
                        data.get("description"),
                        data.get("display_format"),
                    ),
                )
            conn.commit()
        title = (
            self.get_title_by_id(int(data.get("title_id")))
            if data.get("title_id") is not None
            else None
        )
        if title is None:
            raise RuntimeError("Failed to create title template")
        return title

    def update_title_template(self, title_id: int, data: Dict[str, Any]) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE titles SET name = %s, description = %s, display_format = %s WHERE title_id = %s",
                    (
                        data.get("name"),
                        data.get("description"),
                        data.get("display_format"),
                        title_id,
                    ),
                )
            conn.commit()

    def delete_title_template(self, title_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM titles WHERE title_id = %s", (title_id,))
            conn.commit()
