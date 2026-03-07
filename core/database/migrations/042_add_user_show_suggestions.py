import sqlite3
from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    logger.info(
        "正在執行 042_add_user_show_suggestions: 為 users 表添加 show_suggestions 列..."
    )
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN show_suggestions INTEGER DEFAULT 1"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.debug("列 'show_suggestions' 已存在，跳過添加。")
        else:
            raise e


def down(cursor: sqlite3.Cursor):
    pass
