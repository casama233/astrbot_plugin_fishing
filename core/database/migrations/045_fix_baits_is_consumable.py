import sqlite3
from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """
    修复鱼饵 is_consumable 字段：
    - 亮片拟饵 (bait_id=5): is_consumable = 0 (可重复使用)
    - 大师拟饵 (bait_id=11): is_consumable = 0 (可重复使用)
    """
    logger.info("正在执行 045_fix_baits_is_consumable: 修复鱼饵消耗属性...")

    # 亮片拟饵 bait_id=5
    cursor.execute(
        "UPDATE baits SET is_consumable = 0 WHERE bait_id = 5 AND name = '亮片拟饵'"
    )
    logger.info(f"已更新 bait_id=5 (亮片拟饵) is_consumable = 0")

    # 大师拟饵 bait_id=11
    cursor.execute(
        "UPDATE baits SET is_consumable = 0 WHERE bait_id = 11 AND name = '大师拟饵'"
    )
    logger.info(f"已更新 bait_id=11 (大师拟饵) is_consumable = 0")

    logger.info("鱼饵消耗属性修复完成。")


def down(cursor: sqlite3.Cursor):
    """
    回滚：将亮片拟饵和大师拟饵恢复为消耗品
    """
    logger.info("正在回滚 045_fix_baits_is_consumable...")

    cursor.execute(
        "UPDATE baits SET is_consumable = 1 WHERE bait_id = 5 AND name = '亮片拟饵'"
    )
    cursor.execute(
        "UPDATE baits SET is_consumable = 1 WHERE bait_id = 11 AND name = '大师拟饵'"
    )

    logger.info("已回滚鱼饵消耗属性。")
