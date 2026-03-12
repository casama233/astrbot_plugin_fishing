#!/usr/bin/env python3
"""
修復卡池物品映射問題
自動修復卡池中指向不存在模板的物品配置
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_gacha_pool_items(pool_id: int, fix_mode: str = "report"):
    """
    修復卡池物品配置
    
    Args:
        pool_id: 要修復的卡池 ID
        fix_mode: "report" (僅報告), "remove" (刪除無效配置), "update" (更新為有效 ID)
    """
    print("=" * 60)
    print(f"卡池物品修復工具 - 卡池 ID: {pool_id}")
    print("=" * 60)
    
    try:
        # 嘗試不同的配置加載方式
        config = None
        db_type = "sqlite"
        
        try:
            from core.config import get_config
            config = get_config()
            db_config = config.get('database', {})
            db_type = db_config.get('type', 'sqlite')
        except:
            # Fallback: 使用環境變量或默認配置
            print("使用默認配置加載方式")
            pass
        
        if db_type == 'mysql':
            from core.database.mysql_connection_manager import MysqlConnectionManager
            
            db_config = config.get('database', {}) if config else {}
            mysql_config = {
                'host': db_config.get('host', 'localhost'),
                'port': db_config.get('port', 3306),
                'user': db_config.get('user', 'root'),
                'password': db_config.get('password', ''),
                'database': db_config.get('database', 'astrbot_fishing'),
            }
            
            conn_manager = MysqlConnectionManager(mysql_config)
            
            with conn_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 獲取卡池物品
                    cursor.execute("""
                        SELECT gacha_pool_item_id, item_type, item_id, weight, quantity
                        FROM gacha_pool_items
                        WHERE gacha_pool_id = %s
                        ORDER BY gacha_pool_item_id
                    """, (pool_id,))
                    
                    pool_items = cursor.fetchall()
                    
                    if not pool_items:
                        print(f"卡池 {pool_id} 沒有配置任何物品")
                        return
                    
                    print(f"\n找到 {len(pool_items)} 個物品配置\n")
                    
                    invalid_items = []
                    valid_count = 0
                    
                    for item in pool_items:
                        item_type = item['item_type']
                        item_id = item['item_id']
                        
                        # 金幣類型總是有效的
                        if item_type == 'coins':
                            print(f"✓ {item_type}-{item_id}: 金幣配置 (有效)")
                            valid_count += 1
                            continue
                        
                        # 檢查模板是否存在
                        table_map = {
                            'rod': 'rod_templates',
                            'accessory': 'accessory_templates',
                            'bait': 'bait_templates',
                            'item': 'item_templates',
                            'titles': 'title_templates',
                        }
                        
                        template_table = table_map.get(item_type)
                        id_column = f"{item_type}_id"
                        
                        if not template_table:
                            print(f"✗ {item_type}-{item_id}: 未知的物品類型")
                            invalid_items.append(item)
                            continue
                        
                        cursor.execute(f"""
                            SELECT name FROM {template_table} WHERE {id_column} = %s
                        """, (item_id,))
                        
                        result = cursor.fetchone()
                        
                        if result:
                            print(f"✓ {item_type}-{item_id}: {result['name']} (有效)")
                            valid_count += 1
                        else:
                            print(f"✗ {item_type}-{item_id}: 模板不存在 (無效)")
                            invalid_items.append(item)
                    
                    print(f"\n{'='*60}")
                    print(f"統計：{valid_count} 有效，{len(invalid_items)} 無效")
                    
                    if invalid_items:
                        print(f"\n⚠️  發現 {len(invalid_items)} 個無效的物品配置")
                        
                        if fix_mode == "remove":
                            print(f"\n正在刪除無效配置...")
                            for item in invalid_items:
                                cursor.execute("""
                                    DELETE FROM gacha_pool_items
                                    WHERE gacha_pool_item_id = %s
                                """, (item['gacha_pool_item_id'],))
                                print(f"  已刪除：{item['item_type']}-{item['item_id']}")
                            conn.commit()
                            print("\n✓ 修復完成！已刪除所有無效配置")
                        
                        elif fix_mode == "report":
                            print("\n建議操作:")
                            print("  1. 刪除無效配置：python3 scripts/fix_gacha_pool_items.py --pool-id 10 --mode remove")
                            print("  2. 或者手動更新這些配置指向有效的模板 ID")
                    
                    else:
                        print("\n✓ 所有物品配置都有效！")
        
        elif db_type == 'sqlite':
            import sqlite3
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data.db')
            
            if not os.path.exists(db_path):
                print(f"❌ 找不到 SQLite 數據庫文件：{db_path}")
                return
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 獲取卡池物品
            cursor.execute("""
                SELECT gacha_pool_item_id, item_type, item_id, weight, quantity
                FROM gacha_pool_items
                WHERE gacha_pool_id = ?
                ORDER BY gacha_pool_item_id
            """, (pool_id,))
            
            pool_items = cursor.fetchall()
            
            if not pool_items:
                print(f"卡池 {pool_id} 沒有配置任何物品")
                return
            
            print(f"\n找到 {len(pool_items)} 個物品配置\n")
            
            invalid_items = []
            valid_count = 0
            
            for item in pool_items:
                item_type = item['item_type']
                item_id = item['item_id']
                
                if item_type == 'coins':
                    print(f"✓ {item_type}-{item_id}: 金幣配置 (有效)")
                    valid_count += 1
                    continue
                
                table_map = {
                    'rod': 'rod_templates',
                    'accessory': 'accessory_templates',
                    'bait': 'bait_templates',
                    'item': 'item_templates',
                    'titles': 'title_templates',
                }
                
                template_table = table_map.get(item_type)
                id_column = f"{item_type}_id"
                
                if not template_table:
                    print(f"✗ {item_type}-{item_id}: 未知的物品類型")
                    invalid_items.append(item)
                    continue
                
                cursor.execute(f"""
                    SELECT name FROM {template_table} WHERE {id_column} = ?
                """, (item_id,))
                
                result = cursor.fetchone()
                
                if result:
                    print(f"✓ {item_type}-{item_id}: {result['name']} (有效)")
                    valid_count += 1
                else:
                    print(f"✗ {item_type}-{item_id}: 模板不存在 (無效)")
                    invalid_items.append(item)
            
            print(f"\n{'='*60}")
            print(f"統計：{valid_count} 有效，{len(invalid_items)} 無效")
            
            if invalid_items:
                print(f"\n⚠️  發現 {len(invalid_items)} 個無效的物品配置")
                
                if fix_mode == "remove":
                    print(f"\n正在刪除無效配置...")
                    for item in invalid_items:
                        cursor.execute("""
                            DELETE FROM gacha_pool_items
                            WHERE gacha_pool_item_id = ?
                        """, (item['gacha_pool_item_id'],))
                        print(f"  已刪除：{item['item_type']}-{item['item_id']}")
                    conn.commit()
                    print("\n✓ 修復完成！已刪除所有無效配置")
                
                elif fix_mode == "report":
                    print("\n建議操作:")
                    print("  1. 刪除無效配置：python3 scripts/fix_gacha_pool_items.py --pool-id 10 --mode remove")
                    print("  2. 或者手動更新這些配置指向有效的模板 ID")
            else:
                print("\n✓ 所有物品配置都有效！")
            
            conn.close()
    
    except Exception as e:
        print(f"\n❌ 修復過程發生錯誤：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='修復卡池物品配置')
    parser.add_argument('--pool-id', type=int, default=10, help='要修復的卡池 ID (默認：10)')
    parser.add_argument('--mode', type=str, default='report', choices=['report', 'remove'],
                       help='修復模式：report (僅報告), remove (刪除無效配置)')
    
    args = parser.parse_args()
    fix_gacha_pool_items(args.pool_id, args.mode)
