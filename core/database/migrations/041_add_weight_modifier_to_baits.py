import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    應用此遷移：為 baits 表添加 weight_modifier 列。
    """
    logger.info("正在執行 041_add_weight_modifier_to_baits: 為 baits 表添加 weight_modifier 列...")

    try:
        cursor.execute("ALTER TABLE baits ADD COLUMN weight_modifier REAL DEFAULT 1.0")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.debug("列 'weight_modifier' 已存在，跳過添加。")
        else:
            raise e

    # 更新巨物誘餌的重量加成
    cursor.execute("UPDATE baits SET weight_modifier = 1.2 WHERE name = '巨物誘餌'")

def down(cursor: sqlite3.Cursor):
    # SQLite 不支持 ALTER TABLE DROP COLUMN (在較舊版本中)
    pass
