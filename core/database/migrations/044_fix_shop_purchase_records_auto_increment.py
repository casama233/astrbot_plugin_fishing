"""修復 MySQL shop_purchase_records 表的 record_id AUTO_INCREMENT 問題"""

import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    SQLite 版本不需要修改（已正確設置 AUTOINCREMENT）
    此遷移主要用於 MySQL 環境
    """
    # SQLite 的表結構已經正確，無需修改
    # 在 MySQL 環境中，需要執行以下 SQL：
    # ALTER TABLE shop_purchase_records MODIFY COLUMN record_id INT AUTO_INCREMENT PRIMARY KEY;
    pass


def down(cursor: sqlite3.Cursor):
    """回滾"""
    pass


# MySQL 修復 SQL（供手動執行）:
"""
-- 如果使用 MySQL，請執行以下 SQL 修復表結構：

ALTER TABLE shop_purchase_records 
MODIFY COLUMN record_id INT AUTO_INCREMENT PRIMARY KEY,
MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;

-- 如果表不存在，創建表：
CREATE TABLE IF NOT EXISTS shop_purchase_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 創建索引：
CREATE INDEX IF NOT EXISTS idx_shop_purchase_user_item ON shop_purchase_records(user_id, item_id);
CREATE INDEX IF NOT EXISTS idx_shop_purchase_time ON shop_purchase_records(timestamp);
"""
