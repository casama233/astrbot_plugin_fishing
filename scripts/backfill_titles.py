import os
import sys
import types
import sqlite3
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASTRBOT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
sys.path.insert(0, ASTRBOT_ROOT)
sys.path.insert(0, BASE_DIR)

astrbot_module = types.ModuleType("astrbot")
astrbot_api_module = types.ModuleType("astrbot.api")

class DummyLogger:
    def info(self, *args, **kwargs):
        print(*args)
    def error(self, *args, **kwargs):
        print(*args)
    def warning(self, *args, **kwargs):
        print(*args)
    def debug(self, *args, **kwargs):
        print(*args)

astrbot_api_module.logger = DummyLogger()
astrbot_module.api = astrbot_api_module
sys.modules["astrbot"] = astrbot_module
sys.modules["astrbot.api"] = astrbot_api_module

from core.repositories.sqlite_user_repo import SqliteUserRepository
from core.repositories.sqlite_achievement_repo import SqliteAchievementRepository
from core.repositories.sqlite_inventory_repo import SqliteInventoryRepository
from core.repositories.sqlite_item_template_repo import SqliteItemTemplateRepository
from core.repositories.sqlite_log_repo import SqliteLogRepository
from core.services.achievement_service import AchievementService


def parse_reward(achievement):
    if not hasattr(achievement, "reward") or achievement.reward is None:
        return None
    reward_tuple = achievement.reward
    if not isinstance(reward_tuple, (list, tuple)):
        return None
    if len(reward_tuple) == 3:
        reward_type, reward_value, reward_quantity = reward_tuple
    elif len(reward_tuple) == 2:
        reward_type, reward_value = reward_tuple
        reward_quantity = 1
    else:
        return None
    return reward_type, reward_value, reward_quantity


def main():
    db_path = os.environ.get("FISH_DB_PATH", "/opt/1panel/apps/astrbot/astrbot/data/fish.db")
    if not os.path.exists(db_path):
        print(f"找不到資料庫: {db_path}")
        return

    user_repo = SqliteUserRepository(db_path)
    achievement_repo = SqliteAchievementRepository(db_path)
    inventory_repo = SqliteInventoryRepository(db_path)
    item_template_repo = SqliteItemTemplateRepository(db_path)
    log_repo = SqliteLogRepository(db_path)

    achievement_service = AchievementService(
        achievement_repo, user_repo, inventory_repo, item_template_repo, log_repo
    )

    achievements = achievement_service.achievements
    title_achievements = []
    for ach in achievements:
        parsed = parse_reward(ach)
        if not parsed:
            continue
        reward_type, reward_value, reward_quantity = parsed
        if reward_type == "title":
            title_achievements.append((ach, reward_value))

    title_templates = {t.title_id: t for t in item_template_repo.get_all_titles()}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    achievements_in_db = set()
    achievements_table_missing = False
    if "achievements" in tables:
        achievements_in_db = {a.achievement_id for a in achievement_repo.get_all_achievements()}
    else:
        achievements_table_missing = True

    progress_table_missing = "user_achievement_progress" not in tables
    user_titles_table_missing = "user_titles" not in tables

    missing_title_templates = []
    missing_achievement_rows = []
    for ach, title_id in title_achievements:
        if title_id not in title_templates:
            missing_title_templates.append((ach.id, ach.name, title_id))
        if not achievements_table_missing and ach.id not in achievements_in_db:
            missing_achievement_rows.append((ach.id, ach.name))

    user_ids = user_repo.get_all_user_ids()
    grants = []
    checked_users = 0
    if user_titles_table_missing:
        print("缺少 user_titles 表，無法補發稱號")
        return

    for user_id in user_ids:
        user_context = achievement_service._build_user_context(user_id)
        if not user_context:
            continue
        checked_users += 1
        user_progress = {} if progress_table_missing else achievement_repo.get_user_progress(user_id)
        owned_titles = set(inventory_repo.get_user_titles(user_id))
        for ach, title_id in title_achievements:
            if title_id in owned_titles:
                continue
            if title_id not in title_templates:
                continue
            completed_at = user_progress.get(ach.id, {}).get("completed_at")
            if completed_at or ach.check(user_context):
                achievement_repo.grant_title_to_user(user_id, title_id)
                progress_value = ach.get_progress(user_context)
                if not completed_at and not progress_table_missing:
                    achievement_repo.update_user_progress(
                        user_id, ach.id, progress_value, completed_at=datetime.now()
                    )
                grants.append((user_id, ach.id, title_id, title_templates[title_id].name))

    print("稱號補發完成")
    print(f"檢查用戶數: {checked_users}")
    print(f"補發數量: {len(grants)}")
    if missing_title_templates:
        print("缺少稱號模板:")
        for ach_id, ach_name, title_id in missing_title_templates:
            print(f"- 成就 {ach_id} {ach_name} 缺少稱號ID {title_id}")
    if achievements_table_missing:
        print("缺少 achievements 表，無法驗證成就模板完整性")
    elif missing_achievement_rows:
        print("缺少成就模板行:")
        for ach_id, ach_name in missing_achievement_rows:
            print(f"- 成就 {ach_id} {ach_name} 不在 achievements 表")
    if grants:
        print("補發明細:")
        for user_id, ach_id, title_id, title_name in grants:
            print(f"- {user_id} | 成就 {ach_id} | 稱號 {title_id} {title_name}")


if __name__ == "__main__":
    main()
