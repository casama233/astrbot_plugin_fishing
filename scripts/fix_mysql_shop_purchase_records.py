#!/usr/bin/env python3
"""修復 MySQL shop_purchase_records 表結構

問題：MySQL 表的 record_id 沒有設置 AUTO_INCREMENT
錯誤信息：(1364, "Field 'record_id' doesn't have a default value")

使用方法：
    python3 scripts/fix_mysql_shop_purchase_records.py

或者手動執行 SQL：
    ALTER TABLE shop_purchase_records
    MODIFY COLUMN record_id INT AUTO_INCREMENT PRIMARY KEY,
    MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;
"""

import sys
import os

# 添加路徑
sys.path.insert(0, "/opt/1panel/apps/astrbot/astrbot")
sys.path.insert(
    0, "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_fishing"
)

try:
    import pymysql
except ImportError:
    print("錯誤：pymysql 未安裝")
    print("請執行：pip install pymysql")
    sys.exit(1)


def get_mysql_config_from_file():
    """從配置文件讀取 MySQL 連接信息"""
    import json

    config_path = "/opt/1panel/apps/astrbot/astrbot/data/config/astrbot_plugin_fishing_config.json"

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
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
        print(f"讀取配置文件失敗: {e}")
        return None


def main():
    print("=" * 60)
    print("MySQL shop_purchase_records 表結構修復工具")
    print("=" * 60)

    # 嘗試從配置文件讀取
    config = get_mysql_config_from_file()

    if config:
        print(f"\n從配置文件讀取到 MySQL 連接信息:")
        print(f"  Host: {config['host']}")
        print(f"  Port: {config['port']}")
        print(f"  User: {config['user']}")
        print(f"  Database: {config['database']}")

        use_config = input("\n使用以上配置？[Y/n]: ").strip().lower()
        if use_config != "n":
            pass
        else:
            config = None

    if not config:
        print("\n請輸入 MySQL 連接信息：")
        config = {
            "host": input("Host [localhost]: ").strip() or "localhost",
            "port": int(input("Port [3306]: ").strip() or "3306"),
            "user": input("User [root]: ").strip() or "root",
            "password": input("Password: ").strip(),
            "database": input("Database: ").strip(),
            "charset": "utf8mb4",
        }

        if not config["database"]:
            print("錯誤：數據庫名稱不能為空")
            sys.exit(1)

    try:
        print(f"\n連接到 MySQL...")
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config["charset"],
        )

        with conn.cursor() as cursor:
            # 檢查表是否存在
            cursor.execute("SHOW TABLES LIKE 'shop_purchase_records'")
            if not cursor.fetchone():
                print("❌ 表 shop_purchase_records 不存在")
                print("\n正在創建表...")
                cursor.execute("""
                    CREATE TABLE shop_purchase_records (
                        record_id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        item_id INT NOT NULL,
                        quantity INT NOT NULL DEFAULT 1,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                print("✅ 表創建成功")
            else:
                # 檢查 record_id 是否有 AUTO_INCREMENT
                cursor.execute(
                    "SHOW COLUMNS FROM shop_purchase_records LIKE 'record_id'"
                )
                row = cursor.fetchone()

                if row:
                    extra = str(row[5]).lower() if len(row) > 5 else ""
                    if "auto_increment" not in extra:
                        print("❌ record_id 缺少 AUTO_INCREMENT")
                        print("正在修復...")
                        cursor.execute("""
                            ALTER TABLE shop_purchase_records 
                            MODIFY COLUMN record_id INT AUTO_INCREMENT PRIMARY KEY
                        """)
                        print("✅ record_id 修復成功")
                    else:
                        print("✅ record_id 已正確配置")
                else:
                    print("❌ 無法找到 record_id 字段")

                # 檢查 timestamp
                cursor.execute(
                    "SHOW COLUMNS FROM shop_purchase_records LIKE 'timestamp'"
                )
                row = cursor.fetchone()

                if row:
                    extra = str(row[5]) if len(row) > 5 else ""
                    if "CURRENT_TIMESTAMP" not in extra:
                        print("正在修復 timestamp...")
                        cursor.execute("""
                            ALTER TABLE shop_purchase_records 
                            MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                        """)
                        print("✅ timestamp 修復成功")
                    else:
                        print("✅ timestamp 已正確配置")

                # 創建索引
                try:
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_shop_purchase_user_item 
                        ON shop_purchase_records(user_id, item_id)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_shop_purchase_time 
                        ON shop_purchase_records(timestamp)
                    """)
                    print("✅ 索引檢查完成")
                except Exception as e:
                    if "Duplicate" not in str(e):
                        print(f"索引警告: {e}")

            conn.commit()
            print("\n" + "=" * 60)
            print("🎉 修復完成！")
            print("=" * 60)

        conn.close()

    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
