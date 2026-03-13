from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import Commodity, Exchange, UserCommodity
from .abstract_repository import AbstractExchangeRepository


class MysqlExchangeRepository(AbstractExchangeRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def get_all_commodities(self) -> List[Commodity]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT commodity_id, name, description FROM commodities"
                )
                return [Commodity(**row) for row in cursor.fetchall()]

    def get_commodity_by_id(self, commodity_id: str) -> Optional[Commodity]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT commodity_id, name, description FROM commodities WHERE commodity_id=%s",
                    (commodity_id,),
                )
                row = cursor.fetchone()
                return Commodity(**row) if row else None

    def get_prices_for_date(self, date: str) -> List[Exchange]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT date, time, commodity_id, price, update_type, created_at FROM exchange_prices WHERE date=%s ORDER BY time",
                    (date,),
                )
                return [Exchange(**row) for row in cursor.fetchall()]

    def add_exchange_price(self, price: Exchange) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT IGNORE INTO exchange_prices (date, time, commodity_id, price, update_type, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        price.date,
                        price.time,
                        price.commodity_id,
                        price.price,
                        price.update_type,
                        price.created_at,
                    ),
                )
                conn.commit()

    def delete_prices_for_date(self, date: str) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM exchange_prices WHERE date=%s", (date,))
            conn.commit()

    def _row_to_user_commodity(self, row) -> UserCommodity:
        purchased_at = row["purchased_at"]
        if isinstance(purchased_at, str):
            purchased_at = datetime.fromisoformat(purchased_at)
        expires_at = row["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return UserCommodity(
            instance_id=row["instance_id"],
            user_id=row["user_id"],
            commodity_id=row["commodity_id"],
            quantity=row["quantity"],
            purchase_price=row["purchase_price"],
            purchased_at=purchased_at,
            expires_at=expires_at,
        )

    def get_user_commodities(self, user_id: str) -> List[UserCommodity]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT instance_id, user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at
                    FROM user_commodities WHERE user_id=%s
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        commodities = []
        for row in rows:
            try:
                commodities.append(self._row_to_user_commodity(row))
            except Exception as exc:
                logger.error(f"解析用户商品数据失败: {exc}, 行数据: {row}")
        return commodities

    def add_user_commodity(self, user_commodity: UserCommodity) -> UserCommodity:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_commodities (user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_commodity.user_id,
                        user_commodity.commodity_id,
                        user_commodity.quantity,
                        user_commodity.purchase_price,
                        user_commodity.purchased_at,
                        user_commodity.expires_at,
                    ),
                )
                user_commodity.instance_id = cursor.lastrowid
            conn.commit()
        return user_commodity

    def update_user_commodity_quantity(
        self, instance_id: int, new_quantity: int
    ) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_commodities SET quantity=%s WHERE instance_id=%s",
                    (new_quantity, instance_id),
                )
            conn.commit()

    def delete_user_commodity(self, instance_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_commodities WHERE instance_id=%s", (instance_id,)
                )
            conn.commit()

    def get_user_commodity_by_instance_id(
        self, instance_id: int
    ) -> Optional[UserCommodity]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT instance_id, user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at
                    FROM user_commodities WHERE instance_id=%s
                    """,
                    (instance_id,),
                )
                row = cursor.fetchone()
                return self._row_to_user_commodity(row) if row else None

    def get_all_user_commodities(self) -> List[UserCommodity]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT instance_id, user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at FROM user_commodities"
                )
                return [self._row_to_user_commodity(row) for row in cursor.fetchall()]

    def clear_expired_commodities(self, user_id: str) -> int:
        now = datetime.now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM user_commodities WHERE user_id = %s AND expires_at <= %s",
                    (user_id, now),
                )
                count = int((cursor.fetchone() or {}).get("cnt", 0))
                cursor.execute(
                    "DELETE FROM user_commodities WHERE user_id = %s AND expires_at <= %s",
                    (user_id, now),
                )
            conn.commit()
        return count
