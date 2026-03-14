from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from astrbot.api import logger

from ..database.mysql_connection_manager import MysqlConnectionManager
from ..domain.models import TutorialTask, UserTutorialProgress
from ..utils import get_now


class MysqlTutorialRepository:
    """新手引導教程倉儲"""

    DEFAULT_TASKS = [
        {
            "sequence": 1,
            "category": "core",
            "title": "初次簽到",
            "description": "每日簽到領取金幣獎勵",
            "target_type": "command",
            "target_command": "簽到",
            "reward_coins": 50,
            "hint": "使用 /簽到 領取每日獎勵",
        },
        {
            "sequence": 2,
            "category": "core",
            "title": "第一次釣魚",
            "description": "嘗試釣魚，開啟你的漁獲之旅",
            "target_type": "fish_count",
            "target_value": 1,
            "reward_coins": 100,
            "hint": "使用 /釣魚 開始釣魚",
        },
        {
            "sequence": 3,
            "category": "core",
            "title": "釣魚新手",
            "description": "累計釣魚 5 次",
            "target_type": "fish_count",
            "target_value": 5,
            "reward_coins": 200,
            "hint": "繼續使用 /釣魚 累積經驗",
        },
        {
            "sequence": 4,
            "category": "economy",
            "title": "賣出第一條魚",
            "description": "將魚塘裡的魚賣出換取金幣",
            "target_type": "command",
            "target_command": "全部賣出",
            "reward_coins": 100,
            "hint": "使用 /全部賣出 賣掉魚塘所有魚",
        },
        {
            "sequence": 5,
            "category": "economy",
            "title": "商店購物",
            "description": "在商店購買魚餌或其他道具",
            "target_type": "command",
            "target_command": "商店購買",
            "reward_coins": 150,
            "hint": "使用 /商店購買 D1 3 購買魚餌",
        },
        {
            "sequence": 6,
            "category": "equipment",
            "title": "查看裝備",
            "description": "查看你的魚竿和飾品",
            "target_type": "command",
            "target_command": "魚竿",
            "reward_coins": 50,
            "hint": "使用 /魚竿 或 /飾品 查看裝備",
        },
        {
            "sequence": 7,
            "category": "equipment",
            "title": "裝備使用",
            "description": "裝備一個道具或飾品",
            "target_type": "command",
            "target_command": "使用",
            "reward_coins": 100,
            "hint": "使用 /使用 Rxxxx 裝備魚竿",
        },
        {
            "sequence": 8,
            "category": "social",
            "title": "查看排行榜",
            "description": "查看伺服器排行榜",
            "target_type": "command",
            "target_command": "排行榜",
            "reward_coins": 50,
            "hint": "使用 /排行榜 查看排名",
        },
        {
            "sequence": 9,
            "category": "core",
            "title": "釣魚達人",
            "description": "累計釣魚 20 次",
            "target_type": "fish_count",
            "target_value": 20,
            "reward_coins": 500,
            "reward_premium": 5,
            "hint": "堅持釣魚，積累經驗",
        },
        {
            "sequence": 10,
            "category": "economy",
            "title": "交易所開戶",
            "description": "在交易所開設帳戶",
            "target_type": "command",
            "target_command": "交易所 開戶",
            "reward_coins": 200,
            "hint": "使用 /交易所 開戶 開始投資",
        },
    ]

    def __init__(self, config):
        external_sql_config = (
            config.get("external_sql", {})
            if isinstance(config, dict)
            else getattr(config, "get", lambda k, d: {})(k="external_sql", d={})
        )
        self._connection_manager = MysqlConnectionManager(external_sql_config)
        self._ensure_tables_exist()
        self._ensure_default_tasks_exist()

    def _ensure_tables_exist(self):
        """確保教程相關表存在"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tutorial_tasks (
                        task_id INT AUTO_INCREMENT PRIMARY KEY,
                        sequence INT NOT NULL DEFAULT 0,
                        category VARCHAR(50) NOT NULL DEFAULT 'core',
                        title VARCHAR(100) NOT NULL,
                        description TEXT,
                        target_type VARCHAR(50) NOT NULL,
                        target_value INT NOT NULL DEFAULT 1,
                        target_command VARCHAR(100),
                        reward_coins INT NOT NULL DEFAULT 0,
                        reward_premium INT NOT NULL DEFAULT 0,
                        reward_item_id INT,
                        reward_item_quantity INT NOT NULL DEFAULT 0,
                        hint TEXT,
                        is_active TINYINT(1) NOT NULL DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_sequence (sequence)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_tutorial_progress (
                        progress_id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        task_id INT NOT NULL,
                        current_progress INT NOT NULL DEFAULT 0,
                        is_completed TINYINT(1) NOT NULL DEFAULT 0,
                        completed_at DATETIME NULL,
                        reward_claimed TINYINT(1) NOT NULL DEFAULT 0,
                        reward_claimed_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_user_task (user_id, task_id),
                        KEY idx_user_id (user_id),
                        KEY idx_task_id (task_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

    def _ensure_default_tasks_exist(self):
        """確保默認任務存在"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                for task in self.DEFAULT_TASKS:
                    cursor.execute(
                        """
                        SELECT task_id FROM tutorial_tasks WHERE sequence = %s
                    """,
                        (task["sequence"],),
                    )
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO tutorial_tasks
                            (sequence, category, title, description, target_type, target_value,
                             target_command, reward_coins, reward_premium, hint, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                            (
                                task["sequence"],
                                task["category"],
                                task["title"],
                                task["description"],
                                task["target_type"],
                                task.get("target_value", 1),
                                task.get("target_command"),
                                task.get("reward_coins", 0),
                                task.get("reward_premium", 0),
                                task.get("hint"),
                            ),
                        )
                conn.commit()

    def _parse_datetime(self, dt_val) -> Optional[datetime]:
        if isinstance(dt_val, datetime):
            return dt_val
        if isinstance(dt_val, str):
            try:
                return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(dt_val, fmt)
                    except ValueError:
                        pass
        return None

    def _row_to_task(self, row) -> Optional[TutorialTask]:
        if not row:
            return None
        return TutorialTask(
            task_id=row["task_id"],
            sequence=row["sequence"],
            category=row["category"],
            title=row["title"],
            description=row["description"] or "",
            target_type=row["target_type"],
            target_value=row["target_value"] or 1,
            target_command=row.get("target_command"),
            reward_coins=row["reward_coins"] or 0,
            reward_premium=row["reward_premium"] or 0,
            reward_item_id=row.get("reward_item_id"),
            reward_item_quantity=row["reward_item_quantity"] or 0,
            hint=row.get("hint"),
            is_active=bool(row["is_active"]),
        )

    def _row_to_progress(self, row) -> Optional[UserTutorialProgress]:
        if not row:
            return None
        return UserTutorialProgress(
            progress_id=row["progress_id"],
            user_id=row["user_id"],
            task_id=row["task_id"],
            current_progress=row["current_progress"] or 0,
            is_completed=bool(row["is_completed"]),
            completed_at=self._parse_datetime(row.get("completed_at")),
            reward_claimed=bool(row["reward_claimed"]),
            reward_claimed_at=self._parse_datetime(row.get("reward_claimed_at")),
        )

    def get_all_active_tasks(self) -> List[TutorialTask]:
        """獲取所有活躍的教程任務"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM tutorial_tasks WHERE is_active = 1 ORDER BY sequence ASC
                """)
                rows = cursor.fetchall()
                return [self._row_to_task(row) for row in rows if row]

    def get_task_by_id(self, task_id: int) -> Optional[TutorialTask]:
        """根據 ID 獲取任務"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tutorial_tasks WHERE task_id = %s", (task_id,)
                )
                row = cursor.fetchone()
                return self._row_to_task(row)

    def get_task_by_sequence(self, sequence: int) -> Optional[TutorialTask]:
        """根據順序獲取任務"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM tutorial_tasks WHERE sequence = %s", (sequence,)
                )
                row = cursor.fetchone()
                return self._row_to_task(row)

    def get_user_progress(self, user_id: str) -> List[UserTutorialProgress]:
        """獲取用戶所有教程進度"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM user_tutorial_progress WHERE user_id = %s
                """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                return [self._row_to_progress(row) for row in rows if row]

    def get_user_progress_for_task(
        self, user_id: str, task_id: int
    ) -> Optional[UserTutorialProgress]:
        """獲取用戶特定任務的進度"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM user_tutorial_progress WHERE user_id = %s AND task_id = %s
                """,
                    (user_id, task_id),
                )
                row = cursor.fetchone()
                return self._row_to_progress(row)

    def init_user_progress(self, user_id: str) -> None:
        """初始化用戶教程進度"""
        tasks = self.get_all_active_tasks()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                for task in tasks:
                    cursor.execute(
                        """
                        SELECT progress_id FROM user_tutorial_progress
                        WHERE user_id = %s AND task_id = %s
                    """,
                        (user_id, task.task_id),
                    )
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO user_tutorial_progress (user_id, task_id, current_progress)
                            VALUES (%s, %s, 0)
                        """,
                            (user_id, task.task_id),
                        )
                conn.commit()

    def update_progress(self, user_id: str, task_id: int, progress: int) -> None:
        """更新用戶任務進度"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_tutorial_progress (user_id, task_id, current_progress)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE current_progress = %s
                """,
                    (user_id, task_id, progress, progress),
                )
                conn.commit()

    def complete_task(self, user_id: str, task_id: int) -> None:
        """標記任務完成"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_tutorial_progress (user_id, task_id, current_progress, is_completed, completed_at)
                    VALUES (%s, %s, 0, 1, %s)
                    ON DUPLICATE KEY UPDATE is_completed = 1, completed_at = %s
                """,
                    (user_id, task_id, now, now),
                )
                conn.commit()

    def claim_reward(self, user_id: str, task_id: int) -> bool:
        """領取任務獎勵"""
        now = get_now()
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT progress_id, is_completed, reward_claimed FROM user_tutorial_progress
                    WHERE user_id = %s AND task_id = %s
                """,
                    (user_id, task_id),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                if not row["is_completed"]:
                    return False
                if row["reward_claimed"]:
                    return False
                cursor.execute(
                    """
                    UPDATE user_tutorial_progress
                    SET reward_claimed = 1, reward_claimed_at = %s
                    WHERE user_id = %s AND task_id = %s
                """,
                    (now, user_id, task_id),
                )
                conn.commit()
                return True

    def increment_progress(self, user_id: str, task_id: int, amount: int = 1) -> None:
        """增加進度值"""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_tutorial_progress (user_id, task_id, current_progress)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE current_progress = current_progress + %s
                """,
                    (user_id, task_id, amount, amount),
                )
                conn.commit()

    def get_next_unclaimed_task(self, user_id: str) -> Optional[TutorialTask]:
        """獲取下一個未完成或未領取獎勵的任務"""
        tasks = self.get_all_active_tasks()
        progress_list = self.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        for task in tasks:
            progress = progress_map.get(task.task_id)
            if not progress:
                return task
            if progress.is_completed and not progress.reward_claimed:
                return task
            if not progress.is_completed:
                return task
        return None

    def get_completion_rate(self, user_id: str) -> dict:
        """獲取完成率統計"""
        tasks = self.get_all_active_tasks()
        progress_list = self.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        total = len(tasks)
        completed = 0
        claimed = 0

        for task in tasks:
            progress = progress_map.get(task.task_id)
            if progress:
                if progress.is_completed:
                    completed += 1
                if progress.reward_claimed:
                    claimed += 1

        return {
            "total": total,
            "completed": completed,
            "claimed": claimed,
            "rate": completed / total if total > 0 else 0,
        }
