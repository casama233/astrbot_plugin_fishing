from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import MarketListing
from .abstract_repository import AbstractMarketRepository


class MysqlMarketRepository(AbstractMarketRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _row_to_market_listing(self, row) -> Optional[MarketListing]:
        if not row:
            return None
        data = dict(row)
        if "listed_at" in data and isinstance(data["listed_at"], str):
            try:
                data["listed_at"] = datetime.fromisoformat(
                    data["listed_at"].replace("Z", "+00:00")
                )
            except Exception:
                data["listed_at"] = datetime.now()
        if "expires_at" in data and isinstance(data["expires_at"], str):
            try:
                data["expires_at"] = datetime.fromisoformat(
                    data["expires_at"].replace("Z", "+00:00")
                )
            except Exception:
                data["expires_at"] = None
        return MarketListing(**data)

    def get_listing_by_id(self, market_id: int) -> Optional[MarketListing]:
        query = """
            SELECT
                m.market_id,
                m.user_id,
                u.nickname AS seller_nickname,
                m.item_type,
                m.item_id,
                m.item_instance_id,
                m.quantity,
                m.price,
                m.refine_level,
                m.listed_at,
                COALESCE(m.is_anonymous, 0) AS is_anonymous,
                COALESCE(m.quality_level, 0) AS quality_level,
                CASE
                    WHEN m.item_type = 'rod' THEN r.name
                    WHEN m.item_type = 'accessory' THEN a.name
                    WHEN m.item_type = 'item' THEN i.name
                    WHEN m.item_type = 'fish' THEN f.name
                    WHEN m.item_type = 'commodity' THEN c.name
                    ELSE '未知物品'
                END AS item_name,
                CASE
                    WHEN m.item_type = 'rod' THEN r.description
                    WHEN m.item_type = 'accessory' THEN a.description
                    WHEN m.item_type = 'item' THEN i.description
                    WHEN m.item_type = 'fish' THEN f.description
                    WHEN m.item_type = 'commodity' THEN c.description
                    ELSE ''
                END AS item_description,
                m.expires_at
            FROM market m
            JOIN users u ON m.user_id = u.user_id
            LEFT JOIN rods r ON m.item_type = 'rod' AND m.item_id = r.rod_id
            LEFT JOIN accessories a ON m.item_type = 'accessory' AND m.item_id = a.accessory_id
            LEFT JOIN items i ON m.item_type = 'item' AND m.item_id = i.item_id
            LEFT JOIN fish f ON m.item_type = 'fish' AND m.item_id = f.fish_id
            LEFT JOIN commodities c ON m.item_type = 'commodity' AND m.item_id = c.commodity_id
            WHERE m.market_id = %s
        """
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (market_id,))
                return self._row_to_market_listing(cursor.fetchone())

    def get_all_listings(
        self,
        page: int = None,
        per_page: int = None,
        item_type: str = None,
        min_price: int = None,
        max_price: int = None,
        search: str = None,
    ) -> tuple:
        where_conditions = []
        params: list[Any] = []
        if item_type:
            where_conditions.append("m.item_type = %s")
            params.append(item_type)
        if min_price is not None:
            where_conditions.append("m.price >= %s")
            params.append(min_price)
        if max_price is not None:
            where_conditions.append("m.price <= %s")
            params.append(max_price)
        if search:
            search_condition = """(
                (m.item_type = 'rod' AND r.name LIKE %s) OR
                (m.item_type = 'accessory' AND a.name LIKE %s) OR
                (m.item_type = 'item' AND i.name LIKE %s) OR
                (m.item_type = 'fish' AND f.name LIKE %s) OR
                (m.item_type = 'commodity' AND c.name LIKE %s) OR
                u.nickname LIKE %s
            )"""
            where_conditions.append(search_condition)
            search_param = f"%{search}%"
            params.extend(
                [
                    search_param,
                    search_param,
                    search_param,
                    search_param,
                    search_param,
                    search_param,
                ]
            )
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        joins = """
            FROM market m
            JOIN users u ON m.user_id = u.user_id
            LEFT JOIN rods r ON m.item_type = 'rod' AND m.item_id = r.rod_id
            LEFT JOIN accessories a ON m.item_type = 'accessory' AND m.item_id = a.accessory_id
            LEFT JOIN items i ON m.item_type = 'item' AND m.item_id = i.item_id
            LEFT JOIN fish f ON m.item_type = 'fish' AND m.item_id = f.fish_id
            LEFT JOIN commodities c ON m.item_type = 'commodity' AND m.item_id = c.commodity_id
        """
        count_query = f"SELECT COUNT(*) AS cnt {joins} WHERE {where_clause}"
        query = f"""
            SELECT
                m.market_id,
                m.user_id,
                u.nickname AS seller_nickname,
                m.item_type,
                m.item_id,
                m.item_instance_id,
                m.quantity,
                m.price,
                m.refine_level,
                m.listed_at,
                COALESCE(m.is_anonymous, 0) AS is_anonymous,
                COALESCE(m.quality_level, 0) AS quality_level,
                CASE
                    WHEN m.item_type = 'rod' THEN r.name
                    WHEN m.item_type = 'accessory' THEN a.name
                    WHEN m.item_type = 'item' THEN i.name
                    WHEN m.item_type = 'fish' THEN f.name
                    WHEN m.item_type = 'commodity' THEN c.name
                    ELSE '未知物品'
                END AS item_name,
                CASE
                    WHEN m.item_type = 'rod' THEN r.description
                    WHEN m.item_type = 'accessory' THEN a.description
                    WHEN m.item_type = 'item' THEN i.description
                    WHEN m.item_type = 'fish' THEN f.description
                    WHEN m.item_type = 'commodity' THEN c.description
                    ELSE ''
                END AS item_description,
                m.expires_at
            {joins}
            WHERE {where_clause}
            ORDER BY m.listed_at DESC
        """
        query_params = list(params)
        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            query += " LIMIT %s OFFSET %s"
            query_params.extend([per_page, offset])
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(count_query, tuple(params))
                total_count = int((cursor.fetchone() or {}).get("cnt", 0))
                cursor.execute(query, tuple(query_params))
                listings = [
                    self._row_to_market_listing(row) for row in cursor.fetchall() if row
                ]
                return listings, total_count

    def add_listing(self, listing: MarketListing) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO market (user_id, item_type, item_id, item_name, item_description, quantity, price, listed_at, refine_level, is_anonymous, item_instance_id, quality_level, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        listing.user_id,
                        listing.item_type,
                        listing.item_id,
                        listing.item_name,
                        listing.item_description,
                        listing.quantity,
                        listing.price,
                        listing.listed_at or datetime.now(),
                        listing.refine_level,
                        listing.is_anonymous,
                        listing.item_instance_id,
                        getattr(listing, "quality_level", 0),
                        listing.expires_at,
                    ),
                )
            conn.commit()

    def remove_listing(self, market_id: int) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM market WHERE market_id = %s", (market_id,))
            conn.commit()

    def update_listing(self, listing: MarketListing) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE market SET price = %s, refine_level = %s WHERE market_id = %s",
                    (listing.price, listing.refine_level, listing.market_id),
                )
            conn.commit()
