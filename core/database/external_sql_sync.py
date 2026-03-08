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
                "connect_timeout": int(self.config.get("connect_timeout", 10)),
                "autocommit": False,
            }

        host = str(self.config.get("host", "")).strip()
        user = str(self.config.get("user", "")).strip()
        database = str(self.config.get("database", "")).strip()
        if not host or not user or not database:
            raise ValueError(
                "external_sql enabled but host/user/database or mysql_url is missing"
            )

        return {
            "host": host,
            "port": int(self.config.get("port", 3306)),
            "user": user,
            "password": self.config.get("password", ""),
            "database": database,
            "charset": self.config.get("charset", "utf8mb4"),
            "connect_timeout": int(self.config.get("connect_timeout", 10)),
            "autocommit": False,
        }

    @staticmethod
    def _q_ident(name: str) -> str:
        return "`" + name.replace("`", "``") + "`"

    @staticmethod
    def _to_sqlite_value(v: Any) -> Any:
        if isinstance(v, datetime.timedelta):
            total = int(v.total_seconds())
            sign = "-" if total < 0 else ""
            total = abs(total)
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f"{sign}{h:02d}:{m:02d}:{s:02d}"
        if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            return (
                v.isoformat(sep=" ")
                if isinstance(v, datetime.datetime)
                else v.isoformat()
            )
        return v

    def _sqlite_tables(self, conn: sqlite3.Connection) -> List[str]:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        return [row[0] for row in cur.fetchall()]

    def _mysql_has_table(self, mysql_conn, table: str) -> bool:
        with mysql_conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE %s", (table,))
            return cur.fetchone() is not None

    def _copy_mysql_to_sqlite(self) -> None:
        pymysql = self._require_pymysql()
        mysql_conn = pymysql.connect(**self._mysql_connect_kwargs())
        sqlite_conn = sqlite3.connect(self.sqlite_path)

        try:
            sqlite_conn.execute("PRAGMA foreign_keys = OFF")
            tables = self._sqlite_tables(sqlite_conn)

            for table in tables:
                if not self._mysql_has_table(mysql_conn, table):
                    logger.warning(
                        f"[external_sql] MySQL table missing, skip pull: {table}"
                    )
                    continue

                sqlite_cols = [
                    row[1]
                    for row in sqlite_conn.execute(
                        f"PRAGMA table_info({self._q_ident(table)})"
                    ).fetchall()
                ]
                if not sqlite_cols:
                    continue

                cols_sql = ", ".join(self._q_ident(c) for c in sqlite_cols)
                placeholders = ", ".join(["?"] * len(sqlite_cols))
                sqlite_conn.execute(f"DELETE FROM {self._q_ident(table)}")

                total = 0
                with mysql_conn.cursor() as cur:
                    cur.execute(f"SELECT {cols_sql} FROM {self._q_ident(table)}")
                    while True:
                        rows = cur.fetchmany(2000)
                        if not rows:
                            break
                        sqlite_conn.executemany(
                            f"INSERT INTO {self._q_ident(table)} ({cols_sql}) VALUES ({placeholders})",
                            [
                                tuple(self._to_sqlite_value(x) for x in row)
                                for row in rows
                            ],
                        )
                        total += len(rows)
                logger.info(f"[external_sql] pulled {table}: {total} rows")

            sqlite_conn.commit()
            logger.info("[external_sql] mysql -> sqlite startup sync completed")
        finally:
            try:
                sqlite_conn.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
            sqlite_conn.close()
            mysql_conn.close()

    def _copy_sqlite_to_mysql(self) -> None:
        pymysql = self._require_pymysql()
        mysql_conn = pymysql.connect(**self._mysql_connect_kwargs())
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        try:
            with mysql_conn.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS=0")

            tables = self._sqlite_tables(sqlite_conn)
            for table in tables:
                if not self._mysql_has_table(mysql_conn, table):
                    logger.warning(
                        f"[external_sql] MySQL table missing, skip push: {table}"
                    )
                    continue

                src_cur = sqlite_conn.cursor()
                src_cur.execute(f"SELECT * FROM {self._q_ident(table)}")
                col_names = [d[0] for d in src_cur.description]
                if not col_names:
                    continue

                cols_sql = ", ".join(self._q_ident(c) for c in col_names)
                placeholders = ", ".join(["%s"] * len(col_names))
                insert_sql = f"INSERT INTO {self._q_ident(table)} ({cols_sql}) VALUES ({placeholders})"

                with mysql_conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {self._q_ident(table)}")

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
