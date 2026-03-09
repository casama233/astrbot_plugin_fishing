#!/usr/bin/env python3
"""
Fishing 插件數據庫維護腳本
定期執行以保持數據庫健康和性能

使用方法:
    python3 scripts/database_maintenance.py
"""

import sqlite3
import os
import sys
from datetime import datetime

# 添加路徑
sys.path.insert(0, "/opt/1panel/apps/astrbot/astrbot")
sys.path.insert(
    0, "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_fishing"
)

DB_PATH = "/opt/1panel/apps/astrbot/astrbot/data/fish.db"
TMP_DIR = "/opt/1panel/apps/astrbot/astrbot/data/tmp"
PLUGIN_DIR = "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_fishing"


def clean_python_cache():
    """清理 Python 緩存"""
    import shutil

    count = 0
    for root, dirs, files in os.walk(PLUGIN_DIR):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))
                count += 1
        for f in files:
            if f.endswith(".pyc"):
                os.remove(os.path.join(root, f))

    print(f"✅ 清理 {count} 個 __pycache__ 目錄")


def clean_old_files(days=7):
    """清理舊文件"""
    import time

    cleaned = 0
    for root, dirs, files in os.walk(TMP_DIR):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(filepath)
                if time.time() - mtime > days * 86400:
                    os.remove(filepath)
                    cleaned += 1
            except Exception:
                pass

    # 清理備份文件
    backup_dir = os.path.dirname(DB_PATH)
    for f in os.listdir(backup_dir):
        if f.endswith(".bak") or f.endswith(".pre_repair_*"):
            try:
                os.remove(os.path.join(backup_dir, f))
                cleaned += 1
            except Exception:
                pass

    print(f"✅ 清理 {cleaned} 個舊文件")


def vacuum_sqlite():
    """優化 SQLite 數據庫"""
    if not os.path.exists(DB_PATH):
        print("⚠️  數據庫不存在")
        return

    original_size = os.path.getsize(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # VACUUM
    cursor.execute("VACUUM")

    # 完整性檢查
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]

    # ANALYZE
    cursor.execute("ANALYZE")

    conn.commit()
    conn.close()

    new_size = os.path.getsize(DB_PATH)
    saved = original_size - new_size

    print(
        f"✅ SQLite 優化：{original_size / 1024 / 1024:.2f}MB -> {new_size / 1024 / 1024:.2f}MB (節省 {saved / 1024:.1f}KB)"
    )

    if result != "ok":
        print(f"⚠️  完整性檢查警告：{result}")


def check_data_integrity():
    """檢查數據完整性"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 獲取有效用戶
    cursor.execute("SELECT user_id FROM users")
    valid_users = set(row[0] for row in cursor.fetchall())

    issues = []

    # 檢查孤立記錄
    tables = [
        ("user_rods", "user_id"),
        ("user_accessories", "user_id"),
        ("user_items", "user_id"),
        ("user_fish_inventory", "user_id"),
    ]

    for table, col in tables:
        try:
            placeholders = ",".join(["?" for _ in valid_users])
            cursor.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE {col} NOT IN ({placeholders})',
                list(valid_users),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                issues.append(f"{table}: {count} 條孤立記錄")
        except Exception as e:
            issues.append(f"{table}: 檢查失敗 - {e}")

    conn.close()

    if issues:
        print("⚠️  數據完整性問題:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✅ 數據完整性檢查通過")


def main():
    print("=" * 60)
    print("  Fishing 插件數據庫維護")
    print(f"  執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    try:
        print("1. 清理 Python 緩存...")
        clean_python_cache()
        print()

        print("2. 清理舊文件...")
        clean_old_files(days=7)
        print()

        print("3. 優化 SQLite 數據庫...")
        vacuum_sqlite()
        print()

        print("4. 檢查數據完整性...")
        check_data_integrity()
        print()

        print("=" * 60)
        print("  ✅ 維護完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 維護失敗：{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
