from typing import Dict, Any, List, Optional
from datetime import datetime

from astrbot.api import logger

from ..repositories.mysql_tutorial_repo import MysqlTutorialRepository
from ..repositories.mysql_user_repo import MysqlUserRepository
from ..repositories.mysql_inventory_repo import MysqlInventoryRepository
from ..domain.models import TutorialTask, UserTutorialProgress
from ..utils import get_now


class TutorialService:
    """新手引導教程服務"""

    def __init__(
        self,
        tutorial_repo: MysqlTutorialRepository,
        user_repo: MysqlUserRepository,
        inventory_repo: MysqlInventoryRepository,
    ):
        self.tutorial_repo = tutorial_repo
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo

    def init_user_tutorial(self, user_id: str) -> Dict[str, Any]:
        """初始化用戶教程"""
        self.tutorial_repo.init_user_progress(user_id)
        return {"success": True, "message": "教程已初始化"}

    def get_tutorial_status(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶教程狀態"""
        if not self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用戶不存在，請先註冊"}

        tasks = self.tutorial_repo.get_all_active_tasks()
        progress_list = self.tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        task_status = []
        for task in tasks:
            progress = progress_map.get(task.task_id)
            task_status.append(
                {
                    "task_id": task.task_id,
                    "sequence": task.sequence,
                    "category": task.category,
                    "title": task.title,
                    "description": task.description,
                    "target_type": task.target_type,
                    "target_value": task.target_value,
                    "current_progress": progress.current_progress if progress else 0,
                    "is_completed": progress.is_completed if progress else False,
                    "reward_claimed": progress.reward_claimed if progress else False,
                    "reward_coins": task.reward_coins,
                    "reward_premium": task.reward_premium,
                    "hint": task.hint,
                }
            )

        completion = self.tutorial_repo.get_completion_rate(user_id)

        return {
            "success": True,
            "tasks": task_status,
            "completion_rate": completion["rate"],
            "total_tasks": completion["total"],
            "completed_tasks": completion["completed"],
            "claimed_tasks": completion["claimed"],
            "next_task": self._get_next_task_info(user_id),
        }

    def _get_next_task_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """獲取下一個待辦任務信息"""
        next_task = self.tutorial_repo.get_next_unclaimed_task(user_id)
        if not next_task:
            return None

        progress = self.tutorial_repo.get_user_progress_for_task(
            user_id, next_task.task_id
        )

        return {
            "task_id": next_task.task_id,
            "sequence": next_task.sequence,
            "title": next_task.title,
            "description": next_task.description,
            "hint": next_task.hint,
            "current_progress": progress.current_progress if progress else 0,
            "target_value": next_task.target_value,
            "is_completed": progress.is_completed if progress else False,
            "reward_claimed": progress.reward_claimed if progress else False,
        }

    def check_command_progress(self, user_id: str, command: str) -> bool:
        """檢查指令是否觸發任務進度"""
        tasks = self.tutorial_repo.get_all_active_tasks()
        progress_list = self.tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        for task in tasks:
            if task.target_type != "command":
                continue

            progress = progress_map.get(task.task_id)
            if progress and progress.is_completed:
                continue

            if task.target_command:
                if command.strip().lower() == task.target_command.strip().lower():
                    self.tutorial_repo.complete_task(user_id, task.task_id)
                    logger.info(
                        f"[Tutorial] 用戶 {user_id} 完成任務 {task.task_id}: {task.title}"
                    )
                    return True
                if task.target_command in command:
                    self.tutorial_repo.complete_task(user_id, task.task_id)
                    logger.info(
                        f"[Tutorial] 用戶 {user_id} 完成任務 {task.task_id}: {task.title}"
                    )
                    return True

        return False

    def check_fish_count_progress(
        self, user_id: str, current_fish_count: int
    ) -> List[TutorialTask]:
        """檢查釣魚次數進度"""
        completed_tasks = []
        tasks = self.tutorial_repo.get_all_active_tasks()
        progress_list = self.tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        for task in tasks:
            if task.target_type != "fish_count":
                continue

            progress = progress_map.get(task.task_id)
            if progress and progress.is_completed:
                continue

            if current_fish_count >= task.target_value:
                self.tutorial_repo.complete_task(user_id, task.task_id)
                completed_tasks.append(task)
                logger.info(
                    f"[Tutorial] 用戶 {user_id} 完成任務 {task.task_id}: {task.title}"
                )
            else:
                self.tutorial_repo.update_progress(
                    user_id, task.task_id, current_fish_count
                )

        return completed_tasks

    def check_coins_progress(
        self, user_id: str, current_coins: int
    ) -> List[TutorialTask]:
        """檢查金幣數量進度"""
        completed_tasks = []
        tasks = self.tutorial_repo.get_all_active_tasks()
        progress_list = self.tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        for task in tasks:
            if task.target_type != "coins":
                continue

            progress = progress_map.get(task.task_id)
            if progress and progress.is_completed:
                continue

            if current_coins >= task.target_value:
                self.tutorial_repo.complete_task(user_id, task.task_id)
                completed_tasks.append(task)
            else:
                self.tutorial_repo.update_progress(user_id, task.task_id, current_coins)

        return completed_tasks

    def claim_task_reward(self, user_id: str, task_id: int) -> Dict[str, Any]:
        """領取任務獎勵"""
        task = self.tutorial_repo.get_task_by_id(task_id)
        if not task:
            return {"success": False, "message": "任務不存在"}

        progress = self.tutorial_repo.get_user_progress_for_task(user_id, task_id)
        if not progress:
            return {"success": False, "message": "請先完成任務"}

        if not progress.is_completed:
            return {
                "success": False,
                "message": f"任務尚未完成\n\n當前進度：{progress.current_progress}/{task.target_value}\n提示：{task.hint or '無'}",
            }

        if progress.reward_claimed:
            return {"success": False, "message": "獎勵已領取"}

        claimed = self.tutorial_repo.claim_reward(user_id, task_id)
        if not claimed:
            return {"success": False, "message": "領取失敗，請稍後重試"}

        user = self.user_repo.get_by_id(user_id)
        if user:
            new_coins = user.coins + task.reward_coins
            new_premium = user.premium_currency + task.reward_premium
            self.user_repo.update_fields(
                user_id, coins=new_coins, premium_currency=new_premium
            )

        reward_msg = []
        if task.reward_coins > 0:
            reward_msg.append(f"💰 {task.reward_coins} 金幣")
        if task.reward_premium > 0:
            reward_msg.append(f"💎 {task.reward_premium} 高級貨幣")

        return {
            "success": True,
            "message": f"🎉 已領取「{task.title}」獎勵！\n獲得：{' + '.join(reward_msg)}",
        }

    def claim_all_rewards(self, user_id: str) -> Dict[str, Any]:
        """領取所有可用獎勵"""
        tasks = self.tutorial_repo.get_all_active_tasks()
        progress_list = self.tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        total_coins = 0
        total_premium = 0
        claimed_count = 0
        failed_tasks = []

        for task in tasks:
            progress = progress_map.get(task.task_id)
            if not progress:
                continue
            if not progress.is_completed:
                continue
            if progress.reward_claimed:
                continue

            result = self.claim_task_reward(user_id, task.task_id)
            if result["success"]:
                total_coins += task.reward_coins
                total_premium += task.reward_premium
                claimed_count += 1
            else:
                failed_tasks.append(task.title)

        if claimed_count == 0:
            return {
                "success": False,
                "message": "沒有可領取的獎勵\n\n提示：完成任務後才能領取獎勵",
            }

        reward_msg = []
        if total_coins > 0:
            reward_msg.append(f"💰 {total_coins} 金幣")
        if total_premium > 0:
            reward_msg.append(f"💎 {total_premium} 高級貨幣")

        return {
            "success": True,
            "message": f"🎉 已領取 {claimed_count} 個任務獎勵！\n總計：{' + '.join(reward_msg)}",
            "claimed_count": claimed_count,
            "total_coins": total_coins,
            "total_premium": total_premium,
        }

    def get_task_hint(self, user_id: str) -> str:
        """獲取當前任務提示"""
        next_task = self._get_next_task_info(user_id)
        if not next_task:
            return "🎉 恭喜！你已完成所有新手任務！"

        progress_bar = self._build_progress_bar(
            next_task["current_progress"], next_task["target_value"]
        )

        hint = next_task.get("hint") or f"完成條件：{next_task['description']}"

        return (
            f"📋 當前任務：{next_task['title']}\n"
            f"📝 {next_task['description']}\n"
            f"📊 進度：{progress_bar} {next_task['current_progress']}/{next_task['target_value']}\n"
            f"💡 {hint}"
        )

    def _build_progress_bar(self, current: int, total: int, width: int = 10) -> str:
        """構建進度條"""
        if total <= 0:
            return "██████████"
        filled = int((current / total) * width)
        filled = min(filled, width)
        return "█" * filled + "░" * (width - filled)

    def format_tutorial_display(self, user_id: str) -> str:
        """格式化教程顯示"""
        status = self.get_tutorial_status(user_id)
        if not status["success"]:
            return status["message"]

        tasks = status["tasks"]
        completion_rate = status["completion_rate"]

        lines = [f"📖 新手引導任務（完成度：{completion_rate * 100:.0f}%）"]
        lines.append("═" * 30)

        category_icons = {
            "core": "🌊",
            "economy": "💰",
            "equipment": "⚔️",
            "social": "👥",
        }

        current_category = None
        for task in tasks:
            cat = task["category"]
            if cat != current_category:
                icon = category_icons.get(cat, "📌")
                lines.append(f"\n{icon} {cat.upper()}")
                current_category = cat

            if task["reward_claimed"]:
                status_icon = "✅"
            elif task["is_completed"]:
                status_icon = "🎁"
            else:
                status_icon = "⬜"

            progress_str = ""
            if not task["is_completed"] and task["target_value"] > 1:
                progress_str = f" ({task['current_progress']}/{task['target_value']})"

            lines.append(
                f"  {status_icon} {task['sequence']}. {task['title']}{progress_str}"
            )

        lines.append("\n" + "═" * 30)
        lines.append("💡 /教程 領取 - 領取已完成任務獎勵")
        lines.append("💡 /教程 提示 - 查看當前任務提示")

        next_task = status.get("next_task")
        if next_task:
            lines.append(f"\n📍 下一任務：{next_task['title']}")
            if next_task.get("hint"):
                lines.append(f"   → {next_task['hint']}")

        return "\n".join(lines)
