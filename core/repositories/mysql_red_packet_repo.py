from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import RedPacket, RedPacketRecord
from .abstract_repository import AbstractRedPacketRepository


class MysqlRedPacketRepository(AbstractRedPacketRepository):
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

    def _row_to_red_packet(self, row) -> Optional[RedPacket]:
        if not row:
            return None
        return RedPacket(
            packet_id=row["packet_id"],
            sender_id=row["sender_id"],
            group_id=row["group_id"],
            packet_type=row["packet_type"],
            total_amount=row["total_amount"],
            total_count=row["total_count"],
            remaining_amount=row["remaining_amount"],
            remaining_count=row["remaining_count"],
            password=row["password"],
            created_at=self._parse_datetime(row["created_at"]),
            expires_at=self._parse_datetime(row["expires_at"]),
            is_expired=bool(row["is_expired"]),
        )

    def _row_to_record(self, row) -> Optional[RedPacketRecord]:
        if not row:
            return None
        return RedPacketRecord(
            record_id=row["record_id"],
            packet_id=row["packet_id"],
            user_id=row["user_id"],
            amount=row["amount"],
            claimed_at=self._parse_datetime(row["claimed_at"]),
        )

    def create_red_packet(self, packet: RedPacket) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO red_packets (
                        sender_id, group_id, packet_type, total_amount, total_count,
                        remaining_amount, remaining_count, password, created_at, expires_at, is_expired
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        packet.sender_id,
                        packet.group_id,
                        packet.packet_type,
                        packet.total_amount,
                        packet.total_count,
                        packet.remaining_amount,
                        packet.remaining_count,
                        packet.password,
                        packet.created_at,
                        packet.expires_at,
                        packet.is_expired,
                    ),
                )
                packet_id = cursor.lastrowid
            conn.commit()
            return int(packet_id)

    def get_red_packet_by_id(self, packet_id: int) -> Optional[RedPacket]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM red_packets WHERE packet_id = %s", (packet_id,)
                )
                return self._row_to_red_packet(cursor.fetchone())

    def get_active_red_packets_in_group(self, group_id: str) -> List[RedPacket]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM red_packets WHERE group_id = %s AND is_expired = 0 AND remaining_count > 0 ORDER BY created_at DESC",
                    (group_id,),
                )
                return [
                    self._row_to_red_packet(row) for row in cursor.fetchall() if row
                ]

    def update_red_packet(self, packet: RedPacket) -> None:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE red_packets SET remaining_amount = %s, remaining_count = %s, is_expired = %s WHERE packet_id = %s",
                    (
                        packet.remaining_amount,
                        packet.remaining_count,
                        packet.is_expired,
                        packet.packet_id,
                    ),
                )
            conn.commit()

    def create_claim_record(self, record: RedPacketRecord) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO red_packet_records (packet_id, user_id, amount, claimed_at) VALUES (%s, %s, %s, %s)",
                    (
                        record.packet_id,
                        record.user_id,
                        record.amount,
                        record.claimed_at,
                    ),
                )
                record_id = cursor.lastrowid
            conn.commit()
            return int(record_id)

    def has_user_claimed(self, packet_id: int, user_id: str) -> bool:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM red_packet_records WHERE packet_id = %s AND user_id = %s",
                    (packet_id, user_id),
                )
                count = int((cursor.fetchone() or {}).get("cnt", 0))
                return count > 0

    def get_claim_records_by_packet(self, packet_id: int) -> List[RedPacketRecord]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM red_packet_records WHERE packet_id = %s ORDER BY claimed_at ASC",
                    (packet_id,),
                )
                return [self._row_to_record(row) for row in cursor.fetchall() if row]

    def expire_old_packets(self, current_time: datetime) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE red_packets SET is_expired = 1 WHERE expires_at < %s AND is_expired = 0",
                    (current_time,),
                )
                changed = cursor.rowcount
            conn.commit()
            return changed

    def clean_old_red_packets(self, days_to_keep: int = 7) -> int:
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT packet_id FROM red_packets WHERE is_expired = 1 AND expires_at < %s",
                    (cutoff_time,),
                )
                packet_ids = [row["packet_id"] for row in cursor.fetchall()]
                if not packet_ids:
                    return 0
                placeholders = ",".join(["%s"] * len(packet_ids))
                cursor.execute(
                    f"DELETE FROM red_packet_records WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
                cursor.execute(
                    f"DELETE FROM red_packets WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
            conn.commit()
            deleted_count = len(packet_ids)
            logger.info(f"清理了 {deleted_count} 个过期红包记录（{days_to_keep}天前）")
            return deleted_count

    def get_group_red_packets(self, group_id: str) -> List[RedPacket]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM red_packets WHERE group_id = %s ORDER BY created_at DESC",
                    (group_id,),
                )
                return [
                    self._row_to_red_packet(row) for row in cursor.fetchall() if row
                ]

    def revoke_group_red_packets(self, group_id: str) -> tuple[int, int, list]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT packet_id, sender_id, remaining_amount FROM red_packets WHERE group_id = %s AND is_expired = 0 AND remaining_amount > 0",
                    (group_id,),
                )
                packets_to_revoke = cursor.fetchall()
                if not packets_to_revoke:
                    return (0, 0, [])
                packet_ids = [p["packet_id"] for p in packets_to_revoke]
                placeholders = ",".join(["%s"] * len(packet_ids))
                cursor.execute(
                    f"UPDATE red_packets SET is_expired = 1, remaining_count = 0, remaining_amount = 0 WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
            conn.commit()
            refund_count = len(packets_to_revoke)
            refund_amount = sum(p["remaining_amount"] for p in packets_to_revoke)
            return (refund_count, refund_amount, packets_to_revoke)

    def revoke_all_red_packets(self) -> tuple[int, int, list]:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT packet_id, sender_id, remaining_amount FROM red_packets WHERE is_expired = 0 AND remaining_amount > 0"
                )
                packets_to_revoke = cursor.fetchall()
                if not packets_to_revoke:
                    return (0, 0, [])
                cursor.execute(
                    "UPDATE red_packets SET is_expired = 1, remaining_count = 0, remaining_amount = 0 WHERE is_expired = 0 AND remaining_amount > 0"
                )
            conn.commit()
            refund_count = len(packets_to_revoke)
            refund_amount = sum(p["remaining_amount"] for p in packets_to_revoke)
            return (refund_count, refund_amount, packets_to_revoke)

    def delete_group_red_packets(self, group_id: str) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT packet_id FROM red_packets WHERE group_id = %s", (group_id,)
                )
                packet_ids = [row["packet_id"] for row in cursor.fetchall()]
                if not packet_ids:
                    return 0
                placeholders = ",".join(["%s"] * len(packet_ids))
                cursor.execute(
                    f"DELETE FROM red_packet_records WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
                cursor.execute(
                    "DELETE FROM red_packets WHERE group_id = %s", (group_id,)
                )
            conn.commit()
            return len(packet_ids)

    def delete_all_red_packets(self) -> int:
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS cnt FROM red_packets")
                count = int((cursor.fetchone() or {}).get("cnt", 0))
                cursor.execute("DELETE FROM red_packet_records")
                cursor.execute("DELETE FROM red_packets")
            conn.commit()
            logger.info(f"已删除 {count} 个红包记录")
            return count

    def cleanup_expired_red_packets(self) -> int:
        expired_time = datetime.now() - timedelta(hours=24)
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT packet_id FROM red_packets WHERE expires_at < %s AND is_expired = 1",
                    (expired_time,),
                )
                expired_packets = cursor.fetchall()
                if not expired_packets:
                    return 0
                packet_ids = [p["packet_id"] for p in expired_packets]
                placeholders = ",".join(["%s"] * len(packet_ids))
                cursor.execute(
                    f"DELETE FROM red_packet_records WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
                cursor.execute(
                    f"DELETE FROM red_packets WHERE packet_id IN ({placeholders})",
                    tuple(packet_ids),
                )
            conn.commit()
            logger.info(f"已清理 {len(packet_ids)} 个过期红包")
            return len(packet_ids)
