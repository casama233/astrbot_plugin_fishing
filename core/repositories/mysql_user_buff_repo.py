from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import UserBuff
from ..utils import get_now
from .abstract_repository import AbstractUserBuffRepository

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class MysqlUserBuffRepository(AbstractUserBuffRepository):
    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)

    def _to_domain(self, row) -> UserBuff:
        started_at = row["started_at"]
        if isinstance(started_at, str):
            started_at = datetime.strptime(started_at, DATETIME_FORMAT)

        expires_at = row["expires_at"]
        if expires_at is not None and isinstance(expires_at, str):
            expires_at = datetime.strptime(expires_at, DATETIME_FORMAT)

        return UserBuff(
            id=row["id"],
            user_id=row["user_id"],
            buff_type=row["buff_type"],
            payload=row["payload"],
            started_at=started_at,
            expires_at=expires_at,
        )

    def add(self, buff: UserBuff):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_buffs (user_id, buff_type, payload, started_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        buff.user_id,
                        buff.buff_type,
                        buff.payload,
                        buff.started_at.strftime(DATETIME_FORMAT),
                        buff.expires_at.strftime(DATETIME_FORMAT)
                        if buff.expires_at
                        else None,
                    ),
                )
            conn.commit()

    def get_active_by_user_and_type(
        self, user_id: str, buff_type: str
    ) -> Optional[UserBuff]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, buff_type, payload, started_at, expires_at
                    FROM user_buffs
                    WHERE user_id = %s AND buff_type = %s AND (expires_at IS NULL OR expires_at > %s)
                    ORDER BY expires_at DESC
                    LIMIT 1
                    """,
                    (user_id, buff_type, get_now().strftime(DATETIME_FORMAT)),
                )
                row = cursor.fetchone()
                return self._to_domain(row) if row else None

    def update(self, buff: UserBuff):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_buffs
                    SET payload = %s, expires_at = %s
                    WHERE id = %s
                    """,
                    (
                        buff.payload,
                        buff.expires_at.strftime(DATETIME_FORMAT)
                        if buff.expires_at
                        else None,
                        buff.id,
                    ),
                )
            conn.commit()

    def get_all_active_by_user(self, user_id: str) -> List[UserBuff]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, buff_type, payload, started_at, expires_at
                    FROM user_buffs
                    WHERE user_id = %s AND (expires_at IS NULL OR expires_at > %s)
                    """,
                    (user_id, get_now().strftime(DATETIME_FORMAT)),
                )
                return [self._to_domain(row) for row in cursor.fetchall()]

    def delete_expired(self):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_buffs WHERE expires_at IS NOT NULL AND expires_at <= %s",
                    (get_now().strftime(DATETIME_FORMAT),),
                )
            conn.commit()

    def delete(self, buff_id: int):
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_buffs WHERE id = %s", (buff_id,))
            conn.commit()
