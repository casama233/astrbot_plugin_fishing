import os
import time
import re
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from ..draw.rank import draw_fishing_ranking
from ..utils import parse_target_user_id, build_tip_result

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def ranking(plugin: "FishingPlugin", event: AstrMessageEvent):
    """
    查看排行榜。
    支持按不同标准排序，例如：/排行榜 数量 或 /排行榜 重量 或 /排行榜 历史
    默认按金币排名。
    """
    args = event.message_str.split()
    ranking_type = "coins"

    if len(args) > 1:
        sort_key = args[1]
        if sort_key in ["数量", "钓获", "fish"]:
            ranking_type = "fish_count"
        elif sort_key in ["重量", "weight"]:
            ranking_type = "total_weight_caught"
        elif sort_key in ["历史", "最高", "max", "history", "历史最高"]:
            ranking_type = "max_coins"

    # 1. 从服务层获取基础排行榜数据（现在已包含 user_id 和 current_title_id）
    user_data = plugin.user_service.get_leaderboard_data(sort_by=ranking_type).get(
        "leaderboard", []
    )

    if not user_data:
        yield event.plain_result("❌ 当前没有排行榜数据。")
        return

    try:
        from ..draw.list_cards import draw_game_card_list_image

        rank_label = {
            "coins": "金币",
            "fish_count": "钓获数量",
            "total_weight_caught": "钓获重量",
            "max_coins": "历史最高金币",
        }.get(ranking_type, "金币")

        rows = []
        for idx, u in enumerate(user_data[:20], start=1):
            nick = u.get("nickname", "未知用户")
            title = u.get("title", "无称号")
            score = (
                u.get("max_coins", 0)
                if ranking_type == "max_coins"
                else u.get(ranking_type, u.get("coins", 0))
            )
            rows.append(
                f"#{idx}  {nick} 【{title}】  {rank_label}:{score}  钓获:{u.get('fish_count', 0)}"
            )

        image = draw_game_card_list_image(
            title="🏆 排行榜",
            sections=[{"title": f"按{rank_label}排序", "rows": rows}],
            subtitle=f"TOP {min(len(user_data), 20)}",
            footer="💡 可用：/排行榜 数量  /排行榜 重量  /排行榜 历史",
            icon="🏆",
        )
        user_id_for_filename = plugin._get_effective_user_id(event)
        image_path = os.path.join(
            plugin.tmp_dir, f"ranking_card_{user_id_for_filename}.png"
        )
        image.save(image_path)
        yield event.image_result(image_path)
        return
    except Exception:
        pass

    # 2. 遍历列表，为每个用户查询并填充装备和称号的【名称】
    for user_dict in user_data:
        user_id = user_dict.get("user_id")

        # 如果（因为某些意外）没有 user_id，则跳过查询，使用默认值
        if not user_id:
            user_dict["title"] = "无称号"
            user_dict["fishing_rod"] = "无鱼竿"
            user_dict["accessory"] = "无饰品"
            user_dict["total_weight_caught"] = user_dict.get("total_weight_caught", 0)
            continue

        # 获取鱼竿名称
        rod_name = "无鱼竿"
        rod_instance = plugin.inventory_repo.get_user_equipped_rod(user_id)
        if rod_instance:
            rod_template = plugin.item_template_repo.get_rod_by_id(rod_instance.rod_id)
            if rod_template:
                rod_name = rod_template.name
        user_dict["fishing_rod"] = rod_name

        # 获取饰品名称
        accessory_name = "无饰品"
        accessory_instance = plugin.inventory_repo.get_user_equipped_accessory(user_id)
        if accessory_instance:
            accessory_template = plugin.item_template_repo.get_accessory_by_id(
                accessory_instance.accessory_id
            )
            if accessory_template:
                accessory_name = accessory_template.name
        user_dict["accessory"] = accessory_name

        # 获取称号信息（包括 display_format）
        title_info_dict = None
        if current_title_id := user_dict.get("current_title_id"):
            title_info = plugin.item_template_repo.get_title_by_id(current_title_id)
            if title_info:
                title_info_dict = {
                    "name": title_info.name,
                    "display_format": title_info.display_format
                    if hasattr(title_info, "display_format")
                    else "{name}",
                }
                title_name = title_info.name
        user_dict["title"] = title_name
        user_dict["title_info"] = title_info_dict  # 添加完整的稱號信息

        # 确保重量字段存在，以防万一
        user_dict["total_weight_caught"] = user_dict.get("total_weight_caught", 0)

    # 3. 绘制并发送图片
    user_id_for_filename = plugin._get_effective_user_id(event)
    unique_id = getattr(
        event, "message_id", f"{user_id_for_filename}_{int(time.time())}"
    )
    # 安全化文件名，移除特殊字符
    from ..utils import sanitize_filename

    safe_unique_id = sanitize_filename(str(unique_id))
    output_path = os.path.join(plugin.tmp_dir, f"fishing_ranking_{safe_unique_id}.png")

    draw_fishing_ranking(user_data, output_path=output_path, ranking_type=ranking_type)
    yield event.image_result(output_path)


async def steal_fish(plugin: "FishingPlugin", event: AstrMessageEvent):
    """偷鱼功能"""
    user_id = plugin._get_effective_user_id(event)
    parts = event.message_str.strip().split()
    target_id, error_msg = parse_target_user_id(event, parts, 1)

    if error_msg or not target_id:
        yield event.plain_result(
            "❌ 请指定偷鱼的用户！\n用法：/偷鱼 @用户 或 /偷鱼 用户ID"
        )
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能偷自己的鱼哦！")
        return

    result = plugin.game_mechanics_service.steal_fish(user_id, target_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def electric_fish(plugin: "FishingPlugin", event: AstrMessageEvent):
    """电鱼功能"""
    # 检查电鱼功能是否启用
    electric_fish_config = plugin.game_config.get("electric_fish", {})
    if not electric_fish_config.get("enabled", True):
        yield event.plain_result("❌ 电鱼功能已被管理员禁用！")
        return

    user_id = plugin._get_effective_user_id(event)
    parts = event.message_str.strip().split()
    target_id, error_msg = parse_target_user_id(event, parts, 1)

    if error_msg or not target_id:
        yield event.plain_result(
            "❌ 请指定电鱼的用户！\n用法：/电鱼 @用户 或 /电鱼 用户ID"
        )
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能电自己的鱼哦！")
        return

    result = plugin.game_mechanics_service.electric_fish(user_id, target_id)
    if result:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def dispel_protection(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用驅靈香驅散目標的海靈守護 - 統一到使用指令"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split()
    target_id, error_msg = parse_target_user_id(event, args, 1)

    if error_msg:
        yield event.plain_result(error_msg)
        return
    if not target_id:
        yield event.plain_result("請在消息中@要驅散守護的用戶")
        return
    if str(target_id) == str(user_id):
        yield event.plain_result("不能對自己使用驅靈香哦！")
        return

    # 查找驅靈香道具
    all_items = plugin.item_template_repo.get_all_items()
    dispel_item = None
    for item in all_items:
        if item.effect_type == "STEAL_PROTECTION_REMOVAL":
            dispel_item = item
            break

    if not dispel_item:
        yield event.plain_result("❌ 系統錯誤：找不到驅靈香道具")
        return

    # 檢查用戶是否持有驅靈香
    item_inventory = plugin.inventory_repo.get_user_item_inventory(user_id)
    if item_inventory.get(dispel_item.item_id, 0) < 1:
        yield event.plain_result(f"❌ 你沒有【{dispel_item.name}】道具！")
        return

    # 使用統一的道具使用邏輯
    result = plugin.inventory_service.use_item(
        user_id, dispel_item.item_id, quantity=1, target_user_id=target_id
    )

    if result.get("success"):
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result(result["message"])


async def view_titles(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户称号"""
    user_id = plugin._get_effective_user_id(event)
    titles = plugin.user_service.get_user_titles(user_id).get("titles", [])
    if titles:
        try:
            from ..draw.list_cards import draw_text_list_image

            rows = []
            for title in titles:
                status = "(當前)" if title["is_current"] else ""
                rows.append(
                    f"{title['name']}  ID:{title['title_id']} {status}  |  {title['description']}"
                )
            image = draw_text_list_image(
                title="🏅 我的稱號",
                rows=rows,
                subtitle=f"共 {len(titles)} 個",
                footer="💡 /使用稱號 [ID]",
            )
            image_path = os.path.join(plugin.tmp_dir, "title_list.png")
            image.save(image_path)
            yield event.image_result(image_path)
            tip = build_tip_result(
                event,
                "⌨️ 建議下一步\n```\n/使用稱號 [ID]\n```",
                plugin=plugin,
                user_id=user_id,
            )
            if tip is not None:
                yield tip
            return
        except Exception:
            pass

        message = "【🏅 您的称号】\n"
        for title in titles:
            status = " (当前装备)" if title["is_current"] else ""
            message += f"- {title['name']} (ID: {title['title_id']}){status}\n- 描述: {title['description']}\n\n"
        message += "💡 称号是你的身份展示，不直接加战斗属性。\n"
        message += "💡 使用：/使用称号 [ID] 来切换当前展示称号。"
        yield event.plain_result(message)
    else:
        yield event.plain_result(
            "❌ 您还没有任何称号。\n"
            "💡 称号主要通过成就系统或管理员活动发放获得。\n"
            "先试试：/查看成就"
        )


async def use_title(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用称号"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要使用的称号 ID，例如：/使用称号 1")
        return
    title_id_str = args[1]
    if not title_id_str.isdigit():
        yield event.plain_result("❌ 称号 ID 必须是数字，请检查后重试。")
        return
    result = plugin.user_service.use_title(user_id, int(title_id_str))
    yield event.plain_result(result["message"])


async def view_achievements(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用戶成就"""
    from ..utils import safe_datetime_handler

    user_id = plugin._get_effective_user_id(event)
    ach_result = plugin.achievement_service.get_user_achievements(user_id)
    achievements = ach_result.get("achievements", [])

    if achievements:
        message = "【🏆 我的成就牆】\n"
        message += "════════════════════════════\n"

        def format_reward(reward):
            if not reward or not isinstance(reward, (tuple, list)) or len(reward) < 2:
                return "無"
            rtype, rval = reward[0], reward[1]
            rqty = reward[2] if len(reward) > 2 else 1

            names = {
                "coins": "金幣",
                "premium_currency": "高級貨幣",
                "title": "稱號",
                "bait": "魚餌",
                "rod": "魚竿",
                "accessory": "飾品",
                "item": "道具",
            }
            typename = names.get(rtype, rtype)

            if rtype == "title":
                title_template = plugin.item_template_repo.get_title_by_id(rval)
                val_name = title_template.name if title_template else f"ID:{rval}"
                return f"限定稱號「{val_name}」"
            elif rtype == "coins":
                return f"{rval * rqty} 金幣"
            elif rtype in ["bait", "rod", "accessory", "item"]:
                # 嘗試獲取名稱
                template = None
                if rtype == "bait":
                    template = plugin.item_template_repo.get_bait_by_id(rval)
                elif rtype == "rod":
                    template = plugin.item_template_repo.get_rod_by_id(rval)
                elif rtype == "accessory":
                    template = plugin.item_template_repo.get_accessory_by_id(rval)
                elif rtype == "item":
                    template = plugin.item_template_repo.get_by_id(rval)

                val_name = template.name if template else f"ID:{rval}"
                return f"{val_name} x{rqty}"

            return f"{typename} x{rqty}"

        # 按完成狀態排序：未完成的在前
        achievements.sort(key=lambda x: 1 if x.get("completed_at") else 0)

        for ach in achievements:
            comp_at = ach.get("completed_at")
            status_icon = "✅" if comp_at else "⏳"
            status_text = (
                f"已獲得 ({safe_datetime_handler(comp_at)})"
                if comp_at
                else f"進行中 ({ach['progress']}/{ach['target']})"
            )

            message += f"{status_icon} *{ach['name']}* (ID: {ach['id']})\n"
            message += f"   狀態：{status_text}\n"
            message += f"   描述：{ach['description']}\n"
            message += f"   獎勵：{format_reward(ach.get('reward'))}\n"
            message += "────────────────────────────\n"

        message += "💡 成就是你在釣魚世界的里程碑，完成後可解鎖各類限定獎勵！"

        # 訊息過長處理
        if len(message) > 4000:
            # 如果太長，只顯示已完成的統計和未完成的前幾個
            completed_count = sum(1 for a in achievements if a.get("completed_at"))
            message = (
                f"【🏆 我的成就牆】(已完成 {completed_count}/{len(achievements)})\n"
            )
            message += "════════════════════════════\n"
            # 優先顯示最近進展
            for ach in [a for a in achievements if not a.get("completed_at")][:10]:
                message += f"⏳ *{ach['name']}* ({ach['progress']}/{ach['target']})\n"
                message += f"   獎勵：{format_reward(ach.get('reward'))}\n"
            message += "...\n(成就過多，僅顯示部分進行中項目)\n"
            message += "────────────────────────────\n"

        try:
            from ..draw.list_cards import draw_text_list_image

            rows = []
            for ach in achievements:
                comp_at = ach.get("completed_at")
                if comp_at:
                    rows.append(
                        f"✅ {ach['name']}  |  {safe_datetime_handler(comp_at)}  |  獎勵: {format_reward(ach.get('reward'))}"
                    )
                else:
                    rows.append(
                        f"⏳ {ach['name']}  |  進度 {ach['progress']}/{ach['target']}  |  獎勵: {format_reward(ach.get('reward'))}"
                    )
            image = draw_text_list_image(
                title="🏆 我的成就牆",
                rows=rows,
                subtitle=f"已完成 {sum(1 for a in achievements if a.get('completed_at'))}/{len(achievements)}",
                footer="💡 /查看稱號   /使用稱號 [ID]",
            )
            image_path = os.path.join(plugin.tmp_dir, "achievement_list.png")
            image.save(image_path)
            yield event.image_result(image_path)
            tip = build_tip_result(
                event,
                "⌨️ 建議下一步\n```\n/查看稱號\n```\n```\n/使用稱號 [ID]\n```",
                plugin=plugin,
                user_id=user_id,
            )
            if tip is not None:
                yield tip
            return
        except Exception:
            pass

        yield event.plain_result(message)
        tip = build_tip_result(
            event,
            "⌨️ 建議下一步\n```\n/查看稱號\n```\n```\n/使用稱號 [ID]\n```",
            plugin=plugin,
            user_id=user_id,
        )
        if tip is not None:
            yield tip
    else:
        yield event.plain_result(
            "❌ 您目前沒有任何成就記錄。\n"
            "💡 建議從這些開始：/簽到、/釣魚、/全部賣出、/商店"
        )


async def tax_record(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看税收记录"""
    from ..utils import safe_datetime_handler

    user_id = plugin._get_effective_user_id(event)
    result = plugin.user_service.get_tax_record(user_id)
    if result and result["success"]:
        records = result.get("records", [])
        if not records:
            yield event.plain_result("📜 您还没有税收记录。")
            return
        message = "【📜 税收记录】\n\n"
        for record in records:
            message += f"⏱️ 时间: {safe_datetime_handler(record['timestamp'])}\n"
            message += f"💰 金额: {record['amount']} 金币\n"
            message += f"📊 描述: {record['tax_type']}\n\n"
        try:
            from ..draw.list_cards import draw_text_list_image

            rows = [
                f"{safe_datetime_handler(r['timestamp'])}  |  {r['tax_type']}  |  {r['amount']} 金幣"
                for r in records
            ]
            image = draw_text_list_image(
                title="📜 稅收記錄",
                rows=rows,
                subtitle=f"共 {len(records)} 筆",
                footer="💡 稅費會隨交易與玩法而變動",
            )
            image_path = os.path.join(plugin.tmp_dir, "tax_record_list.png")
            image.save(image_path)
            yield event.image_result(image_path)
            return
        except Exception:
            pass

        yield event.plain_result(message)
    else:
        yield event.plain_result(
            f"❌ 查看税收记录失败：{result.get('message', '未知错误')}"
        )
