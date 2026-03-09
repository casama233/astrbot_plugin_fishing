#!/usr/bin/env python3
"""修復 MySQL commodities 表"""

import sys
import os

# 添加路徑
sys.path.insert(0, "/opt/1panel/apps/astrbot/astrbot")
sys.path.insert(0, "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_fishing")

try:
    import pymysql
except ImportError:
    print("錯誤：pymysql 未安裝")
    sys.exit(1)

def get_mysql_config():
    """從配置文件讀取 MySQL 連接信息"""
    import json
    
    config_path = "/opt/1panel/apps/astrbot/astrbot/data/config/astrbot_plugin_fishing_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)
        
        external_sql = config.get("external_sql", {})
        return {
            "host": external_sql.get("host", "localhost"),
            "port": external_sql.get("port", 3306),
            "user": external_sql.get("user", "root"),
            "password": external_sql.get("password", ""),
            "database": external_sql.get("database", "astrbot"),
            "charset": external_sql.get("charset", "utf8mb4"),
        }
    except Exception as e:
        print(f"讀取配置文件失敗：{e}")
        return None

def main():
    config = get_mysql_config()
    if not config:
        print("無法獲取 MySQL 配置")
        return
    
    print("=" * 60)
    print("   MySQL commodities 表修復工具")
    print("=" * 60)
    print(f"\n連接信息：{config['host']}:{config['port']}/{config['database']}")
    
    try:
        print("\n正在連接 MySQL...")
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        # 1. 刪除舊表
        print("\n【1】刪除舊表")
        cursor.execute("DROP TABLE IF EXISTS commodities")
        print("   ✅ 舊表已刪除")
        
        # 2. 創建新表
        print("\n【2】創建 commodities 表")
        cursor.execute("""
            CREATE TABLE commodities (
                commodity_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                base_price INT NOT NULL DEFAULT 0,
                volatility DECIMAL(10,4) NOT NULL DEFAULT 0.1,
                shelf_life_days INT NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        print("   ✅ 表已創建")
        
        # 3. 插入數據
        print("\n【3】插入商品數據")
        commodities = [
            ('dried_fish', '鱼干', '稳健型标的，价格波动低', 6000, 0.08, 3),
            ('fish_roe', '鱼卵', '高风险标的，价格波动极大', 12000, 0.12, 2),
            ('fish_oil', '鱼油', '投机品，有概率触发事件导致价格大幅涨跌', 10000, 0.10, 2),
            ('fish_bone', '魚骨', '堅硬的魚骨，保質期長，價格最穩定，適合長期持有', 4000, 0.05, 7),
            ('fish_scale', '魚鱗', '閃亮的魚鱗，中等保質期，價格波動適中，平衡之選', 8000, 0.09, 4),
            ('fish_sauce', '魚露', '發酵的魚露，極短保質期，價格劇烈波動，僅供高手', 15000, 0.18, 1),
        ]
        
        for item in commodities:
            cursor.execute("""
                INSERT INTO commodities (commodity_id, name, description, base_price, volatility, shelf_life_days)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, item)
            print(f"   ✅ 插入 {item[0]}: {item[1]}")
        
        conn.commit()
        
        # 4. 驗證
        print("\n【4】驗證數據")
        cursor.execute("SELECT commodity_id, name, base_price, volatility, shelf_life_days FROM commodities ORDER BY commodity_id")
        rows = cursor.fetchall()
        print(f"\n   商品總數：{len(rows)}")
        for row in rows:
            print(f"   • {row[0]}: {row[1]} (價格:{row[2]}, 波動:{row[3]}, 保質期:{row[4]}天)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ MySQL commodities 表修復完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 錯誤：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
