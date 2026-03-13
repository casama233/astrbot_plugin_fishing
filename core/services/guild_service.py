from typing import Dict, Any, List, Optional
from datetime import datetime

from astrbot.api import logger

from ..repositories.mysql_guild_repo import MysqlGuildRepository
from ..repositories.mysql_user_repo import MysqlUserRepository
from ..domain.models import Guild, GuildMember
from ..utils import get_now


class GuildService:
    """公會服務"""

    GUILD_CONFIG = {
        "create_cost": 100000,  # 創建公會費用
        "max_members_base": 30,  # 基礎最大成員數
        "max_members_per_level": 5,  # 每級增加的成員上限
        "contribution_reward_ratio": 0.1,  # 貢獻值轉化為金幣獎勵的比例
        "exp_per_contribution": 1,  # 每點貢獻增加的公會經驗
        "level_exp_base": 1000,  # 升級所需經驗基礎值
        "level_exp_multiplier": 1.5,  # 升級經驗倍率
    }

    def __init__(
        self,
        guild_repo: MysqlGuildRepository,
        user_repo: MysqlUserRepository,
    ):
        self.guild_repo = guild_repo
        self.user_repo = user_repo

    def create_guild(
        self, leader_id: str, name: str, description: str = None
    ) -> Dict[str, Any]:
        """創建公會"""
        if not self.user_repo.check_exists(leader_id):
            return {"success": False, "message": "用戶不存在"}

        user = self.user_repo.get_by_id(leader_id)
        if not user:
            return {"success": False, "message": "用戶信息獲取失敗"}

        if user.coins < self.GUILD_CONFIG["create_cost"]:
            return {
                "success": False,
                "message": f"金幣不足！創建公會需要 {self.GUILD_CONFIG['create_cost']} 金幣",
            }

        existing = self.guild_repo.get_user_guild(leader_id)
        if existing:
            return {"success": False, "message": "你已經屬於一個公會，請先退出當前公會"}

        if self.guild_repo.get_guild_by_name(name):
            return {"success": False, "message": f"公會名稱「{name}」已被使用"}

        user.coins -= self.GUILD_CONFIG["create_cost"]
        self.user_repo.update(user)

        guild = self.guild_repo.create_guild(name, leader_id, description)

        return {
            "success": True,
            "message": f"🎉 公會「{name}」創建成功！\n花費 {self.GUILD_CONFIG['create_cost']} 金幣",
            "guild": guild,
        }

    def join_guild(self, user_id: str, guild_id: int) -> Dict[str, Any]:
        """加入公會"""
        if not self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用戶不存在"}

        existing = self.guild_repo.get_user_guild(user_id)
        if existing:
            return {"success": False, "message": "你已經屬於一個公會"}

        guild = self.guild_repo.get_guild_by_id(guild_id)
        if not guild:
            return {"success": False, "message": "公會不存在"}

        if not guild.is_active:
            return {"success": False, "message": "該公會已解散"}

        max_members = self._get_max_members(guild.level)
        if guild.member_count >= max_members:
            return {"success": False, "message": "公會成員已滿"}

        if not self.guild_repo.add_member(guild_id, user_id):
            return {"success": False, "message": "加入公會失敗"}

        return {"success": True, "message": f"🎉 成功加入公會「{guild.name}」！"}

    def leave_guild(self, user_id: str) -> Dict[str, Any]:
        """退出公會"""
        member = self.guild_repo.get_member(user_id)
        if not member:
            return {"success": False, "message": "你沒有加入任何公會"}

        guild = self.guild_repo.get_guild_by_id(member.guild_id)
        if not guild:
            return {"success": False, "message": "公會不存在"}

        if member.role == "leader":
            return {
                "success": False,
                "message": "會長無法直接退出公會，請先轉讓會長或解散公會",
            }

        if not self.guild_repo.remove_member(member.guild_id, user_id):
            return {"success": False, "message": "退出公會失敗"}

        return {"success": True, "message": f"已退出公會「{guild.name}」"}

    def transfer_leader(
        self, current_leader_id: str, new_leader_id: str
    ) -> Dict[str, Any]:
        """轉讓會長"""
        guild = self.guild_repo.get_guild_by_leader(current_leader_id)
        if not guild:
            return {"success": False, "message": "你不是公會會長"}

        new_member = self.guild_repo.get_member(new_leader_id)
        if not new_member or new_member.guild_id != guild.guild_id:
            return {"success": False, "message": "目標用戶不是公會成員"}

        self.guild_repo.update_member_role(guild.guild_id, current_leader_id, "officer")
        self.guild_repo.update_member_role(guild.guild_id, new_leader_id, "leader")

        return {"success": True, "message": f"已將會長職位轉讓給用戶"}

    def kick_member(self, leader_id: str, member_id: str) -> Dict[str, Any]:
        """踢出成員"""
        guild = self.guild_repo.get_guild_by_leader(leader_id)
        if not guild:
            officer = self.guild_repo.get_member(leader_id)
            if not officer or officer.role != "officer":
                return {"success": False, "message": "權限不足"}
            guild = self.guild_repo.get_guild_by_id(officer.guild_id)

        member = self.guild_repo.get_member(member_id)
        if not member or member.guild_id != guild.guild_id:
            return {"success": False, "message": "該用戶不是公會成員"}

        if member.role in ["leader", "officer"]:
            return {"success": False, "message": "無法踢出管理員"}

        if not self.guild_repo.remove_member(guild.guild_id, member_id):
            return {"success": False, "message": "踢出失敗"}

        return {"success": True, "message": "已將該成員踢出公會"}

    def disband_guild(self, leader_id: str) -> Dict[str, Any]:
        """解散公會"""
        guild = self.guild_repo.get_guild_by_leader(leader_id)
        if not guild:
            return {"success": False, "message": "你不是公會會長"}

        self.guild_repo.disband_guild(guild.guild_id)

        return {"success": True, "message": f"公會「{guild.name}」已解散"}

    def contribute(self, user_id: str, amount: int) -> Dict[str, Any]:
        """貢獻金幣"""
        member = self.guild_repo.get_member(user_id)
        if not member:
            return {"success": False, "message": "你沒有加入任何公會"}

        user = self.user_repo.get_by_id(user_id)
        if not user or user.coins < amount:
            return {"success": False, "message": "金幣不足"}

        user.coins -= amount
        self.user_repo.update(user)

        contribution_points = amount // 100
        self.guild_repo.add_contribution(user_id, contribution_points)
        self.guild_repo.add_guild_exp(member.guild_id, contribution_points)
        self.guild_repo.update_guild_stats(member.guild_id, coins_earned=amount)

        return {
            "success": True,
            "message": f"成功貢獻 {amount} 金幣！\n獲得 {contribution_points} 貢獻值",
            "contribution": contribution_points,
        }

    def get_guild_info(self, guild_id: int) -> Dict[str, Any]:
        """獲取公會信息"""
        guild = self.guild_repo.get_guild_by_id(guild_id)
        if not guild:
            return {"success": False, "message": "公會不存在"}

        members = self.guild_repo.get_guild_members(guild_id)
        level_info = self._get_level_info(guild.level)

        return {
            "success": True,
            "guild": guild,
            "members": members,
            "max_members": self._get_max_members(guild.level),
            "next_level_exp": level_info["next_exp"],
        }

    def get_user_guild_info(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶公會信息"""
        guild = self.guild_repo.get_user_guild(user_id)
        if not guild:
            return {
                "success": False,
                "message": "你沒有加入任何公會",
                "has_guild": False,
            }

        member = self.guild_repo.get_member(user_id)
        members = self.guild_repo.get_guild_members(guild.guild_id)

        return {
            "success": True,
            "has_guild": True,
            "guild": guild,
            "member": member,
            "members": members,
            "max_members": self._get_max_members(guild.level),
        }

    def get_guild_ranking(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取公會排行榜"""
        guilds = self.guild_repo.get_top_guilds(limit)
        return [
            {
                "rank": idx + 1,
                "name": g.name,
                "level": g.level,
                "member_count": g.member_count,
                "total_fish": g.total_fish_caught,
            }
            for idx, g in enumerate(guilds)
        ]

    def _get_max_members(self, level: int) -> int:
        """計算最大成員數"""
        base = self.GUILD_CONFIG["max_members_base"]
        per_level = self.GUILD_CONFIG["max_members_per_level"]
        return base + (level - 1) * per_level

    def _get_level_info(self, level: int) -> Dict[str, Any]:
        """獲取等級信息"""
        base = self.GUILD_CONFIG["level_exp_base"]
        multiplier = self.GUILD_CONFIG["level_exp_multiplier"]
        next_exp = int(base * (multiplier ** (level - 1)))
        return {"level": level, "next_exp": next_exp}

    def format_guild_display(
        self, guild: Guild, members: List[GuildMember], max_members: int
    ) -> str:
        """格式化公會顯示"""
        role_names = {"leader": "會長", "officer": "幹部", "member": "成員"}

        lines = [
            f"🏘️ 【{guild.name}】",
            f"════════════════════════",
            f"📊 等級：Lv.{guild.level}",
            f"👥 成員：{guild.member_count}/{max_members}",
            f"🐟 總漁獲：{guild.total_fish_caught:,}",
            f"💰 總收入：{guild.total_coins_earned:,}",
            "",
            "📜 成員列表：",
        ]

        for idx, m in enumerate(members[:10], 1):
            role_icon = {"leader": "👑", "officer": "⭐", "member": "👤"}.get(
                m.role, "👤"
            )
            role_name = role_names.get(m.role, "成員")
            lines.append(f"  {role_icon} {role_name} - 貢獻: {m.contribution}")

        if len(members) > 10:
            lines.append(f"  ... 還有 {len(members) - 10} 名成員")

        return "\n".join(lines)
