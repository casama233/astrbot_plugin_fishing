from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def guild_dispatch(self: "FishingPlugin", event: AstrMessageEvent):
    """公會指令分發"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if not self.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    if len(parts) == 1:
        async for r in view_my_guild(self, event):
            yield r
        return

    sub_cmd = parts[1].lower() if len(parts) > 1 else ""

    if sub_cmd in ["創建", "create"]:
        async for r in create_guild_handler(self, event):
            yield r
    elif sub_cmd in ["加入", "join"]:
        async for r in join_guild_handler(self, event):
            yield r
    elif sub_cmd in ["退出", "離開", "leave"]:
        async for r in leave_guild_handler(self, event):
            yield r
    elif sub_cmd in ["信息", "詳情", "info"]:
        async for r in guild_info_handler(self, event):
            yield r
    elif sub_cmd in ["列表", "全部", "list"]:
        async for r in guild_list_handler(self, event):
            yield r
    elif sub_cmd in ["搜索", "尋找", "search"]:
        async for r in search_guild_handler(self, event):
            yield r
    elif sub_cmd in ["排行", "排行榜", "ranking"]:
        async for r in guild_ranking_handler(self, event):
            yield r
    elif sub_cmd in ["貢獻", "捐獻", "contribute"]:
        async for r in contribute_handler(self, event):
            yield r
    elif sub_cmd in ["商店", "貢獻商店", "shop"]:
        async for r in contribution_shop_handler(self, event):
            yield r
    elif sub_cmd in ["兌換", "購買", "buy"]:
        async for r in purchase_handler(self, event):
            yield r
    elif sub_cmd in ["buff", "增益"]:
        async for r in buff_handler(self, event):
            yield r
    elif sub_cmd in ["設置幹部", "任命", "setofficer"]:
        async for r in set_officer_handler(self, event):
            yield r
    elif sub_cmd in ["踢出", "踢人", "kick"]:
        async for r in kick_member_handler(self, event):
            yield r
    elif sub_cmd in ["轉讓", "transfer"]:
        async for r in transfer_leader_handler(self, event):
            yield r
    elif sub_cmd in ["編輯", "公告", "edit"]:
        async for r in edit_guild_handler(self, event):
            yield r
    elif sub_cmd in ["解散", "disband"]:
        async for r in disband_guild_handler(self, event):
            yield r
    elif sub_cmd in ["貢獻排行", "貢獻榜"]:
        async for r in contribution_ranking_handler(self, event):
            yield r
    else:
        async for r in view_my_guild(self, event):
            yield r


async def view_my_guild(self: "FishingPlugin", event: AstrMessageEvent):
    """查看我的公會"""
    user_id = self._get_effective_user_id(event)
    result = self.guild_service.get_user_guild_info(user_id)

    if not result.get("success"):
        yield event.plain_result(
            f"{result.get('message', '你沒有加入任何公會')}\n\n"
            "💡 使用方式：\n"
            "• /公會 列表 - 查看所有公會\n"
            "• /公會 搜索 [關鍵字] - 搜索公會\n"
            "• /公會 創建 [名稱] - 創建公會"
        )
        return

    guild = result["guild"]
    member = result["member"]
    members = result["members"]
    max_members = result["max_members"]

    role_names = {"leader": "會長", "officer": "幹部", "member": "成員"}
    role_icons = {"leader": "👑", "officer": "⭐", "member": "👤"}

    lines = [
        f"🏘️ 【{guild.name}】",
        f"════════════════════════",
        f"📊 等級：Lv.{guild.level}",
        f"👥 成員：{guild.member_count}/{max_members}",
        f"🐟 總漁獲：{guild.total_fish_caught:,}",
        f"💰 總收入：{guild.total_coins_earned:,}",
        f"💎 我的貢獻：{member.contribution}",
        "",
    ]

    if guild.description:
        lines.append(f"📝 公告：{guild.description}")
        lines.append("")

    lines.append("📜 成員列表：")
    for idx, m in enumerate(members[:10], 1):
        role_icon = role_icons.get(m.role, "👤")
        role_name = role_names.get(m.role, "成員")
        lines.append(f" {role_icon} {role_name} - 貢獻: {m.contribution}")

    if len(members) > 10:
        lines.append(f" ... 還有 {len(members) - 10} 名成員")

    lines.append("")
    lines.append("💡 可用指令：/公會 貢獻 /公會 商店 /公會 buff")

    yield event.plain_result("\n".join(lines))


async def create_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """創建公會"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result(
            "❌ 請指定公會名稱！\n"
            "用法：/公會 創建 [名稱] [描述]\n"
            f"創建費用：{self.guild_service.GUILD_CONFIG['create_cost']:,} 金幣"
        )
        return

    name = parts[2]
    description = " ".join(parts[3:]) if len(parts) > 3 else None

    result = self.guild_service.create_guild(user_id, name, description)
    yield event.plain_result(result["message"])


async def join_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """加入公會"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result(
            "❌ 請指定公會 ID！\n"
            "用法：/公會 加入 [公會ID]\n"
            "💡 使用 /公會 列表 或 /公會 搜索 來查找公會"
        )
        return

    try:
        guild_id = int(parts[2])
    except ValueError:
        yield event.plain_result("❌ 公會 ID 必須是數字！")
        return

    result = self.guild_service.join_guild(user_id, guild_id)
    yield event.plain_result(result["message"])


async def leave_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """退出公會"""
    user_id = self._get_effective_user_id(event)
    result = self.guild_service.leave_guild(user_id)
    yield event.plain_result(result["message"])


async def guild_info_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """查看公會詳情"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) >= 3:
        try:
            guild_id = int(parts[2])
        except ValueError:
            yield event.plain_result("❌ 公會 ID 必須是數字！")
            return
    else:
        guild = self.guild_repo.get_user_guild(user_id)
        if not guild:
            yield event.plain_result("❌ 你沒有加入任何公會，請指定公會 ID")
            return
        guild_id = guild.guild_id

    result = self.guild_service.get_guild_info(guild_id)
    if not result.get("success"):
        yield event.plain_result(result.get("message", "公會不存在"))
        return

    guild = result["guild"]
    members = result["members"]
    max_members = result["max_members"]

    display = self.guild_service.format_guild_display(guild, members, max_members)
    yield event.plain_result(display)


async def guild_list_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """查看公會列表"""
    result = self.guild_service.get_all_guilds(20, 0)

    if not result.get("success"):
        yield event.plain_result(result.get("message", "目前沒有任何公會"))
        return

    lines = ["📋 【公會列表】", "════════════════════════"]

    for g in result["guilds"]:
        lines.append(f"#{g['id']} {g['name']} (Lv.{g['level']}) - {g['members']}人")

    lines.append("")
    lines.append("💡 使用 /公會 加入 [ID] 加入公會")

    yield event.plain_result("\n".join(lines))


async def search_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """搜索公會"""
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result("❌ 請輸入搜索關鍵字！\n用法：/公會 搜索 [關鍵字]")
        return

    keyword = " ".join(parts[2:])
    result = self.guild_service.search_guilds(keyword)

    if not result.get("success"):
        yield event.plain_result(result.get("message", "沒有找到匹配的公會"))
        return

    lines = [f"🔍 搜索結果「{keyword}」", "════════════════════════"]

    for g in result["guilds"]:
        lines.append(f"#{g['id']} {g['name']} (Lv.{g['level']}) - {g['members']}人")
        lines.append(f"   {g['description'][:30]}...")

    lines.append("")
    lines.append("💡 使用 /公會 加入 [ID] 加入公會")

    yield event.plain_result("\n".join(lines))


async def guild_ranking_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """公會排行榜"""
    parts = event.message_str.strip().split()

    sort_by = "fish"
    if len(parts) >= 3:
        sort_key = parts[2].lower()
        if sort_key in ["等級", "level", "lv"]:
            sort_by = "level"
        elif sort_key in ["人數", "members", "成員"]:
            sort_by = "members"
        elif sort_key in ["金幣", "coins", "收入"]:
            sort_by = "coins"

    ranking = self.guild_service.get_guild_ranking(10, sort_by)

    sort_names = {
        "fish": "漁獲",
        "level": "等級",
        "members": "成員數",
        "coins": "總收入",
    }
    sort_name = sort_names.get(sort_by, "漁獲")

    lines = [f"🏆 【公會排行榜】按{sort_name}排序", "════════════════════════"]

    for r in ranking:
        lines.append(
            f"#{r['rank']} {r['name']} (Lv.{r['level']}) - "
            f"🐟{r['total_fish']:,} 👥{r['member_count']} 💰{r['total_coins']:,}"
        )

    lines.append("")
    lines.append("💡 可用排序：/公會 排行 [等級/人數/金幣]")

    yield event.plain_result("\n".join(lines))


async def contribute_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """貢獻金幣"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result(
            "❌ 請指定貢獻金額！\n用法：/公會 貢獻 [金額]\n💡 每 100 金幣 = 1 貢獻值"
        )
        return

    try:
        amount = int(parts[2])
        if amount < 100:
            yield event.plain_result("❌ 最低貢獻金額為 100 金幣")
            return
    except ValueError:
        yield event.plain_result("❌ 金額必須是數字！")
        return

    result = self.guild_service.contribute(user_id, amount)
    yield event.plain_result(result["message"])


async def contribution_shop_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """貢獻值商店"""
    result = self.guild_service.get_contribution_shop()

    lines = ["🛒 【貢獻值商店】", "════════════════════════"]

    for item in result["items"]:
        lines.append(f"• {item['name']} - {item['cost']} 貢獻值")

    lines.append("")
    lines.append("💡 使用 /公會 兌換 [物品ID] 購買")

    yield event.plain_result("\n".join(lines))


async def purchase_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """從貢獻商店購買"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result(
            "❌ 請指定物品 ID！\n用法：/公會 兌換 [物品ID]\n💡 使用 /公會 商店 查看可用物品"
        )
        return

    item_id = parts[2]
    result = self.guild_service.purchase_from_shop(user_id, item_id)
    yield event.plain_result(result["message"])


async def buff_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """公會 Buff"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        buffs_display = self.guild_service.get_guild_buffs_display(user_id)
        buff_list = "\n".join(
            [
                f"• {v['icon']} {v['name']} (上限 {v['max_value'] * 100:.0f}%)"
                for v in self.guild_service.BUFF_CONFIG.values()
            ]
        )
        yield event.plain_result(
            f"{buffs_display}\n\n"
            f"════════════════════════\n"
            f"📖 可購買 Buff：\n{buff_list}\n\n"
            f"💡 使用 /公會 buff [類型] [數值%] [時長小時]"
        )
        return

    buff_type = parts[2].lower()
    buff_map = {
        "釣魚速度": "fishing_speed",
        "稀有": "rare_chance",
        "金幣": "coin_bonus",
        "經驗": "exp_bonus",
        "fishing_speed": "fishing_speed",
        "rare_chance": "rare_chance",
        "coin_bonus": "coin_bonus",
        "exp_bonus": "exp_bonus",
    }

    if buff_type not in buff_map:
        yield event.plain_result(
            "❌ 無效的 Buff 類型！可用：釣魚速度、稀有、金幣、經驗"
        )
        return

    buff_type = buff_map[buff_type]

    if len(parts) < 5:
        yield event.plain_result(
            "❌ 請指定數值和時長！\n用法：/公會 buff [類型] [數值%] [時長小時]"
        )
        return

    try:
        value = float(parts[3].replace("%", "")) / 100
        duration = int(parts[4])
    except ValueError:
        yield event.plain_result("❌ 數值和時長必須是數字！")
        return

    result = self.guild_service.purchase_guild_buff(user_id, buff_type, value, duration)
    yield event.plain_result(result["message"])


async def set_officer_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """設置幹部"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 4:
        yield event.plain_result(
            "❌ 請指定目標用戶和操作！\n用法：/公會 設置幹部 [用戶ID] [設為/取消]"
        )
        return

    target_id = parts[2]
    is_officer = parts[3] in ["設為", "任命", "true", "1"]

    result = self.guild_service.set_officer(user_id, target_id, is_officer)
    yield event.plain_result(result["message"])


async def kick_member_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """踢出成員"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result("❌ 請指定要踢出的成員！\n用法：/公會 踢出 [用戶ID]")
        return

    target_id = parts[2]
    result = self.guild_service.kick_member(user_id, target_id)
    yield event.plain_result(result["message"])


async def transfer_leader_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """轉讓會長"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 3:
        yield event.plain_result("❌ 請指定新會長！\n用法：/公會 轉讓 [用戶ID]")
        return

    new_leader_id = parts[2]
    result = self.guild_service.transfer_leader(user_id, new_leader_id)
    yield event.plain_result(result["message"])


async def edit_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """編輯公會信息"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    if len(parts) < 4:
        yield event.plain_result(
            "❌ 請指定要編輯的內容！\n用法：/公會 編輯 [描述/公告] [內容]"
        )
        return

    field = parts[2].lower()
    content = " ".join(parts[3:])

    if field in ["描述", "公告", "description", "desc"]:
        result = self.guild_service.update_guild_info(user_id, description=content)
    elif field in ["徽章", "emblem"]:
        result = self.guild_service.update_guild_info(user_id, emblem=content)
    else:
        yield event.plain_result("❌ 無效的編輯項！可用：描述、徽章")
        return

    yield event.plain_result(result["message"])


async def disband_guild_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """解散公會"""
    user_id = self._get_effective_user_id(event)
    parts = event.message_str.strip().split()

    confirm = len(parts) >= 3 and parts[2] in ["確認", "confirm", "yes"]
    result = self.guild_service.disband_guild_with_confirm(user_id, confirm)
    yield event.plain_result(result["message"])


async def contribution_ranking_handler(self: "FishingPlugin", event: AstrMessageEvent):
    """公會內貢獻排行"""
    user_id = self._get_effective_user_id(event)
    result = self.guild_service.get_guild_contribution_ranking(user_id)

    if not result.get("success"):
        yield event.plain_result(result.get("message", "獲取排行失敗"))
        return

    lines = ["🏅 【公會貢獻排行】", "════════════════════════"]

    for idx, r in enumerate(result["ranking"], 1):
        lines.append(f"#{idx} 用戶 {r['user_id']} - {r['contribution']} 貢獻值")

    lines.append("")
    lines.append(f"💎 我的貢獻：{result['my_contribution']}")

    yield event.plain_result("\n".join(lines))
