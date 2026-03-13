from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import Guild, GuildMember, GuildBuff
from ..utils import get_now


class MysqlGuildRepository:
    """公會倉儲"""

    def __init__(self, config):
        self._connection_manager = MysqlConnectionManager(config)
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """確保公會相關表存在"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS guilds (
                        guild_id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        leader_id VARCHAR(255) NOT NULL,
                        description TEXT,
                        emblem VARCHAR(255),
                        level INT NOT NULL DEFAULT 1,
                        exp INT NOT NULL DEFAULT 0,
                        member_count INT NOT NULL DEFAULT 1,
                        max_members INT NOT NULL DEFAULT 30,
                        total_fish_caught BIGINT NOT NULL DEFAULT 0,
                        total_coins_earned BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_active TINYINT(1) NOT NULL DEFAULT 1,
                        UNIQUE KEY uk_name (name),
                        KEY idx_leader_id (leader_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS guild_members (
                        membership_id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id INT NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        role VARCHAR(20) NOT NULL DEFAULT 'member',
                        contribution INT NOT NULL DEFAULT 0,
                        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_contribution_at DATETIME NULL,
                        UNIQUE KEY uk_user_guild (user_id, guild_id),
                        KEY idx_guild_id (guild_id),
                        KEY idx_user_id (user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS guild_buffs (
                        buff_id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id INT NOT NULL,
                        buff_type VARCHAR(50) NOT NULL,
                        buff_value DECIMAL(10,4) NOT NULL DEFAULT 0,
                        expires_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_guild_id (guild_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

    def _parse_datetime(self, dt_val) -> Optional[datetime]:
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

    def _row_to_guild(self, row) -> Optional[Guild]:
        if not row:
            return None
        return Guild(
            guild_id=row["guild_id"],
            name=row["name"],
            leader_id=row["leader_id"],
            description=row.get("description"),
            emblem=row.get("emblem"),
            level=row["level"] or 1,
            exp=row["exp"] or 0,
            member_count=row["member_count"] or 1,
            max_members=row["max_members"] or 30,
            total_fish_caught=row["total_fish_caught"] or 0,
            total_coins_earned=row["total_coins_earned"] or 0,
            created_at=self._parse_datetime(row.get("created_at")),
            is_active=bool(row["is_active"]),
        )

    def _row_to_member(self, row) -> Optional[GuildMember]:
        if not row:
            return None
        return GuildMember(
            membership_id=row["membership_id"],
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            role=row["role"] or "member",
            contribution=row["contribution"] or 0,
            joined_at=self._parse_datetime(row.get("joined_at")),
            last_contribution_at=self._parse_datetime(row.get("last_contribution_at")),
        )

    def create_guild(self, name: str, leader_id: str, description: str = None) -> Guild:
        """創建公會"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO guilds (name, leader_id, description, created_at)
                    VALUES (%s, %s, %s, %s)
                """,
                    (name, leader_id, description, now),
                )
                guild_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO guild_members (guild_id, user_id, role, joined_at)
                    VALUES (%s, %s, 'leader', %s)
                """,
                    (guild_id, leader_id, now),
                )
                conn.commit()
        return self.get_guild_by_id(guild_id)

    def get_guild_by_id(self, guild_id: int) -> Optional[Guild]:
        """根據 ID 獲取公會"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM guilds WHERE guild_id = %s", (guild_id,))
                row = cursor.fetchone()
                return self._row_to_guild(row)

    def get_guild_by_name(self, name: str) -> Optional[Guild]:
        """根據名稱獲取公會"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM guilds WHERE name = %s", (name,))
                row = cursor.fetchone()
                return self._row_to_guild(row)

    def get_guild_by_leader(self, leader_id: str) -> Optional[Guild]:
        """根據會長 ID 獲取公會"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM guilds WHERE leader_id = %s AND is_active = 1",
                    (leader_id,),
                )
                row = cursor.fetchone()
                return self._row_to_guild(row)

    def get_user_guild(self, user_id: str) -> Optional[Guild]:
        """獲取用戶所屬公會"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT g.* FROM guilds g
                    JOIN guild_members gm ON g.guild_id = gm.guild_id
                    WHERE gm.user_id = %s AND g.is_active = 1
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return self._row_to_guild(row)

    def get_guild_members(self, guild_id: int) -> List[GuildMember]:
        """獲取公會所有成員"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM guild_members WHERE guild_id = %s ORDER BY role DESC, contribution DESC
                """,
                    (guild_id,),
                )
                rows = cursor.fetchall()
                return [self._row_to_member(row) for row in rows if row]

    def get_member(self, user_id: str) -> Optional[GuildMember]:
        """獲取用戶的公會成員信息"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM guild_members WHERE user_id = %s
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return self._row_to_member(row)

    def add_member(self, guild_id: int, user_id: str, role: str = "member") -> bool:
        """添加成員"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        """
                        INSERT INTO guild_members (guild_id, user_id, role, joined_at)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (guild_id, user_id, role, now),
                    )
                    cursor.execute(
                        """
                        UPDATE guilds SET member_count = member_count + 1 WHERE guild_id = %s
                    """,
                        (guild_id,),
                    )
                    conn.commit()
                    return True
                except Exception as e:
                    logger.error(f"添加公會成員失敗: {e}")
                    return False

    def remove_member(self, guild_id: int, user_id: str) -> bool:
        """移除成員"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM guild_members WHERE guild_id = %s AND user_id = %s
                """,
                    (guild_id, user_id),
                )
                if cursor.rowcount > 0:
                    cursor.execute(
                        """
                        UPDATE guilds SET member_count = GREATEST(1, member_count - 1) WHERE guild_id = %s
                    """,
                        (guild_id,),
                    )
                    conn.commit()
                    return True
                return False

    def update_member_role(self, guild_id: int, user_id: str, role: str) -> bool:
        """更新成員角色"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE guild_members SET role = %s WHERE guild_id = %s AND user_id = %s
                """,
                    (role, guild_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0

    def add_contribution(self, user_id: str, amount: int) -> bool:
        """增加貢獻值"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE guild_members 
                    SET contribution = contribution + %s, last_contribution_at = %s
                    WHERE user_id = %s
                """,
                    (amount, now, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0

    def add_guild_exp(self, guild_id: int, exp: int) -> bool:
        """增加公會經驗"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE guilds SET exp = exp + %s WHERE guild_id = %s
                """,
                    (exp, guild_id),
                )
                conn.commit()
                return cursor.rowcount > 0

    def update_guild_stats(
        self, guild_id: int, fish_caught: int = 0, coins_earned: int = 0
    ) -> bool:
        """更新公會統計"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE guilds 
                    SET total_fish_caught = total_fish_caught + %s,
                        total_coins_earned = total_coins_earned + %s
                    WHERE guild_id = %s
                """,
                    (fish_caught, coins_earned, guild_id),
                )
                conn.commit()
                return cursor.rowcount > 0

    def disband_guild(self, guild_id: int) -> bool:
        """解散公會"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM guild_members WHERE guild_id = %s", (guild_id,)
                )
                cursor.execute(
                    "UPDATE guilds SET is_active = 0 WHERE guild_id = %s", (guild_id,)
                )
                conn.commit()
                return True

    def get_top_guilds(self, limit: int = 10) -> List[Guild]:
        """獲取公會排行榜"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM guilds WHERE is_active = 1
                    ORDER BY total_fish_caught DESC LIMIT %s
                """,
                    (limit,),
                )
                rows = cursor.fetchall()
                return [self._row_to_guild(row) for row in rows if row]
