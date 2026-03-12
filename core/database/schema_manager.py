from astrbot.api import logger
from .mysql_connection_manager import MysqlConnectionManager


def ensure_mysql_runtime_schema(config: dict) -> None:
    """
    MySQL 模式下的輕量運行時自修復，避免 SQLite 遷移鏈影響。
    """
    manager = MysqlConnectionManager(config)
    with manager.get_connection() as conn:
        with conn.cursor() as cursor:
            _repair_user_items_table(cursor)
            _repair_user_buffs_table(cursor)
            _create_exchange_tables(cursor)
            _insert_default_commodities(cursor)
            conn.commit()


def _repair_user_items_table(cursor) -> None:
    cursor.execute("SHOW TABLES LIKE 'user_items'")
    if not cursor.fetchone():
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_items (
                user_id VARCHAR(255) NOT NULL,
                item_id BIGINT NOT NULL,
                quantity BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, item_id),
                KEY idx_user_items_item_id (item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        return

    cursor.execute("SHOW COLUMNS FROM user_items")
    columns = {row["Field"]: row for row in cursor.fetchall()}
    cursor.execute("SHOW INDEX FROM user_items")
    indexes = cursor.fetchall()

    has_composite_primary_key = False
    primary_key_columns = [
        row["Column_name"] for row in indexes if row.get("Key_name") == "PRIMARY"
    ]
    if primary_key_columns == ["user_id", "item_id"]:
        has_composite_primary_key = True

    has_unique_user_item = any(
        row.get("Key_name") != "PRIMARY"
        and row.get("Non_unique") == 0
        and row.get("Column_name") == "user_id"
        for row in indexes
    ) and any(
        row.get("Key_name") != "PRIMARY"
        and row.get("Non_unique") == 0
        and row.get("Column_name") == "item_id"
        for row in indexes
    )

    needs_rebuild = (
        "id" in columns
        or "user_id" not in columns
        or "item_id" not in columns
        or "quantity" not in columns
        or not (has_composite_primary_key or has_unique_user_item)
    )

    if not needs_rebuild:
        return

    logger.warning("檢測到 MySQL 表 user_items 結構異常，正在自動修復為複合主鍵結構。")
    cursor.execute("DROP TABLE IF EXISTS user_items_repaired")
    cursor.execute(
        """
        CREATE TABLE user_items_repaired (
            user_id VARCHAR(255) NOT NULL,
            item_id BIGINT NOT NULL,
            quantity BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item_id),
            KEY idx_user_items_item_id (item_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        INSERT INTO user_items_repaired (user_id, item_id, quantity)
        SELECT user_id, item_id, GREATEST(0, COALESCE(SUM(quantity), 0))
        FROM user_items
        GROUP BY user_id, item_id
        ON DUPLICATE KEY UPDATE quantity = VALUES(quantity)
        """
    )
    cursor.execute("DROP TABLE user_items")
    cursor.execute("RENAME TABLE user_items_repaired TO user_items")


def _repair_user_buffs_table(cursor) -> None:
    cursor.execute("SHOW TABLES LIKE 'user_buffs'")
    if not cursor.fetchone():
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_buffs (
                id BIGINT NOT NULL AUTO_INCREMENT,
                user_id VARCHAR(255) NOT NULL,
                buff_type VARCHAR(255) NOT NULL,
                payload LONGTEXT,
                started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NULL,
                PRIMARY KEY (id),
                KEY idx_user_buffs_user_id (user_id),
                KEY idx_user_buffs_expires_at (expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        return

    cursor.execute("SHOW COLUMNS FROM user_buffs")
    columns = {row["Field"]: row for row in cursor.fetchall()}
    id_column = columns.get("id")
    extra = str((id_column or {}).get("Extra", "")).lower()

    if id_column and "auto_increment" in extra:
        return

    logger.warning(
        "檢測到 MySQL 表 user_buffs 的 id 不是 AUTO_INCREMENT，正在嘗試輕量修復。"
    )

    if id_column:
        cursor.execute(
            """
            ALTER TABLE user_buffs
            MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT
            """
        )
        return

    cursor.execute(
        """
        ALTER TABLE user_buffs
        ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST
        """
    )


def _create_exchange_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS commodities (
            commodity_id VARCHAR(255) PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS exchange_prices (
            price_id BIGINT NOT NULL AUTO_INCREMENT,
            date VARCHAR(255) NOT NULL,
            time LONGTEXT NOT NULL,
            commodity_id VARCHAR(255) NOT NULL,
            price BIGINT NOT NULL,
            update_type LONGTEXT,
            created_at VARCHAR(255) NOT NULL,
            PRIMARY KEY (price_id),
            KEY idx_exchange_prices_created_at (created_at),
            KEY idx_exchange_prices_date_commodity (date(100), commodity_id(100)),
            CONSTRAINT fk_exchange_prices_0 FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS check_ins (
            user_id VARCHAR(255) NOT NULL,
            check_in_date DATE NOT NULL,
            PRIMARY KEY (user_id, check_in_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    cursor.execute("SHOW TABLES LIKE 'exchange_prices_new'")
    if cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO exchange_prices (date, time, commodity_id, price, update_type, created_at)
            SELECT n.date, n.time, n.commodity_id, n.price, n.update_type, n.created_at
            FROM exchange_prices_new n
            LEFT JOIN exchange_prices e
            ON e.date = n.date
            AND e.time = n.time
            AND e.commodity_id = n.commodity_id
            WHERE e.price_id IS NULL
            """
        )
        cursor.execute("DROP TABLE exchange_prices_new")


def _insert_default_commodities(cursor) -> None:
    cursor.execute(
        """
        INSERT INTO commodities (commodity_id, name, description) VALUES
        ('dried_fish', '魚乾', '穩健型標的，價格波動低'),
        ('fish_roe', '魚卵', '高風險標的，價格波動極大'),
        ('fish_oil', '魚油', '投機品，有概率觸發事件導致價格大幅漲跌'),
        ('fish_bone', '魚骨', '堅硬的魚骨，保質期長，價格最穩定，適合長期持有'),
        ('fish_scale', '魚鱗', '閃亮的魚鱗，中等保質期，價格波動適中，平衡之選'),
        ('fish_sauce', '魚露', '發酵的魚露，極短保質期，價格劇烈波動，僅供高手')
        ON DUPLICATE KEY UPDATE
        name = VALUES(name), description = VALUES(description)
        """
    )
