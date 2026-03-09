-- 修复 shop_purchase_records 表结构
-- 如果 record_id 不是 AUTO_INCREMENT，需要重建表

-- 1. 备份数据
CREATE TABLE IF NOT EXISTS shop_purchase_records_backup AS SELECT * FROM shop_purchase_records;

-- 2. 删除旧表
DROP TABLE IF EXISTS shop_purchase_records;

-- 3. 创建新表（正确的结构）
CREATE TABLE shop_purchase_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 4. 恢复数据（如果有备份）
INSERT INTO shop_purchase_records (record_id, user_id, item_id, quantity, timestamp)
SELECT record_id, user_id, item_id, quantity, timestamp FROM shop_purchase_records_backup;

-- 5. 删除备份表
DROP TABLE IF EXISTS shop_purchase_records_backup;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_shop_purchase_user_item ON shop_purchase_records(user_id, item_id);
CREATE INDEX IF NOT EXISTS idx_shop_purchase_time ON shop_purchase_records(timestamp);
