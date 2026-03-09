import asyncio
import datetime
import sqlite3
from typing import Any, Dict, List, Optional

from astrbot.api import logger


class ExternalSqlSyncManager:
    def __init__(self, sqlite_path: str, config: Dict[str, Any]):
        self.sqlite_path = sqlite_path
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", False))
        self.sync_on_startup = bool(self.config.get("sync_on_startup", True))
        self.sync_interval_seconds = int(self.config.get("sync_interval_seconds", 300))
        self.startup_direction = (
            str(self.config.get("startup_direction", "mysql_to_sqlite")).strip().lower()
        )
        self.fail_fast_on_startup = bool(self.config.get("fail_fast_on_startup", False))
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def _require_pymysql(self):
        try:
            import pymysql  # type: ignore

            return pymysql
        except Exception as exc:
            raise RuntimeError(
                "external_sql.enabled=true but pymysql is unavailable. "
                "Install dependency: pip install pymysql"
            ) from exc

    def _mysql_connect_kwargs(self) -> Dict[str, Any]:
        mysql_url = str(self.config.get("mysql_url", "")).strip()
        if mysql_url:
            from urllib.parse import unquote, urlparse

            parsed = urlparse(mysql_url)
            if parsed.scheme not in {"mysql", "mysql+pymysql"}:
                raise ValueError(f"Unsupported mysql_url scheme: {parsed.scheme}")
            if not parsed.hostname or not parsed.username or not parsed.path:
                raise ValueError("Invalid mysql_url in external_sql config")
            return {
                "host": parsed.hostname,
                "port": parsed.port or 3306,
                "user": unquote(parsed.username),
                "password": unquote(parsed.password or ""),
                "database": unquote(parsed.path.lstrip("/")),
                "charset": self.config.get("charset", "utf8mb4"),
            }
        return {
            "host": self.config.get("host", "localhost"),
            "port": self.config.get("port", 3306),
            "user": self.config.get("user", "root"),
            "password": self.config.get("password", ""),
            "database": self.config.get("database", "astrbot"),
            "charset": self.config.get("charset", "utf8mb4"),
        }

    def _get_tables(self, cursor) -> List[str]:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [
            r[0]
            for r in cursor.fetchall()
            if not r[0].startswith("sqlite_") and r[0] != "schema_version"
        ]

    def _q_ident(self, ident: str) -> str:
        return f"`{ident}`"

    def _copy_sqlite_to_mysql(self):
        pymysql = self._require_pymysql()
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        mysql_conn = pymysql.connect(**self._mysql_connect_kwargs())
        try:
            src_cur = sqlite_conn.cursor()
            tables = self._get_tables(src_cur)

            with mysql_conn.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS=0")

            for table in tables:
                src_cur.execute(f"SELECT * FROM {table} LIMIT 1")
                col_names = [d[0] for d in src_cur.description]
                placeholders = ", ".join(["%s"] * len(col_names))
                cols_str = ", ".join([self._q_ident(c) for c in col_names])
                insert_sql = (
                    f"INSERT INTO {self._q_ident(table)} ({cols_str}) "
                    f"VALUES ({placeholders})"
                )

                src_cur.execute(f"SELECT * FROM {table}")
                with mysql_conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE {self._q_ident(table)}")

                total = 0
                while True:
                    rows = src_cur.fetchmany(2000)
                    if not rows:
                        break
                    payload = [tuple(row[c] for c in col_names) for row in rows]
                    with mysql_conn.cursor() as cur:
                        cur.executemany(insert_sql, payload)
                        total += len(payload)
                        logger.info(f"[external_sql] pushed {table}: {total} rows")

            with mysql_conn.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
            mysql_conn.commit()
            logger.info("[external_sql] sqlite -> mysql sync completed")
        except Exception:
            mysql_conn.rollback()
            raise
        finally:
            mysql_conn.close()
            sqlite_conn.close()

    def _copy_mysql_to_sqlite(self):
        pymysql = self._require_pymysql()
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        mysql_conn = pymysql.connect(**self._mysql_connect_kwargs())
        try:
            with mysql_conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = [r[0] for r in cur.fetchall()]

            for table in tables:
                if table.startswith("sqlite_") or table == "schema_version":
                    continue
                with mysql_conn.cursor() as cur:
                    cur.execute(f"SELECT * FROM {self._q_ident(table)}")
                    col_names = [d[0] for d in cur.description]
                    placeholders = ", ".join(["?"] * len(col_names))
                    cols_str = ", ".join([f'"{c}"' for c in col_names])
                    insert_sql = (
                        f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"
                    )

                    rows = cur.fetchall()
                    sqlite_conn.execute(f"DELETE FROM {table}")
                    sqlite_conn.executemany(insert_sql, rows)
                    logger.info(f"[external_sql] pulled {table}: {len(rows)} rows")

            sqlite_conn.commit()
            logger.info("[external_sql] mysql -> sqlite sync completed")
        except Exception:
            sqlite_conn.rollback()
            raise
        finally:
            mysql_conn.close()
            sqlite_conn.close()

    def startup_sync(self):
        if not self.enabled or not self.sync_on_startup:
            return
        try:
            if self.startup_direction == "sqlite_to_mysql":
                logger.info("[external_sql] startup sync: sqlite -> mysql")
                self._copy_sqlite_to_mysql()
            else:
                logger.info("[external_sql] startup sync: mysql -> sqlite")
                self._copy_mysql_to_sqlite()
        except Exception as e:
            logger.error(f"[external_sql] startup sync failed: {e}")
            if self.fail_fast_on_startup:
                raise

    async def sync_once_async(self):
        if not self.enabled:
            return
        async with self._lock:
            await asyncio.to_thread(self._copy_sqlite_to_mysql)

    async def _loop(self):
        while True:
            try:
                await self.sync_once_async()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[external_sql] periodic sync failed: {e}")
            await asyncio.sleep(max(self.sync_interval_seconds, 30))

    def start_periodic_sync(self):
        if not self.enabled:
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("[external_sql] periodic sync task started")

    async def stop(self):
        if not self.enabled:
            return
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        try:
            await self.sync_once_async()
        except Exception as e:
            logger.error(f"[external_sql] final sync failed: {e}")
