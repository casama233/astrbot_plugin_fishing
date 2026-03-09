#!/usr/bin/env python3
"""
Fix record_id AUTO_INCREMENT issue in MySQL tables.
This script adds AUTO_INCREMENT to record_id columns in fishing_records and gacha_records tables.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrbot.api import logger
from core.database.mysql_connection_manager import MysqlConnectionManager
from typing import Dict, Any

def fix_autoincrement(config: Dict[str, Any]):
    """Fix AUTO_INCREMENT on record_id columns."""
    try:
        import pymysql
    except ImportError:
        print("pymysql not installed. Install with: pip install pymysql")
        return False
    
    try:
        conn = pymysql.connect(
            host=config.get('host', ''),
            port=int(config.get('port', 3306)),
            user=config.get('user', ''),
            password=config.get('password', ''),
            database=config.get('database', ''),
            charset='utf8mb4',
            autocommit=False
        )
    except Exception as e:
        print(f"Failed to connect to MySQL: {e}")
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check fishing_records table
            cursor.execute("SHOW COLUMNS FROM fishing_records")
            columns = {row[0]: row for row in cursor.fetchall()}
            
            if 'record_id' in columns:
                col_info = columns['record_id']
                print(f"fishing_records.record_id: {col_info}")
                if 'auto_increment' not in col_info[3].lower():  # col_info[3] is Extra field
                    print("Fixing fishing_records.record_id...")
                    # Drop the primary key
                    cursor.execute("ALTER TABLE fishing_records DROP PRIMARY KEY")
                    # Modify record_id to be BIGINT AUTO_INCREMENT
                    cursor.execute("""
                        ALTER TABLE fishing_records 
                        MODIFY record_id BIGINT NOT NULL AUTO_INCREMENT,
                        ADD PRIMARY KEY (record_id)
                    """)
                    print("✓ Fixed fishing_records.record_id")
                else:
                    print("✓ fishing_records.record_id is already AUTO_INCREMENT")
            
            # Check gacha_records table
            cursor.execute("SHOW COLUMNS FROM gacha_records")
            columns = {row[0]: row for row in cursor.fetchall()}
            
            if 'record_id' in columns:
                col_info = columns['record_id']
                print(f"gacha_records.record_id: {col_info}")
                if 'auto_increment' not in col_info[3].lower():
                    print("Fixing gacha_records.record_id...")
                    # Drop the primary key
                    cursor.execute("ALTER TABLE gacha_records DROP PRIMARY KEY")
                    # Modify record_id to be BIGINT AUTO_INCREMENT
                    cursor.execute("""
                        ALTER TABLE gacha_records 
                        MODIFY record_id BIGINT NOT NULL AUTO_INCREMENT,
                        ADD PRIMARY KEY (record_id)
                    """)
                    print("✓ Fixed gacha_records.record_id")
                else:
                    print("✓ gacha_records.record_id is already AUTO_INCREMENT")
        
        conn.commit()
        print("\n✅ All fixes applied successfully!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during fix: {e}")
        logger.error(f"Fix failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import json
    
    # Load config from file
    config_path = "/opt/1panel/apps/astrbot/astrbot/data/config/astrbot_plugin_fishing_config.json"
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)
    else:
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    
    external_sql = config.get('external_sql', {})
    if not external_sql.get('enabled', False):
        print("External SQL is not enabled in config")
        sys.exit(1)
    
    print(f"MySQL Config: {external_sql.get('host')}:{external_sql.get('port')}/{external_sql.get('database')}")
    print("Starting fix...\n")
    
    success = fix_autoincrement(external_sql)
    sys.exit(0 if success else 1)
