import sqlite3

from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """添加新的交易所商品：魚骨、魚鱗、魚露"""
    logger.info("正在執行 043_add_new_exchange_commodities: 添加新的交易所商品...")

    # 檢查 commodities 表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='commodities'"
    )
    if not cursor.fetchone():
        logger.warning("commodities 表不存在，跳過遷移")
        return

    # 檢查 commodities 表字段，兼容舊表結構
    cursor.execute("PRAGMA table_info(commodities)")
    columns = {row[1] for row in cursor.fetchall()}

    # 新商品數據
    new_commodities = [
        {
            "commodity_id": "fish_bone",
            "name": "魚骨",
            "description": "堅硬的魚骨，保質期長，價格最穩定，適合長期持有",
            "base_price": 4000,
            "volatility": 0.05,
            "shelf_life_days": 7,
        },
        {
            "commodity_id": "fish_scale",
            "name": "魚鱗",
            "description": "閃亮的魚鱗，中等保質期，價格波動適中，平衡之選",
            "base_price": 8000,
            "volatility": 0.09,
            "shelf_life_days": 4,
        },
        {
            "commodity_id": "fish_sauce",
            "name": "魚露",
            "description": "發酵的魚露，極短保質期，價格劇烈波動，僅供高手",
            "base_price": 15000,
            "volatility": 0.18,
            "shelf_life_days": 1,
        },
    ]

    # 插入新商品
    for commodity in new_commodities:
        try:
            # 檢查商品是否已存在
            cursor.execute(
                "SELECT commodity_id FROM commodities WHERE commodity_id = ?",
                (commodity["commodity_id"],),
            )
            if cursor.fetchone():
                logger.debug(f"商品 '{commodity['name']}' 已存在，跳過添加")
                continue

            # 插入新商品，兼容只有基础三列的旧结构
            if {"base_price", "volatility", "shelf_life_days"}.issubset(columns):
                cursor.execute(
                    """
                    INSERT INTO commodities (
                        commodity_id, name, description, base_price,
                        volatility, shelf_life_days
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        commodity["commodity_id"],
                        commodity["name"],
                        commodity["description"],
                        commodity["base_price"],
                        commodity["volatility"],
                        commodity["shelf_life_days"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO commodities (commodity_id, name, description)
                    VALUES (?, ?, ?)
                    """,
                    (
                        commodity["commodity_id"],
                        commodity["name"],
                        commodity["description"],
                    ),
                )
            logger.info(f"成功添加商品: {commodity['name']}")
        except sqlite3.Error as e:
            logger.error(f"添加商品 '{commodity['name']}' 失敗: {e}")
            # 繼續處理其他商品

    logger.info("新商品添加完成")


def down(cursor: sqlite3.Cursor):
    """回滾：刪除新添加的商品"""
    logger.info("正在回滾 043_add_new_exchange_commodities...")

    new_commodity_ids = ["fish_bone", "fish_scale", "fish_sauce"]

    for commodity_id in new_commodity_ids:
        try:
            cursor.execute(
                "DELETE FROM commodities WHERE commodity_id = ?", (commodity_id,)
            )
        except sqlite3.Error as e:
            logger.error(f"刪除商品 '{commodity_id}' 失敗: {e}")

    logger.info("回滾完成")
