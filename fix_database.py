#!/usr/bin/env python3
"""
數據庫修復和優化腳本
用於修復 SQLite 數據庫鎖定和損壞問題
"""

import sqlite3
import os
import shutil
from datetime import datetime


def fix_database(db_path: str):
    """修復數據庫"""
    print(f"開始修復數據庫: {db_path}")
    
    # 檢查數據庫文件是否存在
    if not os.path.exists(db_path):
        print(f"❌ 數據庫文件不存在: {db_path}")
        return False
    
    # 創建備份
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 創建備份: {backup_path}")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ 備份成功")
    except Exception as e:
        print(f"❌ 備份失敗: {e}")
        return False
    
    try:
        # 嘗試連接並檢查數據庫
        print("🔍 檢查數據庫完整性...")
        conn = sqlite3.connect(db_path, timeout=60)
        cursor = conn.cursor()
        
        # 檢查數據庫完整性
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] != "ok":
            print(f"⚠️ 數據庫完整性檢查失敗: {result[0]}")
            print("嘗試修復...")
            
            # 嘗試使用 VACUUM 修復
            try:
                cursor.execute("VACUUM;")
                conn.commit()
                print("✅ VACUUM 完成")
            except Exception as e:
                print(f"❌ VACUUM 失敗: {e}")
        else:
            print("✅ 數據庫完整性檢查通過")
        
        # 優化數據庫設置
        print("⚙️ 優化數據庫設置...")
        
        # 啟用 WAL 模式（提高並發性能）
        cursor.execute("PRAGMA journal_mode = WAL;")
        journal_mode = cursor.fetchone()
        print(f"  - Journal mode: {journal_mode[0] if journal_mode else 'unknown'}")
        
        # 設置同步模式
        cursor.execute("PRAGMA synchronous = NORMAL;")
        sync_mode = cursor.fetchone()
        print(f"  - Synchronous: {sync_mode[0] if sync_mode else 'unknown'}")
        
        # 設置緩存大小（10MB）
        cursor.execute("PRAGMA cache_size = -10000;")
        
        # 設置臨時存儲
        cursor.execute("PRAGMA temp_store = MEMORY;")
        
        # 設置鎖定超時
        cursor.execute("PRAGMA busy_timeout = 60000;")  # 60秒
        
        conn.commit()
        print("✅ 數據庫設置優化完成")
        
        # 分析數據庫以優化查詢
        print("📊 分析數據庫...")
        cursor.execute("ANALYZE;")
        conn.commit()
        print("✅ 數據庫分析完成")
        
        conn.close()
        
        print("\n✅ 數據庫修復和優化完成！")
        print(f"📦 備份文件保存在: {backup_path}")
        return True
        
    except sqlite3.DatabaseError as e:
        print(f"❌ 數據庫錯誤: {e}")
        print("\n如果數據庫嚴重損壞，請考慮：")
        print(f"1. 恢復備份: mv {backup_path} {db_path}")
        print("2. 或者重新初始化數據庫（會丟失所有數據）")
        return False
    except Exception as e:
        print(f"❌ 未知錯誤: {e}")
        return False


def main():
    """主函數"""
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # 默認路徑
        db_path = "data/fish.db"
    
    print("=" * 60)
    print("SQLite 數據庫修復和優化工具")
    print("=" * 60)
    print()
    
    success = fix_database(db_path)
    
    print()
    print("=" * 60)
    if success:
        print("✅ 修復完成！請重啟應用程序。")
    else:
        print("❌ 修復失敗！請檢查錯誤信息。")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
