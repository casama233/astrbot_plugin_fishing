#!/usr/bin/env python3
"""修复 MySQL shop_purchase_records 表结构"""

import sys
import os

# 添加路径
sys.path.insert(0, "/opt/1panel/apps/astrbot/astrbot")
sys.path.insert(
    0, "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_fishing"
)

try:
    from pymysql import connect
except ImportError:
    print("错误：pymysql 未安装")
    sys.exit(1)


def get_mysql_config():
    """从环境或配置获取 MySQL 连接信息"""
    # 尝试从 AstrBot 主配置获取
    # 这里需要根据实际情况调整
    return {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "astrbot"),
        "port": int(os.environ.get("MYSQL_PORT", 3306)),
    }


def main():
    print("请输入 MySQL 连接信息：")
    host = input("Host [localhost]: ").strip() or "localhost"
    port = int(input("Port [3306]: ").strip() or "3306")
    user = input("User [root]: ").strip() or "root"
    password = input("Password: ").strip()
    database = input("Database: ").strip()

    if not database:
        print("错误：数据库名称不能为空")
        sys.exit(1)

    try:
        conn = connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )

        with conn.cursor() as cursor:
            # 检查表是否存在
            cursor.execute("SHOW TABLES LIKE 'shop_purchase_records'")
            if not cursor.fetchone():
                print("表 shop_purchase_records 不存在，将创建...")
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
                print("✅ 表创建成功")
            else:
                # 检查 record_id 是否有 AUTO_INCREMENT
                cursor.execute(
                    "SHOW COLUMNS FROM shop_purchase_records LIKE 'record_id'"
                )
                row = cursor.fetchone()
                if row and "auto_increment" not in str(row[5]).lower():
                    print("正在修复 record_id 字段...")
                    cursor.execute(
                        "ALTER TABLE shop_purchase_records MODIFY COLUMN record_id INT AUTO_INCREMENT PRIMARY KEY"
                    )
                    print("✅ record_id 修复成功")
                else:
                    print("✅ record_id 已正确配置")

                # 检查 timestamp 是否有 DEFAULT CURRENT_TIMESTAMP
                cursor.execute(
                    "SHOW COLUMNS FROM shop_purchase_records LIKE 'timestamp'"
                )
                row = cursor.fetchone()
                if row and "CURRENT_TIMESTAMP" not in str(row[5]):
                    print("正在修复 timestamp 字段...")
                    cursor.execute(
                        "ALTER TABLE shop_purchase_records MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
                    )
                    print("✅ timestamp 修复成功")
                else:
                    print("✅ timestamp 已正确配置")

            # 创建索引
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_shop_purchase_user_item ON shop_purchase_records(user_id, item_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_shop_purchase_time ON shop_purchase_records(timestamp)"
                )
                print("✅ 索引创建成功")
            except Exception as e:
                if "Duplicate" not in str(e):
                    print(f"索引创建警告: {e}")

            conn.commit()
            print("\n🎉 修复完成！")

        conn.close()

    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
