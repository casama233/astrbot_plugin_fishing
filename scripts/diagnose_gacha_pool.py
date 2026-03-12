#!/usr/bin/env python3
"""
診斷卡池物品映射問題
檢查卡池中的物品 ID 是否存在於對應的模板表中
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def diagnose_gacha_pool_items():
    """診斷卡池物品映射問題"""
    print("=" * 60)
    print("卡池物品映射診斷工具")
    print("=" * 60)

    try:
        from core.database.mysql_connection_manager import MysqlConnectionManager
        from core.config import get_config

        config = get_config()
        db_config = config.get("database", {})

        if db_config.get("type") != "mysql":
            print("\n當前使用 SQLite 數據庫")
            print("請確認是否已遷移到 MySQL，或檢查 SQLite 數據庫")
            return

        mysql_config = {
            "host": db_config.get("host", "localhost"),
            "port": db_config.get("port", 3306),
            "user": db_config.get("user"),
            "password": db_config.get("password"),
            "database": db_config.get("database"),
        }

        conn_manager = MysqlConnectionManager(mysql_config)

        with conn_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                # 1. 查看所有卡池
                print("\n【1. 卡池列表】")
                cursor.execute(
                    "SELECT gacha_pool_id, name, cost_coins FROM gacha_pools ORDER BY gacha_pool_id"
                )
                pools = cursor.fetchall()
                for pool in pools:
                    print(
                        f"  ID {pool['gacha_pool_id']}: {pool['name']} (消耗：{pool['cost_coins']} 金幣)"
                    )

                # 2. 檢查指定卡池的物品
                target_pool_id = 10
                print(f"\n【2. 檢查卡池 ID {target_pool_id} 的物品配置】")

                cursor.execute(
                    """
                    SELECT gacha_pool_item_id, item_type, item_id, weight, quantity
                    FROM gacha_pool_items
                    WHERE gacha_pool_id = %s
                    ORDER BY gacha_pool_item_id
                """,
                    (target_pool_id,),
                )

                pool_items = cursor.fetchall()

                if not pool_items:
                    print(f"  卡池 {target_pool_id} 沒有配置任何物品")
                    return

                print(f"  找到 {len(pool_items)} 個物品配置:\n")

                # 3. 檢查每個物品是否存在於對應的模板表
                missing_items = []

                for item in pool_items:
                    item_type = item["item_type"]
                    item_id = item["item_id"]

                    # 跳過金幣類型的物品
                    if item_type == "coins":
                        print(
                            f"  ✓ ID {item['gacha_pool_item_id']}: {item_type} - {item_id} 金幣 (權重：{item['weight']})"
                        )
                        continue

                    # 檢查對應的模板表
                    template_found = False
                    template_name = None

                    if item_type == "rod":
                        cursor.execute(
                            "SELECT name FROM rod_templates WHERE rod_id = %s",
                            (item_id,),
                        )
                        result = cursor.fetchone()
                        if result:
                            template_found = True
                            template_name = result["name"]

                    elif item_type == "accessory":
                        cursor.execute(
                            "SELECT name FROM accessory_templates WHERE accessory_id = %s",
                            (item_id,),
                        )
                        result = cursor.fetchone()
                        if result:
                            template_found = True
                            template_name = result["name"]

                    elif item_type == "bait":
                        cursor.execute(
                            "SELECT name FROM bait_templates WHERE bait_id = %s",
                            (item_id,),
                        )
                        result = cursor.fetchone()
                        if result:
                            template_found = True
                            template_name = result["name"]

                    elif item_type == "item":
                        cursor.execute(
                            "SELECT name FROM item_templates WHERE item_id = %s",
                            (item_id,),
                        )
                        result = cursor.fetchone()
                        if result:
                            template_found = True
                            template_name = result["name"]

                    elif item_type == "titles":
                        cursor.execute(
                            "SELECT name FROM title_templates WHERE title_id = %s",
                            (item_id,),
                        )
                        result = cursor.fetchone()
                        if result:
                            template_found = True
                            template_name = result["name"]

                    # 顯示結果
                    status = "✓" if template_found else "✗"
                    template_name_display = template_name if template_name else "不存在"
                    print(
                        f"  {status} ID {item['gacha_pool_item_id']}: {item_type}-{item_id} -> {template_name_display} (權重：{item['weight']})"
                    )

                    if not template_found:
                        missing_items.append(
                            {
                                "gacha_pool_item_id": item["gacha_pool_item_id"],
                                "item_type": item_type,
                                "item_id": item_id,
                            }
                        )

                # 4. 總結
                print(f"\n【3. 診斷結果】")
                if missing_items:
                    print(f"  ⚠️  發現 {len(missing_items)} 個物品配置指向不存在的模板:")
                    for missing in missing_items:
                        print(
                            f"    - {missing['item_type']}-{missing['item_id']} (卡池物品 ID: {missing['gacha_pool_item_id']})"
                        )
                    print("\n  建議修復方法:")
                    print("  1. 更新卡池物品配置，使用正確的模板 ID")
                    print("  2. 或者創建對應的物品模板")
                    print("\n  可以使用以下命令修復:")
                    print("  python3 scripts/fix_gacha_pool_items.py --pool-id 10")
                else:
                    print("  ✓ 所有物品配置都正確映射到存在的模板")

    except Exception as e:
        print(f"\n❌ 診斷過程發生錯誤：{e}")
        print("\n請確認:")
        print("  1. 數據庫連接配置正確")
        print("  2. 數據庫服務正在運行")
        print("  3. 相關數據表已創建")


if __name__ == "__main__":
    diagnose_gacha_pool_items()
