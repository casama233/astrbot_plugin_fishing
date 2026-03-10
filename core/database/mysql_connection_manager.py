from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from typing import Any, Dict
from urllib.parse import unquote, urlparse

from astrbot.api import logger


class MysqlConnectionManager:
    _auto_increment_fixed = False

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self._local = threading.local()

    def _require_pymysql(self):
        try:
            import pymysql  # type: ignore

            return pymysql
        except Exception as exc:
            raise RuntimeError(
                "MySQL backend requires pymysql. Install with: pip install pymysql"
            ) from exc

    def _connect_kwargs(self) -> Dict[str, Any]:
        mysql_url = str(self.config.get("mysql_url", "")).strip()
        if mysql_url:
            parsed = urlparse(mysql_url)
            if parsed.scheme not in {"mysql", "mysql+pymysql"}:
                raise ValueError(f"Unsupported mysql_url scheme: {parsed.scheme}")
            if not parsed.hostname or not parsed.username or not parsed.path:
                raise ValueError("Invalid mysql_url in config")
            return {
                "host": parsed.hostname,
                "port": parsed.port or 3306,
                "user": unquote(parsed.username),
                "password": unquote(parsed.password or ""),
                "database": unquote(parsed.path.lstrip("/")),
                "charset": self.config.get("charset", "utf8mb4"),
                "connect_timeout": int(self.config.get("connect_timeout", 10)),
                "read_timeout": int(self.config.get("read_timeout", 30)),
                "write_timeout": int(self.config.get("write_timeout", 30)),
            }

        host = str(self.config.get("host", "")).strip()
        user = str(self.config.get("user", "")).strip()
        database = str(self.config.get("database", "")).strip()
        if not host or not user or not database:
            raise ValueError("MySQL backend missing host/user/database or mysql_url")

        return {
            "host": host,
            "port": int(self.config.get("port", 3306)),
            "user": user,
            "password": self.config.get("password", ""),
            "database": database,
            "charset": self.config.get("charset", "utf8mb4"),
            "connect_timeout": int(self.config.get("connect_timeout", 10)),
            "read_timeout": int(self.config.get("read_timeout", 30)),
            "write_timeout": int(self.config.get("write_timeout", 30)),
        }

    def _get_connection(self):
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            try:
                conn.ping(reconnect=True)
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                if hasattr(self._local, "connection"):
                    delattr(self._local, "connection")

        if conn is None or not hasattr(self._local, "connection"):
            pymysql = self._require_pymysql()
            conn = pymysql.connect(
                **self._connect_kwargs(),
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self._local.connection = conn
            self._fix_auto_increment_once()
        return conn

    def _fix_auto_increment_once(self):
        """修復所有 MySQL 表的 AUTO_INCREMENT 問題（只執行一次）"""
        if MysqlConnectionManager._auto_increment_fixed:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._fix_auto_increment_sync)
        except RuntimeError:
            import threading

            thread = threading.Thread(target=self._fix_auto_increment_sync, daemon=True)
            thread.start()

    def _fix_auto_increment_sync(self):
        """同步執行數據庫結構修復（運行在線程池中）"""
        if MysqlConnectionManager._auto_increment_fixed:
            return

        tables_to_fix = {
            "shop_item_costs": "cost_id",
            "shop_item_rewards": "reward_id",
            "shop_purchase_records": "record_id",
            "exchange_prices": "price_id",
            "user_item_usage_logs": "id",
            "user_fish_pond": "fish_id",
            "shops": "shop_id",
            "shop_items": "item_id",
            "gacha_records": "record_id",
            "market_listings": "listing_id",
            "red_packets": "packet_id",
            "red_packet_claims": "claim_id",
            "user_achievements": "achievement_id",
            "user_buffs": "buff_id",
            "user_titles": "title_id",
            "user_accessories": "accessory_id",
            "user_baits": "bait_id",
            "user_items": "item_id",
            "user_rods": "rod_id",
        }

        columns_to_add = {
            "baits": [
                ("weight_modifier", "REAL", "DEFAULT 1.0"),
                ("is_consumable", "BOOLEAN", "DEFAULT 1"),
            ],
            "rods": [
                ("weight_modifier", "REAL", "DEFAULT 1.0"),
            ],
            "accessories": [
                ("weight_modifier", "REAL", "DEFAULT 1.0"),
            ],
            "users": [
                ("current_title_id", "INTEGER", "DEFAULT NULL"),
                ("show_suggestions", "BOOLEAN", "DEFAULT 1"),
                ("zone_pass_expires_at", "DATETIME", "DEFAULT NULL"),
            ],
            "shop_item_costs": [
                ("quality_level", "INTEGER", "DEFAULT 0"),
            ],
            "fishing_zones": [
                ("pass_duration_hours", "INTEGER", "DEFAULT NULL"),
            ],
        }

        conn = None
        try:
            pymysql = self._require_pymysql()
            conn = pymysql.connect(
                **self._connect_kwargs(),
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
            with conn.cursor() as cursor:
                for table_name, pk_column in tables_to_fix.items():
                    try:
                        cursor.execute(
                            """
                            SELECT COLUMN_NAME, EXTRA 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = %s 
                            AND COLUMN_NAME = %s
                            """,
                            (table_name, pk_column),
                        )
                        row = cursor.fetchone()
                        if (
                            row
                            and "auto_increment"
                            not in str(row.get("EXTRA", "")).lower()
                        ):
                            cursor.execute(
                                f"ALTER TABLE {table_name} MODIFY COLUMN {pk_column} INT AUTO_INCREMENT PRIMARY KEY"
                            )
                            logger.info(
                                f"已修复表 {table_name}.{pk_column} 的 AUTO_INCREMENT"
                            )
                    except Exception as e:
                        pass

                for table_name, columns in columns_to_add.items():
                    for col_name, col_type, col_default in columns:
                        try:
                            cursor.execute(
                                """
                                SELECT COLUMN_NAME 
                                FROM INFORMATION_SCHEMA.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = %s 
                                AND COLUMN_NAME = %s
                                """,
                                (table_name, col_name),
                            )
                            if not cursor.fetchone():
                                cursor.execute(
                                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {col_default}"
                                )
                                logger.info(f"已为表 {table_name} 添加列 {col_name}")
                        except Exception as e:
                            pass

                conn.commit()
            MysqlConnectionManager._auto_increment_fixed = True
        except Exception as e:
            logger.warning(f"检查数据库结构时发生错误: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @contextmanager
    def get_connection(self):
        conn = self._get_connection()
        try:
            try:
                conn.ping(reconnect=True)
            except Exception:
                if hasattr(self._local, "connection"):
                    delattr(self._local, "connection")
                conn = self._get_connection()
            yield conn
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            if hasattr(self._local, "connection"):
                delattr(self._local, "connection")
            logger.error(f"MySQL operation failed: {exc}")
            raise

    def close_connection(self):
        if hasattr(self._local, "connection"):
            try:
                self._local.connection.close()
            except Exception:
                pass
            finally:
                delattr(self._local, "connection")
