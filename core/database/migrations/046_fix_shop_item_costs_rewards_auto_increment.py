"""修復 MySQL shop_item_costs 和 shop_item_rewards 表的 AUTO_INCREMENT 問題"""

import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    SQLite 版本不需要修改（已正確設置 AUTOINCREMENT）
    此遷移主要用於 MySQL 環境
    """
    pass


def down(cursor: sqlite3.Cursor):
    """回滾"""
    pass


# MySQL 修復 SQL（供手動執行）:
"""
-- 修復 shop_item_costs 表
ALTER TABLE shop_item_costs
MODIFY COLUMN cost_id INT AUTO_INCREMENT PRIMARY KEY;

-- 如果表不存在，創建表：
CREATE TABLE IF NOT EXISTS shop_item_costs (
    cost_id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    cost_type VARCHAR(50) NOT NULL,
    cost_amount INT NOT NULL,
    cost_item_id INT,
    cost_relation VARCHAR(10) DEFAULT 'and',
    group_id INT,
    quality_level INT DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
    CHECK (cost_type IN ('coins','premium','item','fish')),
    CHECK (cost_amount > 0),
    CHECK (cost_relation IN ('and', 'or'))
);

-- 創建索引：
CREATE INDEX IF NOT EXISTS idx_shop_item_costs_item ON shop_item_costs(item_id);
CREATE INDEX IF NOT EXISTS idx_shop_item_costs_type ON shop_item_costs(cost_type);
CREATE INDEX IF NOT EXISTS idx_shop_item_costs_relation ON shop_item_costs(cost_relation);
CREATE INDEX IF NOT EXISTS idx_shop_item_costs_group ON shop_item_costs(group_id);


-- 修復 shop_item_rewards 表
ALTER TABLE shop_item_rewards
MODIFY COLUMN reward_id INT AUTO_INCREMENT PRIMARY KEY;

-- 如果表不存在，創建表：
CREATE TABLE IF NOT EXISTS shop_item_rewards (
    reward_id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    reward_type VARCHAR(50) NOT NULL,
    reward_item_id INT,
    reward_quantity INT NOT NULL DEFAULT 1,
    reward_refine_level INT,
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
    CHECK (reward_type IN ('rod','accessory','bait','item','fish','coins')),
    CHECK (reward_quantity > 0)
);

-- 創建索引：
CREATE INDEX IF NOT EXISTS idx_shop_item_rewards_item ON shop_item_rewards(item_id);
CREATE INDEX IF NOT EXISTS idx_shop_item_rewards_type ON shop_item_rewards(reward_type);
"""
