from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Dict
from urllib.parse import unquote, urlparse

from astrbot.api import logger


class MysqlConnectionManager:
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
        }

    def _get_connection(self):
        conn = getattr(self._local, "connection", None)
        if conn is None:
            pymysql = self._require_pymysql()
            conn = pymysql.connect(
                **self._connect_kwargs(),
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self._local.connection = conn
        return conn

    @contextmanager
    def get_connection(self):
        conn = self._get_connection()
        try:
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
