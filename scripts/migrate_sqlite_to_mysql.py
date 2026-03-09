#!/usr/bin/env python3
"""SQLite -> MySQL migration tool for astrbot_plugin_fishing.

Features:
- Reads MySQL target from plugin config or CLI overrides
- Creates target database if missing
- Rebuilds table schema from SQLite metadata
- Migrates all data in batches
- Recreates indexes and foreign keys
- Verifies row counts table-by-table
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse


def resolve_default_sqlite_path() -> str:
    candidates = [
        "/opt/1panel/apps/astrbot/astrbot/data/plugin_data/astrbot_plugin_fishing/fish.db",
        "/opt/1panel/apps/astrbot/astrbot/data/fish.db",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def _require_pymysql():
    try:
        import pymysql  # type: ignore

        return pymysql
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency 'pymysql'. Install with: pip install pymysql"
        ) from exc


@dataclass
class MysqlTarget:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout: int = 10


def parse_mysql_url(url: str) -> MysqlTarget:
    parsed = urlparse(url)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise ValueError(f"Unsupported MySQL URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("MySQL URL missing hostname")
    if not parsed.username:
        raise ValueError("MySQL URL missing username")
    if not parsed.path or parsed.path == "/":
        raise ValueError("MySQL URL missing database name")

    return MysqlTarget(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username),
        password=unquote(parsed.password or ""),
        database=unquote(parsed.path.lstrip("/")),
    )


def load_target_from_config(config_path: str) -> Optional[MysqlTarget]:
    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)

    section = cfg.get("external_sql") or {}
    if not section:
        return None

    mysql_url = section.get("mysql_url", "").strip()
    if mysql_url:
        target = parse_mysql_url(mysql_url)
        target.charset = section.get("charset", target.charset)
        target.connect_timeout = int(
            section.get("connect_timeout", target.connect_timeout)
        )
        return target

    host = section.get("host", "").strip()
    user = section.get("user", "").strip()
    database = section.get("database", "").strip()
    password = section.get("password", "")
    if host and user and database:
        return MysqlTarget(
            host=host,
            port=int(section.get("port", 3306)),
            user=user,
            password=password,
            database=database,
            charset=section.get("charset", "utf8mb4"),
            connect_timeout=int(section.get("connect_timeout", 10)),
        )

    return None


def sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [row[0] for row in cur.fetchall()]


def q_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def map_sqlite_type(sqlite_type: str, col_name: str, indexed: bool = False) -> str:
    t = (sqlite_type or "").strip().upper()
    if t == "":
        return "LONGTEXT"

    # Handle INTEGER PRIMARY KEY specially - should be BIGINT AUTO_INCREMENT
    if t == "INTEGER":
        return "BIGINT"
    if "INT" in t and t != "INTEGER":
        return "BIGINT"
    if any(x in t for x in ("CHAR", "CLOB", "TEXT", "JSON")):
        if indexed:
            return "VARCHAR(255)"
        return "LONGTEXT"
    if "BLOB" in t:
        return "LONGBLOB"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE"
    if "DEC" in t or "NUM" in t:
        return "DECIMAL(38,10)"
    if "BOOL" in t:
        return "TINYINT(1)"
    if t == "TIME":
        return "TIME"
    if "DATE" in t and "TIME" not in t:
        return "DATE"
    if "TIME" in t:
        return "DATETIME"

    return "LONGTEXT"


def normalize_default(raw_default: Optional[str]) -> Optional[str]:
    if raw_default is None:
        return None

    d = raw_default.strip()
    if d == "":
        return None

    if d.startswith("(") and d.endswith(")"):
        d = d[1:-1].strip()

    upper = d.upper()
    if upper in {"CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "NULL"}:
        return d

    return d


def can_set_default(mysql_type: str) -> bool:
    upper = mysql_type.upper()
    if "TEXT" in upper or "BLOB" in upper or "JSON" in upper:
        return False
    return True


def build_create_table_sql(sqlite_conn: sqlite3.Connection, table: str) -> str:
    cur = sqlite_conn.cursor()
    cur.execute(f"PRAGMA table_info({q_ident(table)});")
    cols = cur.fetchall()
    if not cols:
        raise RuntimeError(f"No columns found for table: {table}")

    col_defs: List[str] = []
    pk_cols: List[Tuple[int, str]] = []

    indexed_cols = set()
    idx_rows = sqlite_conn.execute(f"PRAGMA index_list({q_ident(table)});").fetchall()
    for idx_row in idx_rows:
        idx_name = idx_row[1]
        idx_cols = sqlite_conn.execute(
            f"PRAGMA index_info({q_ident(idx_name)});"
        ).fetchall()
        for idx_col in idx_cols:
            indexed_cols.add(idx_col[2])

    fk_rows = sqlite_conn.execute(
        f"PRAGMA foreign_key_list({q_ident(table)});"
    ).fetchall()
    for fk_row in fk_rows:
        indexed_cols.add(fk_row[3])

    # Get autoincrement columns from SQLite
    autoincrement_cols = set()
    try:
        cur.execute("PRAGMA table_info(sqlite_sequence)")
        if cur.fetchall():  # Only if sqlite_sequence exists
            cur.execute("SELECT name FROM sqlite_sequence")
            # This won't work directly, need to check column definition
            pass
    except:
        pass

    for row_idx, (_, name, col_type, notnull, default, pk) in enumerate(cols):
        mysql_type = map_sqlite_type(
            col_type, name, indexed=(name in indexed_cols or int(pk) > 0)
        )
        parts = [q_ident(name), mysql_type]

        # Check if this column is AUTOINCREMENT in SQLite
        is_autoincrement = False
        if int(pk) > 0 and col_type and "AUTOINCREMENT" in col_type.upper():
            is_autoincrement = True
        # Also check by pattern: INTEGER PRIMARY KEY in SQLite implies ROWID alias
        if int(pk) > 0 and col_type and col_type.upper() == "INTEGER":
            is_autoincrement = True

        if int(notnull) == 1:
            parts.append("NOT NULL")
        if is_autoincrement:
            parts.append("AUTO_INCREMENT")
        default_norm = normalize_default(default)
        if default_norm is not None and can_set_default(mysql_type):
            parts.append(f"DEFAULT {default_norm}")
        if int(pk) > 0:
            pk_cols.append((int(pk), name))
        col_defs.append(" ".join(parts))

    constraints: List[str] = []
    if pk_cols:
        pk_cols_sorted = [q_ident(name) for _, name in sorted(pk_cols)]
        constraints.append(f"PRIMARY KEY ({', '.join(pk_cols_sorted)})")

    fk_map: Dict[int, List[sqlite3.Row]] = {}
    for row in fk_rows:
        fk_map.setdefault(int(row[0]), []).append(row)

    for fk_id, rows in sorted(fk_map.items(), key=lambda x: x[0]):
        rows_sorted = sorted(rows, key=lambda r: int(r[1]))
        ref_table = rows_sorted[0][2]
        from_cols = ", ".join(q_ident(r[3]) for r in rows_sorted)
        to_cols = ", ".join(q_ident(r[4]) for r in rows_sorted)
        on_update = rows_sorted[0][5]
        on_delete = rows_sorted[0][6]
        clause = (
            f"CONSTRAINT {q_ident('fk_' + table + '_' + str(fk_id))} "
            f"FOREIGN KEY ({from_cols}) REFERENCES {q_ident(ref_table)} ({to_cols})"
        )
        if on_update and on_update.upper() != "NO ACTION":
            clause += f" ON UPDATE {on_update}"
        if on_delete and on_delete.upper() != "NO ACTION":
            clause += f" ON DELETE {on_delete}"
        constraints.append(clause)

    all_defs = col_defs + constraints
    return (
        f"CREATE TABLE {q_ident(table)} (\n  "
        + ",\n  ".join(all_defs)
        + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
    )


def build_index_sqls(sqlite_conn: sqlite3.Connection, table: str) -> List[str]:
    idx_rows = sqlite_conn.execute(f"PRAGMA index_list({q_ident(table)});").fetchall()
    sqls: List[str] = []
    for row in idx_rows:
        idx_name = row[1]
        unique = int(row[2]) == 1
        origin = row[3] if len(row) > 3 else None
        if origin == "pk":
            continue

        cols = sqlite_conn.execute(
            f"PRAGMA index_info({q_ident(idx_name)});"
        ).fetchall()
        col_names = [q_ident(c[2]) for c in sorted(cols, key=lambda c: int(c[0]))]
        if not col_names:
            continue

        mysql_idx_name = idx_name[:60] if len(idx_name) > 60 else idx_name
        prefix = "UNIQUE INDEX" if unique else "INDEX"
        sqls.append(
            f"CREATE {prefix} {q_ident(mysql_idx_name)} ON {q_ident(table)} ({', '.join(col_names)});"
        )
    return sqls


def batched(
    iterable: Sequence[sqlite3.Row], size: int
) -> Iterable[Sequence[sqlite3.Row]]:
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def fetch_table_count(conn, table: str, is_sqlite: bool) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {q_ident(table)}")
    row = cur.fetchone()
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    return int(row[0])


def migrate(
    sqlite_path: str,
    target: MysqlTarget,
    batch_size: int,
    drop_existing: bool,
    skip_schema: bool,
    skip_data: bool,
) -> None:
    pymysql = _require_pymysql()

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    mysql_admin = pymysql.connect(
        host=target.host,
        port=target.port,
        user=target.user,
        password=target.password,
        charset=target.charset,
        connect_timeout=target.connect_timeout,
        autocommit=True,
    )
    with mysql_admin.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {q_ident(target.database)} "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    mysql_admin.close()

    mysql_conn = pymysql.connect(
        host=target.host,
        port=target.port,
        user=target.user,
        password=target.password,
        database=target.database,
        charset=target.charset,
        connect_timeout=target.connect_timeout,
        autocommit=False,
    )

    try:
        tables = sqlite_tables(sqlite_conn)
        if not tables:
            raise RuntimeError("No tables found in SQLite source database")

        print(f"Found {len(tables)} tables in SQLite source")
        with mysql_conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")

        if not skip_schema:
            for table in tables:
                print(f"[schema] {table}")
                create_sql = build_create_table_sql(sqlite_conn, table)
                with mysql_conn.cursor() as cur:
                    if drop_existing:
                        cur.execute(f"DROP TABLE IF EXISTS {q_ident(table)}")
                    cur.execute(create_sql)
                    for idx_sql in build_index_sqls(sqlite_conn, table):
                        cur.execute(idx_sql)
            mysql_conn.commit()

        if not skip_data:
            for table in tables:
                print(f"[data] {table}")
                src_cur = sqlite_conn.cursor()
                src_cur.execute(f"SELECT * FROM {q_ident(table)}")
                col_names = [d[0] for d in src_cur.description]
                if not col_names:
                    continue

                placeholders = ", ".join(["%s"] * len(col_names))
                cols_sql = ", ".join(q_ident(c) for c in col_names)
                insert_sql = (
                    f"INSERT INTO {q_ident(table)} ({cols_sql}) VALUES ({placeholders})"
                )

                total = 0
                while True:
                    rows = src_cur.fetchmany(batch_size)
                    if not rows:
                        break
                    payload = [tuple(row[c] for c in col_names) for row in rows]
                    with mysql_conn.cursor() as cur:
                        cur.executemany(insert_sql, payload)
                    total += len(payload)
                mysql_conn.commit()
                print(f"  inserted {total} rows")

        # Verify row counts
        print("[verify] row counts")
        for table in tables:
            src_count = fetch_table_count(sqlite_conn, table, is_sqlite=True)
            dst_count = fetch_table_count(mysql_conn, table, is_sqlite=False)
            status = "OK" if src_count == dst_count else "MISMATCH"
            print(f"  {table}: src={src_count}, dst={dst_count} -> {status}")
            if src_count != dst_count:
                raise RuntimeError(f"Row count mismatch for table: {table}")

        with mysql_conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        mysql_conn.commit()

        print("Migration completed successfully.")
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        mysql_conn.close()


def build_target(args: argparse.Namespace) -> MysqlTarget:
    config_target = load_target_from_config(args.config)

    if args.mysql_url:
        target = parse_mysql_url(args.mysql_url)
    elif config_target:
        target = config_target
    else:
        raise RuntimeError(
            "MySQL target is missing. Provide --mysql-url or set external_sql in config."
        )

    if args.mysql_host:
        target.host = args.mysql_host
    if args.mysql_port:
        target.port = args.mysql_port
    if args.mysql_user:
        target.user = args.mysql_user
    if args.mysql_password is not None:
        target.password = args.mysql_password
    if args.mysql_database:
        target.database = args.mysql_database
    if args.mysql_charset:
        target.charset = args.mysql_charset
    if args.mysql_connect_timeout:
        target.connect_timeout = args.mysql_connect_timeout

    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate fishing SQLite database to MySQL"
    )
    parser.add_argument(
        "--sqlite",
        default=resolve_default_sqlite_path(),
        help="Path to SQLite source database",
    )
    parser.add_argument(
        "--config",
        default="/opt/1panel/apps/astrbot/astrbot/data/config/astrbot_plugin_fishing_config.json",
        help="Path to fishing plugin config JSON",
    )
    parser.add_argument(
        "--mysql-url", default="", help="MySQL URL, e.g. mysql://user:pass@host:3306/db"
    )
    parser.add_argument("--mysql-host", default="")
    parser.add_argument("--mysql-port", type=int, default=0)
    parser.add_argument("--mysql-user", default="")
    parser.add_argument("--mysql-password", default=None)
    parser.add_argument("--mysql-database", default="")
    parser.add_argument("--mysql-charset", default="")
    parser.add_argument("--mysql-connect-timeout", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--no-drop-existing", action="store_true", help="Do not drop target tables"
    )
    parser.add_argument("--skip-schema", action="store_true")
    parser.add_argument("--skip-data", action="store_true")

    args = parser.parse_args()

    try:
        target = build_target(args)
        print("Target MySQL:")
        print(
            f"  host={target.host} port={target.port} db={target.database} user={target.user}"
        )

        migrate(
            sqlite_path=args.sqlite,
            target=target,
            batch_size=args.batch_size,
            drop_existing=not args.no_drop_existing,
            skip_schema=args.skip_schema,
            skip_data=args.skip_data,
        )
        return 0
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
