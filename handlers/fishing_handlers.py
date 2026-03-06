from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from ..core.utils import get_now
from ..utils import (
    safe_datetime_handler,
    to_percentage,
    safe_get_file_path,
    get_loading_tip,
    should_send_loading_tip,
    build_tip_result,
)
from ..draw.pokedex import draw_pokedex
from astrbot.api.message_components import Image as AstrImage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


def _normalize_now_for(lst_time):
    """根据 lst_time 的时区信息，规范化当前时间的 tzinfo。"""
    now = get_now()
    if lst_time and lst_time.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    if lst_time and lst_time.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=lst_time.tzinfo)
    return now


def _compute_cooldown_seconds(base_seconds, equipped_accessory):
    """根据是否装备海洋之心动态计算冷却时间。"""
    if equipped_accessory and equipped_accessory.get("name") == "海洋之心":
        return base_seconds / 2
    return base_seconds


def _build_fish_message(result, fishing_cost):
    if result["success"]:
        fish = result["fish"]
        # 构建品质显示
        quality_display = ""
        if fish.get("quality_level") == 1:
            quality_display = " ✨高品质"

        message = (
            f"🎣 恭喜你钓到了：{fish['name']}{quality_display}\n"
            f"✨稀有度：{'★' * fish['rarity']} \n"
            f"⚖️重量：{fish['weight']} 克\n"
            f"💰价值：{fish['value']} 金币\n"
            f"💸消耗：{fishing_cost} 金币/次"
        )
        if "equipment_broken_messages" in result:
            for broken_msg in result["equipment_broken_messages"]:
                message += f"\n{broken_msg}"
        return message
    return f"{result['message']}\n💸消耗：{fishing_cost} 金币/次"


class FishingHandlers:
    def __init__(self, plugin: "FishingPlugin"):
        self.plugin = plugin
        self.user_service = plugin.user_service
        self.fishing_service = plugin.fishing_service
        self.inventory_service = plugin.inventory_service
        self.gacha_service = plugin.gacha_service
        self.market_service = plugin.market_service
        self.shop_service = plugin.shop_service
        self.item_template_repo = plugin.item_template_repo
        self.achievement_service = plugin.achievement_service
        self.aquarium_service = plugin.aquarium_service
        self.exchange_service = plugin.exchange_service

    def _get_fishing_cost(self, user):
        zone = self.plugin.inventory_repo.get_zone_by_id(user.fishing_zone_id)
        return zone.fishing_cost if zone else 10

    async def fish(self, event: AstrMessageEvent):
        """钓鱼"""
        user_id = self.plugin._get_effective_user_id(event)
        user = self.plugin.user_repo.get_by_id(user_id)
        if not user:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
            return
        # 检查用户钓鱼CD
        lst_time = user.last_fishing_time
        info = self.user_service.get_user_current_accessory(user_id)
        if info["success"] is False:
            yield event.plain_result(f"❌ 获取用户饰品信息失败：{info['message']}")
            return
        equipped_accessory = info.get("accessory")
        base_cooldown = self.plugin.game_config["fishing"]["cooldown_seconds"]
        cooldown_seconds = _compute_cooldown_seconds(base_cooldown, equipped_accessory)
        # 修复时区问题
        now = _normalize_now_for(lst_time)
        if lst_time and (now - lst_time).total_seconds() < cooldown_seconds:
            wait_time = cooldown_seconds - (now - lst_time).total_seconds()
            yield event.plain_result(
                f"⏳ 您还需要等待 {int(wait_time)} 秒才能再次钓鱼。"
            )
            return
        fishing_cost = self._get_fishing_cost(user)
        result = self.fishing_service.go_fish(user_id)
        if not result:
            yield event.plain_result("❌ 出错啦！请稍后再试。")
            return
        yield event.plain_result(_build_fish_message(result, fishing_cost))
        if should_send_loading_tip(self.plugin.game_config):
            yield build_tip_result(event, get_loading_tip("fishing"))

    async def auto_fish(self, event: AstrMessageEvent):
        """自动钓鱼"""
        user_id = self.plugin._get_effective_user_id(event)
        result = self.fishing_service.toggle_auto_fishing(user_id)
        yield event.plain_result(result["message"])

    async def fishing_area(self, event: AstrMessageEvent):
        """查看或切換釣魚區域"""
        user_id = self.plugin._get_effective_user_id(event)
        args = event.message_str.split()
        if len(args) < 2:
            result = self.fishing_service.get_user_fishing_zones(user_id)
            if not result:
                yield event.plain_result("❌ 系統忙碌中，請稍後再試。")
                return
            if not result.get("success"):
                yield event.plain_result(f"❌ 查看釣魚區域失敗：{result['message']}")
                return
            zones = result.get("zones", [])
            message = "【🌊 釣魚區域列表】\n"
            message += "════════════════════════════\n"
            for zone in zones:
                status_icons = []
                if zone["whether_in_use"]:
                    status_icons.append("✅")
                if not zone["is_active"]:
                    status_icons.append("🚫")
                if zone.get("requires_pass"):
                    status_icons.append("🔑")
                status_text = " ".join(status_icons) if status_icons else ""

                zone_id = zone.get("zone_id")
                zone_name = zone.get("name", "未知區域")
                desc = zone.get("description", "")
                fishing_cost = zone.get("fishing_cost", 10)
                remaining_rare = max(
                    0, zone["daily_rare_fish_quota"] - zone["rare_fish_caught_today"]
                )

                message += f"• ID {zone_id}｜{zone_name} {status_text}\n"
                if desc:
                    message += f"  └─ {desc}\n"
                message += f"  💰 消耗：{fishing_cost} 金幣 / 次\n"
                if zone.get("requires_pass"):
                    required_item_name = zone.get("required_item_name", "通行證")
                    message += f"  🔑 進入需求：{required_item_name}\n"
                if zone.get("available_from") or zone.get("available_until"):
                    message += "  ⏰ 開放時間："
                    if zone.get("available_from") and zone.get("available_until"):
                        from_time = zone["available_from"].strftime("%Y-%m-%d %H:%M")
                        until_time = zone["available_until"].strftime("%Y-%m-%d %H:%M")
                        message += f"{from_time} 至 {until_time}\n"
                    elif zone.get("available_from"):
                        from_time = zone["available_from"].strftime("%Y-%m-%d %H:%M")
                        message += f"{from_time} 開始\n"
                    elif zone.get("available_until"):
                        until_time = zone["available_until"].strftime("%Y-%m-%d %H:%M")
                        message += f"至 {until_time} 結束\n"
                if zone.get("daily_rare_fish_quota", 0) > 0:
                    message += f"  🐟 今日稀有額度：剩餘 {remaining_rare}\n"
                message += "────────────────────────────\n"

            message += "💡 切換區域：/釣魚區域 ID\n"
            message += "💡 示例：/釣魚區域 3"
            yield event.plain_result(message)
            return
        zone_id = args[1]
        if not zone_id.isdigit():
            yield event.plain_result("❌ 釣魚區域 ID 必須是數字，請檢查後重試。")
            return
        zone_id = int(zone_id)

        # 动态获取所有有效的区域ID
        all_zones = self.plugin.fishing_zone_service.get_all_zones()
        valid_zone_ids = [zone["id"] for zone in all_zones]

        if zone_id not in valid_zone_ids:
            yield event.plain_result(
                f"❌ 無效的釣魚區域 ID。\n"
                f"可用 ID：{', '.join(map(str, valid_zone_ids))}"
            )
            yield event.plain_result("💡 請使用：/釣魚區域 <ID>")
            return

        # 切换用户的钓鱼区域
        result = self.fishing_service.set_user_fishing_zone(user_id, zone_id)
        yield event.plain_result(
            result["message"] if result else "❌ 系統忙碌中，請稍後再試。"
        )

    async def fish_pokedex(self, event: AstrMessageEvent):
        """查看鱼类图鉴"""
        user_id = self.plugin._get_effective_user_id(event)
        args = event.message_str.split()
        page = 1
        if len(args) > 1 and args[1].isdigit():
            page = int(args[1])

        pokedex_data = self.fishing_service.get_user_pokedex(user_id)
        if not pokedex_data or not pokedex_data.get("success"):
            yield event.plain_result(
                f"❌ 查看图鉴失败: {pokedex_data.get('message', '未知错误')}"
            )
            return

        pokedex_list = pokedex_data.get("pokedex", [])
        if not pokedex_list:
            yield event.plain_result("❌ 您还没有捕捉到任何鱼类，快去钓鱼吧！")
            return

        user_info = self.plugin.user_repo.get_by_id(user_id)

        # 绘制图片
        output_path = safe_get_file_path(
            self.plugin, f"pokedex_{user_id}_page_{page}.png"
        )

        try:
            await draw_pokedex(
                pokedex_data,
                {"nickname": user_info.nickname, "user_id": user_id},
                output_path,
                page=page,
                data_dir=self.plugin.data_dir,
            )
            yield event.image_result(output_path)
        except Exception as e:
            logger.error(f"绘制图鉴图片失败: {e}", exc_info=e)
            yield event.plain_result("❌ 绘制图鉴时发生错误，请稍后再试或联系管理员。")
