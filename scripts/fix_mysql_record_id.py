#!/usr/bin/env python3
"""
緊急修復：MySQL record_id 缺少 AUTO_INCREMENT 問題
"""
import sys
import os
sys.path.insert(0, '/opt/1panel/apps/astrbot/astrbot')

try:
    import pymysql
    print("✓ pymysql 已安裝")
except ImportError:
    print("✗ 未安裝 pymysql，請執行：pip install pymysql")
    sys.exit(1)

# 載入配置
import json
config_path = "/opt/1panel/apps/astrbot/astrbot/data/config/astrbot_plugin_fishing_config.json"

if not os.path.exists(config_path):
    print(f"配置文件不存在：{config_path}")
    sys.exit(1)

with open(config_path, 'r', encoding='utf-8-sig') as f:
    config = json.load(f)

external_sql = config.get('external_sql', {})
if not external_sql.get('enabled', False):
    print("外部 SQL 未在配置中啟用")
    sys.exit(1)

print(f"連接 MySQL: {external_sql.get('host')}:{external_sql.get('port')}/{external_sql.get('database')}")

try:
    conn = pymysql.connect(
        host=external_sql.get('host', ''),
        port=int(external_sql.get('port', 3306)),
        user=external_sql.get('user', ''),
        password=external_sql.get('password', ''),
        database=external_sql.get('database', ''),
        charset='utf8mb4',
        autocommit=False
    )
    print("✓ MySQL 連接成功")
except Exception as e:
    print(f"✗ MySQL 連接失敗：{e}")
    sys.exit(1)

try:
    with conn.cursor() as cursor:
        # 修復 fishing_records
        print("\n檢查 fishing_records 表...")
        cursor.execute("SHOW COLUMNS FROM fishing_records")
        columns = cursor.fetchall()
        record_id_col = None
        for col in columns:
            if col[0] == 'record_id':
                record_id_col = col
                break
        
        if record_id_col:
            print(f"  record_id 類型：{record_id_col[1]}")
            print(f"  可為空：{record_id_col[2]}")
            print(f"  鍵：{record_id_col[3]}")
            print(f"  默認值：{record_id_col[4]}")
            print(f"  額外：{record_id_col[5]}")
            
            if 'auto_increment' not in (record_id_col[5] or '').lower():
                print("\n⚠  需要修復 fishing_records.record_id...")
                try:
                    # 1. 刪除主鍵
                    print("  1. 刪除主鍵約束...")
                    cursor.execute("ALTER TABLE fishing_records DROP PRIMARY KEY")
                    
                    # 2. 修改為 AUTO_INCREMENT
                    print("  2. 設置 AUTO_INCREMENT...")
                    cursor.execute("""
                        ALTER TABLE fishing_records 
                        MODIFY record_id BIGINT NOT NULL AUTO_INCREMENT,
                        ADD PRIMARY KEY (record_id)
                    """)
                    
                    print("  ✓ fishing_records.record_id 修復成功")
                except Exception as e:
                    print(f"  ✗ 修復失敗：{e}")
            else:
                print("  ✓ record_id 已經是 AUTO_INCREMENT")
        
        # 修復 gacha_records
        print("\n檢查 gacha_records 表...")
        cursor.execute("SHOW COLUMNS FROM gacha_records")
        columns = cursor.fetchall()
        record_id_col = None
        for col in columns:
            if col[0] == 'record_id':
                record_id_col = col
                break
        
        if record_id_col:
            print(f"  record_id 類型：{record_id_col[1]}")
            print(f"  可為空：{record_id_col[2]}")
            print(f"  鍵：{record_id_col[3]}")
            print(f"  默認值：{record_id_col[4]}")
            print(f"  額外：{record_id_col[5]}")
            
            if 'auto_increment' not in (record_id_col[5] or '').lower():
                print("\n⚠  需要修復 gacha_records.record_id...")
                try:
                    # 1. 刪除主鍵
                    print("  1. 刪除主鍵約束...")
                    cursor.execute("ALTER TABLE gacha_records DROP PRIMARY KEY")
                    
                    # 2. 修改為 AUTO_INCREMENT
                    print("  2. 設置 AUTO_INCREMENT...")
                    cursor.execute("""
                        ALTER TABLE gacha_records 
                        MODIFY record_id BIGINT NOT NULL AUTO_INCREMENT,
                        ADD PRIMARY KEY (record_id)
                    """)
                    
                    print("  ✓ gacha_records.record_id 修復成功")
                except Exception as e:
                    print(f"  ✗ 修復失敗：{e}")
            else:
                print("  ✓ record_id 已經是 AUTO_INCREMENT")
    
    conn.commit()
    print("\n✅ 修復完成！")
    print("\n請重啟 AstrBot 以應用更改")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ 修復過程中出错：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    conn.close()
