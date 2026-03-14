from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from astrbot.api import logger

from ..repositories.mysql_guild_repo import MysqlGuildRepository
from ..repositories.mysql_user_repo import MysqlUserRepository
from ..domain.models import Guild, GuildMember, GuildBuff
from ..utils import get_now


class GuildService:
    """公會服務"""

    GUILD_CONFIG = {
        "create_cost": 100000,
        "max_members_base": 30,
        "max_members_per_level": 5,
        "contribution_reward_ratio": 0.1,
        "exp_per_contribution": 1,
        "level_exp_base": 1000,
        "level_exp_multiplier": 1.5,
    }

    BUFF_CONFIG = {
        "fishing_speed": {
            "name": "釣魚速度",
            "icon": "⚡",
            "max_value": 0.5,
            "cost_per_percent": 100,
        },
        "rare_chance": {
            "name": "稀有魚機率",
            "icon": "🌟",
            "max_value": 0.3,
            "cost_per_percent": 200,
        },
        "coin_bonus": {
            "name": "金幣加成",
            "icon": "💰",
            "max_value": 0.5,
            "cost_per_percent": 150,
        },
        "exp_bonus": {
            "name": "經驗加成",
            "icon": "📈",
            "max_value": 0.5,
            "cost_per_percent": 100,
        },
    }

    CONTRIBUTION_SHOP = {
        "buff_24h": {
            "name": "公會 Buff (24小時)",
            "cost": 500,
            "type": "buff_purchase",
        },
        "buff_72h": {
            "name": "公會 Buff (72小時)",
            "cost": 1200,
            "type": "buff_purchase",
        },
        "title_member": {"name": "公會成員稱號", "cost": 1000, "type": "title"},
        "title_officer": {"name": "公會幹部稱號", "cost": 5000, "type": "title"},
        "coins_1000": {
            "name": "1000 金幣",
            "cost": 100,
            "type": "coins",
            "value": 1000,
        },
        "coins_5000": {
            "name": "5000 金幣",
            "cost": 450,
            "type": "coins",
            "value": 5000,
        },
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

    def get_guild_ranking(
        self, limit: int = 10, sort_by: str = "fish"
    ) -> List[Dict[str, Any]]:
        """獲取公會排行榜（支持多維度排序）"""
        guilds = self.guild_repo.get_top_guilds(limit, sort_by)
        return [
            {
                "rank": idx + 1,
                "name": g.name,
                "level": g.level,
                "member_count": g.member_count,
                "total_fish": g.total_fish_caught,
                "total_coins": g.total_coins_earned,
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
            lines.append(f" {role_icon} {role_name} - 貢獻: {m.contribution}")

        if len(members) > 10:
            lines.append(f" ... 還有 {len(members) - 10} 名成員")

        return "\n".join(lines)

    def set_officer(
        self, leader_id: str, target_id: str, is_officer: bool = True
    ) -> Dict[str, Any]:
        """設置/取消幹部"""
        guild = self.guild_repo.get_guild_by_leader(leader_id)
        if not guild:
            return {"success": False, "message": "你不是公會會長"}

        member = self.guild_repo.get_member(target_id)
        if not member or member.guild_id != guild.guild_id:
            return {"success": False, "message": "該用戶不是公會成員"}

        if member.role == "leader":
            return {"success": False, "message": "無法修改會長的角色"}

        new_role = "officer" if is_officer else "member"
        self.guild_repo.update_member_role(guild.guild_id, target_id, new_role)

        action = "設為幹部" if is_officer else "取消幹部"
        return {"success": True, "message": f"已將成員 {action}"}

    def update_guild_info(
        self, leader_id: str, description: str = None, emblem: str = None
    ) -> Dict[str, Any]:
        """更新公會公告/描述"""
        guild = self.guild_repo.get_guild_by_leader(leader_id)
        if not guild:
            return {"success": False, "message": "你不是公會會長"}

        if not self.guild_repo.update_guild_info(guild.guild_id, description, emblem):
            return {"success": False, "message": "更新失敗"}

        return {"success": True, "message": "公會信息已更新"}

    def search_guilds(self, keyword: str, limit: int = 10) -> Dict[str, Any]:
        """搜索公會"""
        guilds = self.guild_repo.search_guilds(keyword, limit)
        if not guilds:
            return {"success": False, "message": "沒有找到匹配的公會"}

        result = []
        for g in guilds:
            result.append(
                {
                    "id": g.guild_id,
                    "name": g.name,
                    "level": g.level,
                    "members": g.member_count,
                    "description": g.description or "無描述",
                }
            )

        return {"success": True, "guilds": result}

    def get_all_guilds(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """獲取公會列表"""
        guilds = self.guild_repo.get_all_guilds(limit, offset)
        if not guilds:
            return {"success": False, "message": "目前沒有任何公會"}

        result = []
        for g in guilds:
            result.append(
                {
                    "id": g.guild_id,
                    "name": g.name,
                    "level": g.level,
                    "members": g.member_count,
                    "description": g.description or "無描述",
                }
            )

        return {"success": True, "guilds": result}

    def get_user_buffs(self, user_id: str) -> Dict[str, float]:
        """獲取用戶的公會 Buff 加成"""
        buffs = self.guild_repo.get_user_guild_buffs(user_id)
        result = {}
        for buff in buffs:
            if buff.buff_type not in result:
                result[buff.buff_type] = 0
            result[buff.buff_type] += buff.buff_value
        return result

    def purchase_guild_buff(
        self, user_id: str, buff_type: str, value: float, duration_hours: int
    ) -> Dict[str, Any]:
        """購買公會 Buff（使用貢獻值）"""
        if buff_type not in self.BUFF_CONFIG:
            return {"success": False, "message": "無效的 Buff 類型"}

        member = self.guild_repo.get_member(user_id)
        if not member:
            return {"success": False, "message": "你沒有加入任何公會"}

        config = self.BUFF_CONFIG[buff_type]
        cost = int(config["cost_per_percent"] * value * 100)

        if member.contribution < cost:
            return {"success": False, "message": f"貢獻值不足！需要 {cost} 貢獻值"}

        if value > config["max_value"]:
            return {
                "success": False,
                "message": f"Buff 值超出上限（最大 {config['max_value'] * 100}%）",
            }

        self.guild_repo.add_contribution(user_id, -cost)
        self.guild_repo.add_guild_buff(
            member.guild_id, buff_type, value, duration_hours
        )

        return {
            "success": True,
            "message": f"✅ 已為公會購買 {config['name']} +{value * 100:.0f}%（{duration_hours}小時）\n花費 {cost} 貢獻值",
        }

    def get_contribution_shop(self) -> Dict[str, Any]:
        """獲取貢獻值商店"""
        items = []
        for item_id, item in self.CONTRIBUTION_SHOP.items():
            items.append(
                {
                    "id": item_id,
                    "name": item["name"],
                    "cost": item["cost"],
                    "type": item["type"],
                }
            )
        return {"success": True, "items": items}

    def purchase_from_shop(self, user_id: str, item_id: str) -> Dict[str, Any]:
        """從貢獻值商店購買物品"""
        if item_id not in self.CONTRIBUTION_SHOP:
            return {"success": False, "message": "無效的物品 ID"}

        item = self.CONTRIBUTION_SHOP[item_id]
        member = self.guild_repo.get_member(user_id)

        if not member:
            return {"success": False, "message": "你沒有加入任何公會"}

        if member.contribution < item["cost"]:
            return {
                "success": False,
                "message": f"貢獻值不足！需要 {item['cost']} 貢獻值",
            }

        self.guild_repo.add_contribution(user_id, -item["cost"])

        if item["type"] == "coins":
            user = self.user_repo.get_by_id(user_id)
            if user:
                user.coins += item["value"]
                self.user_repo.update(user)
            return {
                "success": True,
                "message": f"✅ 成功兌換 {item['name']}\n花費 {item['cost']} 貢獻值",
            }
        elif item["type"] == "buff_purchase":
            return self._handle_buff_purchase(user_id, item_id)

        return {"success": True, "message": f"✅ 成功購買 {item['name']}"}

    def _handle_buff_purchase(self, user_id: str, item_id: str) -> Dict[str, Any]:
        """處理 Buff 購買"""
        member = self.guild_repo.get_member(user_id)
        if not member:
            return {"success": False, "message": "獲取成員信息失敗"}

        if item_id == "buff_24h":
            duration = 24
        elif item_id == "buff_72h":
            duration = 72
        else:
            return {"success": False, "message": "無效的 Buff 包"}

        random_buff_type = "rare_chance"
        self.guild_repo.add_guild_buff(
            member.guild_id, random_buff_type, 0.05, duration
        )

        return {
            "success": True,
            "message": f"✅ 成功為公會購買隨機 Buff！\n獲得：稀有魚機率 +5%（{duration}小時）",
        }

    def get_guild_contribution_ranking(self, user_id: str) -> Dict[str, Any]:
        """獲取公會內貢獻排行"""
        member = self.guild_repo.get_member(user_id)
        if not member:
            return {"success": False, "message": "你沒有加入任何公會"}

        ranking = self.guild_repo.get_guild_contribution_ranking(member.guild_id, 10)

        return {
            "success": True,
            "ranking": ranking,
            "my_contribution": member.contribution,
        }

    def disband_guild_with_confirm(
        self, leader_id: str, confirm: bool = False
    ) -> Dict[str, Any]:
        """解散公會（需要確認）"""
        if not confirm:
            guild = self.guild_repo.get_guild_by_leader(leader_id)
            if not guild:
                return {"success": False, "message": "你不是公會會長"}
            return {
                "success": False,
                "need_confirm": True,
                "message": f"⚠️ 確定要解散公會「{guild.name}」嗎？\n解散後公會數據將無法恢復！\n請再次輸入 /公會 解散 確認 來確認解散",
            }

        return self.disband_guild(leader_id)

    def get_guild_buffs_display(self, user_id: str) -> str:
        """獲取公會 Buff 顯示"""
        buffs = self.get_user_buffs(user_id)
        if not buffs:
            return "無公會 Buff 生效中"

        lines = ["【公會 Buff】"]
        for buff_type, value in buffs.items():
            if buff_type in self.BUFF_CONFIG:
                config = self.BUFF_CONFIG[buff_type]
                lines.append(f"{config['icon']} {config['name']}: +{value * 100:.1f}%")

        return "\n".join(lines)
