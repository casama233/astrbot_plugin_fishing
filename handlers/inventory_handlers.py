import os
from astrbot.api.event import filter, AstrMessageEvent
from ..utils import (
    to_percentage,
    format_accessory_or_rod,
    format_rarity_display,
    parse_amount,
    parse_target_user_id,
    get_loading_tip,
    should_send_loading_tip,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


def _build_dynamic_shortcuts(
    plugin: "FishingPlugin", user_id: str, scene: str = "general"
) -> str:
    tips = []
    try:
        user = plugin.user_repo.get_by_id(user_id)

        # 检查用户是否关闭了建议消息
        if user and not user.show_suggestions:
            return ""

        # 检查全局配置
        show_suggestions = plugin.game_config.get("show_suggestions", True)
        if not show_suggestions:
            return ""

        coins = user.coins if user else 0

        state_data = plugin.user_service.get_user_state(user_id) or {}
        can_auto_fish = bool(state_data.get("user", {}).get("is_auto_fishing", False))

        bait_info = plugin.inventory_service.get_user_bait_inventory(user_id) or {}
        baits = bait_info.get("baits", []) or []
        has_bait = any(int(b.get("quantity", 0) or 0) > 0 for b in baits)

        item_info = plugin.inventory_service.get_user_item_inventory(user_id) or {}
        items = item_info.get("items", []) or []
        has_item = any(int(i.get("quantity", 0) or 0) > 0 for i in items)

        rod_info = plugin.inventory_service.get_user_rod_inventory(user_id) or {}
        rods = rod_info.get("rods", []) or []
        has_rod = len(rods) > 0

        acc_info = plugin.inventory_service.get_user_accessory_inventory(user_id) or {}
        accessories = acc_info.get("accessories", []) or []

        rod_count = {}
        for r in rods:
            rid = r.get("rod_id")
            if rid is not None:
                rod_count[rid] = rod_count.get(rid, 0) + 1
        acc_count = {}
        for a in accessories:
            aid = a.get("accessory_id")
            if aid is not None:
                acc_count[aid] = acc_count.get(aid, 0) + 1
        can_refine = any(v >= 2 for v in rod_count.values()) or any(
            v >= 2 for v in acc_count.values()
        )

        pond_data = plugin.inventory_service.get_user_fish_pond(user_id) or {}
        pond_stats = pond_data.get("stats", {}) if isinstance(pond_data, dict) else {}
        fish_count = int(pond_stats.get("total_count", 0) or 0)

        if not has_bait:
            tips.append("- 你目前没有鱼饵：/商店（先补基础鱼饵）")
        if not has_rod:
            tips.append("- 你目前没有鱼竿：/商店（先买入门鱼竿）")
        if coins < 200:
            tips.append("- 金币偏少：/签到、/全部卖出（先补流动资金）")
        if fish_count > 0:
            tips.append("- 鱼塘有库存：/出售稀有度 1 或 /全部卖出")
        if can_refine:
            tips.append("- 检测到可精炼装备：/精炼 R短码 或 /精炼 A短码")
        if has_item:
            tips.append("- 背包有可用道具：/使用 D短码")
        if can_auto_fish:
            tips.append("- 自动钓鱼已开启：/自动钓鱼（可随时关闭）")
        if fish_count >= 20:
            tips.append("- 鱼库存较多：/市场 上架 或 /保留卖出")

        scene_defaults = {
            "backpack": [
                "- /鱼竿 /饰品 /鱼饵 /道具：分类查看",
                "- /使用 [短码]：装备或使用",
                "- /开启全部钱袋：批量开袋",
                "- /钓鱼：继续推进资源循环",
            ],
            "pond": [
                "- /出售 [ID] 或 /全部卖出：变现",
                "- /放入水族箱 [ID]：收藏珍品",
                "- /钓鱼：继续积累",
            ],
            "rod": [
                "- /使用 R短码：装备鱼竿",
                "- /锁定 R短码：防止误出售",
                "- /钓鱼：实战验证当前搭配",
            ],
            "accessory": [
                "- /使用 A短码：装备饰品",
                "- /锁定 A短码：防止误出售",
                "- /钓鱼：实战验证当前搭配",
            ],
            "bait": [
                "- /使用 B短码：切换鱼饵",
                "- /钓鱼：消耗鱼饵并产出收益",
                "- /商店：补充鱼饵库存",
            ],
            "item": [
                "- /使用 D短码：使用道具",
                "- /开启全部钱袋：批量开袋",
                "- /背包：返回总览",
            ],
        }

        defaults = scene_defaults.get(scene, scene_defaults["backpack"])
        merged = tips + defaults
        merged = merged[:6]
        if scene == "backpack":
            moneybag_tip = "- /开启全部钱袋：批量开袋"
            if moneybag_tip not in merged:
                if len(merged) >= 6:
                    merged[-1] = moneybag_tip
                else:
                    merged.append(moneybag_tip)
        return (
            "⌨️ 智能快捷提示\n"
            + "\n".join(merged)
            + "\n💡 输入 /钓鱼帮助 速查 查看完整快捷表"
        )
    except Exception:
        return (
            "⌨️ 快捷操作\n"
            "- /商店：补给\n"
            "- /钓鱼：推进\n"
            "- /背包：查看道具\n"
            "- /开启全部钱袋（/打开所有钱袋）：批量开袋\n"
            "- /使用 [短码]：装备或使用"
        )


async def user_backpack(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户背包"""
    user_id = plugin._get_effective_user_id(event)
    user = plugin.user_repo.get_by_id(user_id)

    if not user:
        yield event.plain_result("❌ 找不到您的用户数据，请先使用 /注册 命令。")
        return

    try:
        # 导入绘制函数
        from ..draw.backpack import draw_backpack_image, get_user_backpack_data

        # 获取用户背包数据
        backpack_data = get_user_backpack_data(
            plugin.inventory_service, user_id, max_items_per_category=50
        )

        # 检查是否有称号，并将其添加到 backpack_data
        user_title_info = None
        if hasattr(user, "current_title_id") and user.current_title_id:
            title_template = plugin.item_template_repo.get_title_by_id(
                user.current_title_id
            )
            if title_template:
                user_title_info = {
                    "name": title_template.name,
                    "display_format": getattr(
                        title_template, "display_format", "{name}"
                    ),
                }
        backpack_data["user_title"] = user_title_info

        # 设置用户昵称
        backpack_data["nickname"] = user.nickname or user_id

        # 如果物品总数超过200，先给出警告提示
        total_items = (
            backpack_data.get("total_rods", 0)
            + backpack_data.get("total_accessories", 0)
            + backpack_data.get("total_baits", 0)
            + backpack_data.get("total_items", 0)
        )

        if total_items > 200:
            yield event.plain_result(
                f"⚠️ 检测到您的背包有 {total_items} 个物品！\\n"
                "💡 物品过多可能导致图片生成较慢或失败，建议先清理背包。\\n"
                "📝 您也可以使用「鱼竿」「饰品」「鱼饵」「道具」命令分类查看。\\n"
                "⏳ 正在生成背包图片，请稍候..."
            )

        # 生成背包图像
        image = draw_backpack_image(backpack_data, plugin.data_dir)
        # 保存图像到临时文件
        image_path = os.path.join(plugin.tmp_dir, f"user_backpack_{user_id}.png")
        image.save(image_path)
        yield event.image_result(image_path)

        shortcuts = _build_dynamic_shortcuts(plugin, user_id, "backpack")
        if shortcuts:
            yield event.plain_result(shortcuts)

        # 如果内容被截断或过滤，额外发送提示
        if backpack_data.get("is_truncated", False):
            filter_info = []
            if backpack_data.get("rods_filtered", False):
                filter_info.append(
                    f"鱼竿：仅显示5星以上 ({backpack_data['displayed_rods']}/{backpack_data['total_rods']})"
                )
            if backpack_data.get("accessories_filtered", False):
                filter_info.append(
                    f"饰品：仅显示5星以上 ({backpack_data['displayed_accessories']}/{backpack_data['total_accessories']})"
                )
            if filter_info:
                yield event.plain_result(
                    "💡 为保持图片清晰，部分低星物品已折叠显示。\n"
                    "📝 使用分类命令查看完整列表：/鱼竿 /饰品"
                )

    except Exception as e:
        from astrbot.api import logger

        logger.error(f"生成背包图片失败: {e}", exc_info=True)
        yield event.plain_result(
            "❌ 生成背包图片失败。\\n"
            "💡 可能的原因是物品过多，请尝试使用 `/鱼竿` `/饰品` 等命令分类查看。"
        )


async def pond(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户鱼塘内的鱼"""
    user_id = plugin._get_effective_user_id(event)
    user = plugin.user_repo.get_by_id(user_id)

    if pond_fish := plugin.inventory_service.get_user_fish_pond(user_id):
        fishes = pond_fish["fishes"]
        stats = pond_fish["stats"]

        try:
            from ..draw.pond import draw_pond_image
            import os

            user_data = {
                "nickname": user.nickname if user else user_id,
                "current_title": None,
            }

            if user and hasattr(user, "current_title_id") and user.current_title_id:
                try:
                    title_info = plugin.item_template_repo.get_title_by_id(
                        user.current_title_id
                    )
                    if title_info:
                        user_data["current_title"] = {
                            "name": title_info.name,
                            "display_format": getattr(
                                title_info, "display_format", "{name}"
                            ),
                        }
                except Exception:
                    pass

            capacity_info = plugin.inventory_service.get_user_fish_pond_capacity(
                user_id
            )

            image = draw_pond_image(user_data, fishes, stats, capacity_info)
            image_path = os.path.join(plugin.tmp_dir, f"pond_{user_id}.png")
            image.save(image_path)

            yield event.image_result(image_path)

            shortcuts = _build_dynamic_shortcuts(plugin, user_id, "pond")
            if shortcuts:
                yield event.plain_result(shortcuts)

        except Exception as e:
            from astrbot.api import logger

            logger.error(f"生成鱼塘图片时发生错误: {e}", exc_info=True)

            fallback_message = "【🐠 魚塘】\n"
            fished_by_rarity = {}
            for fish in fishes:
                rarity = fish.get("rarity", "未知")
                if rarity not in fished_by_rarity:
                    fished_by_rarity[rarity] = []
                fished_by_rarity[rarity].append(fish)

            for rarity in sorted(fished_by_rarity.keys(), reverse=True):
                fish_list = fished_by_rarity[rarity]
                if fish_list:
                    fallback_message += f"\n {format_rarity_display(rarity)}：\n"
                    for fish in fish_list:
                        fish_id = int(fish.get("fish_id", 0) or 0)
                        quality_level = fish.get("quality_level", 0)
                        if quality_level == 1:
                            fcode = f"F{fish_id}H" if fish_id else "F0H"
                        else:
                            fcode = f"F{fish_id}" if fish_id else "F0"
                        quality_display = " ✨高品質" if quality_level == 1 else ""
                        fallback_message += f" - {fish['name']}{quality_display} x {fish['quantity']} （{fish['actual_value']}金幣 / 個） ID: {fcode}\n"

            fallback_message += f"\n🐟 總魚數：{stats['total_count']} 條\n"
            fallback_message += f"💰 總價值：{stats['total_value']} 金幣\n"
            yield event.plain_result(fallback_message)
    else:
        yield event.plain_result("🐟 您的鱼塘是空的，快去钓鱼吧！")


async def peek_pond(plugin: "FishingPlugin", event: AstrMessageEvent):
    """偷看他人鱼塘内的鱼"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.strip().split()
    target_user_id, error_msg = parse_target_user_id(event, args, 1)

    if error_msg or not target_user_id:
        yield event.plain_result(
            "❌ 请指定要查看的用户！\n用法：/偷看鱼塘 @用户 或 /偷看鱼塘 用户ID"
        )
        return

    # 检查目标用户是否存在
    target_user = plugin.user_repo.get_by_id(target_user_id)
    if not target_user:
        yield event.plain_result(f"❌ 用户 {target_user_id} 不存在！")
        return

    # 获取目标用户的鱼塘信息
    if pond_fish := plugin.inventory_service.get_user_fish_pond(target_user_id):
        fishes = pond_fish["fishes"]
        # 把fishes按稀有度分组
        fished_by_rarity = {}
        for fish in fishes:
            rarity = fish.get("rarity", "未知")
            if rarity not in fished_by_rarity:
                fished_by_rarity[rarity] = []
            fished_by_rarity[rarity].append(fish)

        # 构造输出信息
        message = f"【🔍 偷看 {target_user.nickname} 的鱼塘】：\n"

        for rarity in sorted(fished_by_rarity.keys(), reverse=True):
            fish_list = fished_by_rarity[rarity]
            if fish_list:
                message += f"\n {format_rarity_display(rarity)} 稀有度 {rarity}：\n"
                for fish in fish_list:
                    fish_id = int(fish.get("fish_id", 0) or 0)
                    quality_level = fish.get("quality_level", 0)
                    # 生成带品质标识的FID
                    if quality_level == 1:
                        fcode = f"F{fish_id}H" if fish_id else "F0H"  # H代表✨高品质
                    else:
                        fcode = f"F{fish_id}" if fish_id else "F0"  # 普通品质
                    # 显示品质信息
                    quality_display = ""
                    if quality_level == 1:
                        quality_display = " ✨高品质"
                    actual_value = fish.get("actual_value", fish.get("base_value", 0))
                    message += f"  - {fish['name']}{quality_display} x  {fish['quantity']} （{actual_value}金币 / 个） ID: {fcode}\n"
        message += f"\n🐟 总鱼数：{pond_fish['stats']['total_count']} 条\n"
        message += f"💰 总价值：{pond_fish['stats']['total_value']} 金币\n"
        yield event.plain_result(message)
    else:
        yield event.plain_result(f"🐟 {target_user.nickname} 的鱼塘是空的！")


async def pond_capacity(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户鱼塘容量"""
    user_id = plugin._get_effective_user_id(event)
    pond_capacity = plugin.inventory_service.get_user_fish_pond_capacity(user_id)
    if pond_capacity["success"]:
        message = f"🐠 您的鱼塘容量为 {pond_capacity['current_fish_count']} / {pond_capacity['fish_pond_capacity']} 条鱼。"
        yield event.plain_result(message)
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def upgrade_pond(plugin: "FishingPlugin", event: AstrMessageEvent):
    """升级鱼塘容量"""
    user_id = plugin._get_effective_user_id(event)
    result = plugin.inventory_service.upgrade_fish_pond(user_id)
    if result["success"]:
        yield event.plain_result(
            f"🐠 鱼塘升级成功！新容量为 {result['new_capacity']} 条鱼。"
        )
    else:
        yield event.plain_result(f"❌ 升级失败：{result['message']}")


async def rod(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户鱼竿信息"""
    user_id = plugin._get_effective_user_id(event)
    rod_info = plugin.inventory_service.get_user_rod_inventory(user_id)
    if rod_info and rod_info["rods"]:
        all_rods = rod_info["rods"]
        total_count = len(all_rods)

        # 智能过滤：鱼竿过多时只显示5星以上
        rods = all_rods
        is_filtered = False

        if total_count > 30:
            high_rarity_rods = [r for r in all_rods if r.get("rarity", 1) >= 5]
            if len(high_rarity_rods) > 0:
                # 即使5星以上也限制最多100项
                rods = high_rarity_rods[:100]
                is_filtered = True
            else:
                # 如果没有5星以上，按稀有度排序取前50个
                rods = sorted(all_rods, key=lambda x: x.get("rarity", 1), reverse=True)[
                    :50
                ]
                is_filtered = True

        displayed_count = len(rods)

        # 构造输出信息,附带emoji
        if is_filtered:
            message = f"【🎣 鱼竿】共 {total_count} 根，仅显示高品质鱼竿 {displayed_count} 根：\n"
            message += "💡 提示：数量过多，仅显示5星以上鱼竿\n\n"
        else:
            message = f"【🎣 鱼竿】共 {total_count} 根：\n"

        for rod in rods:
            message += format_accessory_or_rod(rod)
            if (
                rod.get("bonus_rare_fish_chance", 1) != 1
                and rod.get("bonus_fish_weight", 1.0) != 1.0
            ):
                message += f"   - 钓上鱼鱼类几率加成: {to_percentage(rod['bonus_rare_fish_chance'])}\n"
            message += f"   -精炼等级: {rod.get('refine_level', 1)}\n"

        # 检查消息长度，如果太长则截断
        if len(message) > 3000:
            message = message[:3000] + "\n\n📝 消息过长已截断。"

        # 如果被过滤，添加清理建议
        if is_filtered:
            message += "\n\n🧹 建议及时清理低品质鱼竿：\n"
            message += "• /出售所有鱼竿 - 快速清理低品质鱼竿\n"
            message += "• /出售 [鱼竿ID] - 出售指定鱼竿"

        message += "\n\n" + _build_dynamic_shortcuts(plugin, user_id, "rod")

        yield event.plain_result(message)
    else:
        yield event.plain_result("🎣 您还没有鱼竿，快去商店购买或抽奖获得吧！")


async def bait(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户鱼饵信息"""
    user_id = plugin._get_effective_user_id(event)
    bait_info = plugin.inventory_service.get_user_bait_inventory(user_id)
    if bait_info and bait_info["baits"]:
        # 构造输出信息,附带emoji
        message = "【🐟 鱼饵】：\n"

        for bait in bait_info["baits"]:
            bait_id = int(bait.get("bait_id", 0) or 0)
            bcode = f"B{bait_id}" if bait_id else "B0"
            message += f" - {bait['name']} x {bait['quantity']} (稀有度: {format_rarity_display(bait['rarity'])}) ID: {bcode}\n"
            if bait["duration_minutes"] > 0:
                message += f"   - 持续时间: {bait['duration_minutes']} 分钟\n"
            if bait["effect_description"]:
                message += f"   - 效果: {bait['effect_description']}\n"
            message += "\n"
        message += _build_dynamic_shortcuts(plugin, user_id, "bait")
        yield event.plain_result(message)
    else:
        yield event.plain_result("🐟 您还没有鱼饵，快去商店购买或抽奖获得吧！")


async def items(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户道具信息（文本版）"""
    user_id = plugin._get_effective_user_id(event)
    item_info = plugin.inventory_service.get_user_item_inventory(user_id)
    if item_info and item_info.get("items"):
        message = "【📦 道具】：\n"
        for it in item_info["items"]:
            item_id = int(it.get("item_id", 0) or 0)
            dcode = f"D{item_id}" if item_id else "D0"
            consumable_text = "消耗品" if it.get("is_consumable") else "非消耗"
            message += f" - {it['name']} x {it['quantity']} (稀有度: {format_rarity_display(it['rarity'])}，{consumable_text}) ID: {dcode}\n"
            if it.get("effect_description"):
                message += f"   - 效果: {it['effect_description']}\n"
            message += "\n"
        message += _build_dynamic_shortcuts(plugin, user_id, "item")
        yield event.plain_result(message)
    else:
        yield event.plain_result("📦 您还没有道具。")


async def use_item(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用一个或多个道具"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定要使用的道具 ID，例如：/使用道具 1\n💡 支持中文数字，如：/使用道具 1 五"
        )
        return

    item_id_str = args[1]
    if not item_id_str.isdigit():
        yield event.plain_result("❌ 道具 ID 必须是数字。")
        return

    item_id = int(item_id_str)

    quantity = 1
    if len(args) > 2:
        try:
            quantity = parse_amount(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数。")
                return
        except Exception as e:
            yield event.plain_result(
                f"❌ 无法解析数量：{str(e)}。示例：1 或 五 或 一千"
            )
            return

    result = plugin.inventory_service.use_item(user_id, item_id, quantity)

    if result and result.get("success"):
        yield event.plain_result(f"✅ {result['message']}")
    else:
        error_message = result.get("message", "未知错误") if result else "未知错误"
        yield event.plain_result(f"❌ 使用道具失败：{error_message}")


async def open_all_money_bags(plugin: "FishingPlugin", event: AstrMessageEvent):
    """开启全部钱袋：/开启全部钱袋"""
    user_id = plugin._get_effective_user_id(event)

    result = plugin.inventory_service.open_all_money_bags(user_id)

    if result and result.get("success"):
        yield event.plain_result(f"✅ {result['message']}")
    else:
        error_message = result.get("message", "未知错误") if result else "未知错误"
        yield event.plain_result(f"❌ 开启钱袋失败：{error_message}")


async def accessories(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户饰品信息"""
    user_id = plugin._get_effective_user_id(event)
    accessories_info = plugin.inventory_service.get_user_accessory_inventory(user_id)
    if accessories_info and accessories_info["accessories"]:
        all_accessories = accessories_info["accessories"]
        total_count = len(all_accessories)

        # 智能过滤：饰品过多时只显示5星以上
        accessories = all_accessories
        is_filtered = False

        if total_count > 30:
            high_rarity_accessories = [
                a for a in all_accessories if a.get("rarity", 1) >= 5
            ]
            if len(high_rarity_accessories) > 0:
                # 即使5星以上也限制最多100项
                accessories = high_rarity_accessories[:100]
                is_filtered = True
            else:
                # 如果没有5星以上，按稀有度排序取前50个
                accessories = sorted(
                    all_accessories, key=lambda x: x.get("rarity", 1), reverse=True
                )[:50]
                is_filtered = True

        displayed_count = len(accessories)

        # 构造输出信息,附带emoji
        if is_filtered:
            message = f"【💍 饰品】共 {total_count} 个，仅显示高品质饰品 {displayed_count} 个：\n"
            message += "💡 提示：数量过多，仅显示5星以上饰品\n\n"
        else:
            message = f"【💍 饰品】共 {total_count} 个：\n"

        for accessory in accessories:
            message += format_accessory_or_rod(accessory)
            message += f"   -精炼等级: {accessory.get('refine_level', 1)}\n"

        # 检查消息长度，如果太长则截断
        if len(message) > 3000:
            message = message[:3000] + "\n\n📝 消息过长已截断。"

        # 如果被过滤，添加清理建议
        if is_filtered:
            message += "\n\n🧹 建议及时清理低品质饰品：\n"
            message += "• /出售所有饰品 - 快速清理低品质饰品\n"
            message += "• /出售 [饰品ID] - 出售指定饰品"

        message += "\n\n" + _build_dynamic_shortcuts(plugin, user_id, "accessory")

        yield event.plain_result(message)
    else:
        yield event.plain_result("💍 您还没有饰品，快去商店购买或抽奖获得吧！")


async def refine_help(plugin: "FishingPlugin", event: AstrMessageEvent):
    """精炼系统帮助（当前版本）"""
    help_message = """🔨 精炼系统指南（当前版本）

═══════════════════════════════════
📖 核心规则
═══════════════════════════════════

• 精炼对象：鱼竿、饰品（同模板之间精炼）
• 等级范围：1级 → 10级（目前的满级）
• 消耗条件：同模板材料 + 金币
• 每次只升1级：精N → 精N+1
• 材料选择：优先使用"未装备、精炼等级最低"的同模板实例；永不使用正在装备的作为材料

成功：
• 目标等级+1，消耗1件材料与对应金币

失败（三种）：
• 普通失败：装备本体不变，但会消耗1件材料与对应金币
• 降级失败：装备等级-1，消耗1件材料与对应金币（10%概率）
• 毁坏失败（高等级概率触发）：消耗1件材料与对应金币，并摧毁本体装备

═══════════════════════════════════
✨ 稀有度与费用/成功率
═══════════════════════════════════

🎲 成功率（关键档位）：
• 1-4星：前期成功率高，后期逐步下降（更易满精）
• 5星：6→10级约为 50%、40%、35%、30%、25%
• 6星：6→10级约为 45%、35%、30%、25%、20%
• 7星及以上：挑战性高，6→10级约为 60%、50%、40%、30%、20%

提示：成功率按"目标新等级"计算（例如精2→精3，用精3的成功率）。

═══════════════════════════════════
⚡ 属性成长与加成
═══════════════════════════════════

• 1-3星：≈+15%/级
• 4星：≈+12%/级
• 5星：≈+8%/级
• 6星：≈+5%/级
• 7星+：≈+3%/级

═══════════════════════════════════
💰 精炼收益（系统回收价）
═══════════════════════════════════

• 售价 = 基础价(按稀有度) × 精炼等级乘数
• 基础价（示例）：1★=100，2★=500，3★=2000，4★=5000，5★=10000
• 精炼乘数（示例）：1→10级：1.0, 1.6, 3.0, 6.0, 12.0, 25.0, 55.0, 125.0, 280.0, 660.0
• 设计目标：收益随等级近指数增长，高精炼装备可覆盖成本并获得显著利润
• 出售所有会逐件按该规则计价，跳过正在装备的物品
• 玩家市场价格由卖家自定，不受该公式限制

═══════════════════════════════════
🏆 耐久度（仅鱼竿）
═══════════════════════════════════

• 每次钓鱼：鱼竿耐久 -1，降至0自动卸下
• 精炼成功：耐久恢复至当前最大值
• 每升1级：最大耐久度 ×1.5（累计）
• 神器奖励：5星及以上鱼竿精炼到10级 → 获得"无限耐久"（∞）
• 饰品无耐久度，不受上述规则影响

═══════════════════════════════════
📉 失败类型与概率
═══════════════════════════════════

🎲 降级概率（固定）：
• 所有等级：10%概率降级

💥 毁坏概率（5级及以上）：
• 1-2星：30%概率毁坏
• 3-4星：35%概率毁坏
• 5-6星：40%概率毁坏
• 7星+：50%概率毁坏

💔 普通失败：剩余概率（装备保持不变）

═══════════════════════════════════
📝 命令用法
═══════════════════════════════════

• /精炼鱼竿 [鱼竿ID]
• /精炼饰品 [饰品ID]
• 需要至少两件同模板装备（目标 + 材料）
• 查看背包以确认实例ID：/背包、/鱼竿、/饰品

"""

    yield event.plain_result(help_message)


async def use_equipment(
    plugin: "FishingPlugin", event: AstrMessageEvent, equipment_type: str = None
):
    """统一使用命令 - 根据短码前缀自动判断类型"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定要使用的物品ID，例如：/使用 R1A2B（鱼竿）、/使用 A3C4D（饰品）、/使用 D1（道具）、/使用 B2（鱼饵）\n💡 道具支持数量参数：/使用 D1 10（使用10个道具）"
        )
        return

    token = args[1].strip().upper()

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result(
            "❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n• D开头：道具（如 D1）\n• B开头：鱼饵（如 B2）\n\n💡 提示：使用 /背包 查看您的物品短码"
        )
        return

    # 根据前缀自动判断物品类型
    if token.startswith("R"):
        target_type = "rod"
        type_name = "鱼竿"
    elif token.startswith("A"):
        target_type = "accessory"
        type_name = "饰品"
    elif token.startswith("D"):
        target_type = "item"
        type_name = "道具"
    elif token.startswith("B"):
        target_type = "bait"
        type_name = "鱼饵"
    else:
        # 如果没有前缀，使用传入的类型参数
        if equipment_type:
            target_type = equipment_type
            type_name = "鱼竿" if equipment_type == "rod" else "饰品"
        else:
            yield event.plain_result(
                "❌ 请使用正确的物品ID：R开头为鱼竿，A开头为饰品，D开头为道具，B开头为鱼饵"
            )
            return

    # 处理不同类型的物品
    if target_type in ["rod", "accessory"]:
        # 装备类物品
        equipment_info = (
            plugin.inventory_service.get_user_rod_inventory(user_id)
            if target_type == "rod"
            else plugin.inventory_service.get_user_accessory_inventory(user_id)
        )

        if not equipment_info or not equipment_info.get(
            "rods" if target_type == "rod" else "accessories"
        ):
            yield event.plain_result(f"❌ 您还没有{type_name}，请先购买或抽奖获得。")
            return

        # 解析实例ID
        if target_type == "rod":
            instance_id = plugin.inventory_service.resolve_rod_instance_id(
                user_id, token
            )
        else:
            instance_id = plugin.inventory_service.resolve_accessory_instance_id(
                user_id, token
            )

        if instance_id is None:
            yield event.plain_result(f"❌ 无效的{type_name}ID，请检查后重试。")
            return

        # 装备物品
        if result := plugin.inventory_service.equip_item(
            user_id, int(instance_id), target_type
        ):
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用{type_name}失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    elif target_type == "item":
        # 道具类物品（简单数字ID）
        try:
            item_id = int(token[1:])
        except Exception:
            yield event.plain_result("❌ 无效的道具ID，请检查后重试。")
            return

        # 处理数量参数
        quantity = 1
        if len(args) > 2 and args[2].isdigit():
            quantity = int(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数。")
                return

        # 解析目标用户（用于驱灵类道具）
        target_user_id = None
        if len(args) > 2:
            parsed_target_id, _ = parse_target_user_id(event, args, 2, allow_self=False)
            if parsed_target_id:
                target_user_id = parsed_target_id

        # 使用道具
        if result := plugin.inventory_service.use_item(
            user_id, int(item_id), quantity, target_user_id=target_user_id
        ):
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用道具失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    elif target_type == "bait":
        # 鱼饵类物品（简单数字ID）
        try:
            bait_id = int(token[1:])
        except Exception:
            yield event.plain_result("❌ 无效的鱼饵ID，请检查后重试。")
            return

        # 使用鱼饵
        if result := plugin.inventory_service.use_bait(user_id, int(bait_id)):
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用鱼饵失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")


async def use_bait(plugin: "FishingPlugin", event: AstrMessageEvent):
    """使用鱼饵"""
    user_id = plugin._get_effective_user_id(event)
    bait_info = plugin.inventory_service.get_user_bait_inventory(user_id)
    if not bait_info or not bait_info["baits"]:
        yield event.plain_result("❌ 您还没有鱼饵，请先购买或抽奖获得。")
        return
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result("❌ 请指定要使用的鱼饵 ID，例如：/使用鱼饵 13")
        return
    bait_instance_id = args[1]
    if not bait_instance_id.isdigit():
        yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
        return
    if result := plugin.inventory_service.use_bait(user_id, int(bait_instance_id)):
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 使用鱼饵失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def refine_equipment(
    plugin: "FishingPlugin", event: AstrMessageEvent, equipment_type: str = None
):
    """统一精炼装备命令 - 根据短码前缀自动判断类型"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        # 如果没有参数，返回精炼帮助
        async for r in refine_help(plugin, event):
            yield r
        return

    token = args[1].strip().upper()

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result(
            "❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n\n💡 提示：使用 /背包 查看您的物品短码"
        )
        return

    # 根据前缀自动判断装备类型
    if token.startswith("R"):
        target_type = "rod"
        type_name = "鱼竿"
    elif token.startswith("A"):
        target_type = "accessory"
        type_name = "饰品"
    else:
        # 如果没有前缀，使用传入的类型参数
        if equipment_type:
            target_type = equipment_type
            type_name = "鱼竿" if equipment_type == "rod" else "饰品"
        else:
            yield event.plain_result("❌ 请使用正确的装备ID：R开头为鱼竿，A开头为饰品")
            return

    # 解析实例ID
    if target_type == "rod":
        instance_id = plugin.inventory_service.resolve_rod_instance_id(user_id, token)
    else:
        instance_id = plugin.inventory_service.resolve_accessory_instance_id(
            user_id, token
        )

    if instance_id is None:
        yield event.plain_result(f"❌ 无效的{type_name}ID，请检查后重试。")
        return

    # 精炼物品
    if result := plugin.inventory_service.refine(
        user_id, int(instance_id), target_type
    ):
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 精炼失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def sell_equipment(
    plugin: "FishingPlugin", event: AstrMessageEvent, equipment_type: str = None
):
    """统一出售物品命令 - 根据短码前缀自动判断类型"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定要出售的物品ID，例如：/出售 R1A2B（鱼竿）、/出售 A3C4D（饰品）、/出售 D1（道具）\n💡 道具支持数量参数：/出售 D1 10（出售10个道具）或 /出售 D1 一千（支持中文数字）"
        )
        return

    token = args[1].strip().upper()

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result(
            "❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n• D开头：道具（如 D1）\n\n💡 提示：使用 /背包 查看您的物品短码"
        )
        return

    # 根据前缀自动判断物品类型
    if token.startswith("R"):
        target_type = "rod"
        type_name = "鱼竿"
    elif token.startswith("A"):
        target_type = "accessory"
        type_name = "饰品"
    elif token.startswith("D"):
        target_type = "item"
        type_name = "道具"
    else:
        # 如果没有前缀，使用传入的类型参数
        if equipment_type:
            target_type = equipment_type
            type_name = "鱼竿" if equipment_type == "rod" else "饰品"
        else:
            yield event.plain_result(
                "❌ 请使用正确的物品ID：R开头为鱼竿，A开头为饰品，D开头为道具"
            )
            return

    # 处理道具的特殊情况（需要解析数量参数）
    if target_type == "item":
        # 解析道具ID
        try:
            item_id = int(token[1:])
        except ValueError:
            yield event.plain_result("❌ 无效的道具ID，请检查后重试。")
            return

        # 解析数量参数
        quantity = 1
        if len(args) >= 3:
            try:
                quantity = parse_amount(args[2])
                if quantity <= 0:
                    yield event.plain_result("❌ 数量必须是正整数")
                    return
            except Exception as e:
                yield event.plain_result(
                    f"❌ 无法解析数量：{str(e)}。示例：1 或 五 或 一千"
                )
                return

        # 出售道具
        item_tpl = plugin.item_template_repo.get_item_by_id(item_id)
        if item_tpl and (
            getattr(item_tpl, "effect_type", None) == "ADD_COINS"
            or "钱袋" in getattr(item_tpl, "name", "")
        ):
            yield event.plain_result(
                "❌ 钱袋类道具不走出售流程。\n"
                "请使用：/开启全部钱袋\n"
                "📌 说明：钱袋的主要用途是开启获得金币。"
            )
            return

        if result := plugin.inventory_service.sell_item(user_id, item_id, quantity):
            if result["success"]:
                yield event.plain_result(result["message"])
                if should_send_loading_tip(plugin.game_config):
                    yield event.plain_result(get_loading_tip("inventory"))
            else:
                yield event.plain_result(f"❌ 出售失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")
        return

    # 处理装备（鱼竿和饰品）
    # 解析实例ID
    if target_type == "rod":
        instance_id = plugin.inventory_service.resolve_rod_instance_id(user_id, token)
    else:
        instance_id = plugin.inventory_service.resolve_accessory_instance_id(
            user_id, token
        )

    if instance_id is None:
        yield event.plain_result(f"❌ 无效的{type_name}ID，请检查后重试。")
        return

    # 出售物品
    if result := plugin.inventory_service.sell_equipment(
        user_id, int(instance_id), target_type
    ):
        if result["success"]:
            yield event.plain_result(result["message"])
            if should_send_loading_tip(plugin.game_config):
                yield event.plain_result(get_loading_tip("inventory"))
        else:
            yield event.plain_result(f"❌ 出售失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def lock_equipment(
    plugin: "FishingPlugin", event: AstrMessageEvent, equipment_type: str = None
):
    """统一锁定装备命令 - 根据短码前缀自动判断类型"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定要锁定的装备ID，例如：/锁定 R1A2B 或 /锁定 A3C4D"
        )
        return

    token = args[1].strip().upper()

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result(
            "❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n\n💡 提示：使用 /背包 查看您的物品短码"
        )
        return

    # 根据前缀自动判断装备类型
    if token.startswith("R"):
        target_type = "rod"
        type_name = "鱼竿"
    elif token.startswith("A"):
        target_type = "accessory"
        type_name = "饰品"
    else:
        # 如果没有前缀，使用传入的类型参数
        if equipment_type:
            target_type = equipment_type
            type_name = "鱼竿" if equipment_type == "rod" else "饰品"
        else:
            yield event.plain_result("❌ 请使用正确的装备ID：R开头为鱼竿，A开头为饰品")
            return

    # 解析实例ID
    if target_type == "rod":
        instance_id = plugin.inventory_service.resolve_rod_instance_id(user_id, token)
    else:
        instance_id = plugin.inventory_service.resolve_accessory_instance_id(
            user_id, token
        )

    if instance_id is None:
        yield event.plain_result(f"❌ 无效的{type_name}ID，请检查后重试。")
        return

    # 锁定物品
    if target_type == "rod":
        result = plugin.inventory_service.lock_rod(user_id, int(instance_id))
    else:
        result = plugin.inventory_service.lock_accessory(user_id, int(instance_id))

    if result["success"]:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result(f"❌ 锁定失败：{result['message']}")


async def unlock_equipment(
    plugin: "FishingPlugin", event: AstrMessageEvent, equipment_type: str = None
):
    """统一解锁装备命令 - 根据短码前缀自动判断类型"""
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请指定要解锁的装备ID，例如：/解锁 R1A2B 或 /解锁 A3C4D"
        )
        return

    token = args[1].strip().upper()

    # 检查是否为数字ID（旧格式）
    if token.isdigit():
        yield event.plain_result(
            "❌ 请使用正确的物品ID！\n\n📝 短码格式：\n• R开头：鱼竿（如 R2N9C）\n• A开头：饰品（如 A7K3Q）\n\n💡 提示：使用 /背包 查看您的物品短码"
        )
        return

    # 根据前缀自动判断装备类型
    if token.startswith("R"):
        target_type = "rod"
        type_name = "鱼竿"
    elif token.startswith("A"):
        target_type = "accessory"
        type_name = "饰品"
    else:
        # 如果没有前缀，使用传入的类型参数
        if equipment_type:
            target_type = equipment_type
            type_name = "鱼竿" if equipment_type == "rod" else "饰品"
        else:
            yield event.plain_result("❌ 请使用正确的装备ID：R开头为鱼竿，A开头为饰品")
            return

    # 解析实例ID
    if target_type == "rod":
        instance_id = plugin.inventory_service.resolve_rod_instance_id(user_id, token)
    else:
        instance_id = plugin.inventory_service.resolve_accessory_instance_id(
            user_id, token
        )

    if instance_id is None:
        yield event.plain_result(f"❌ 无效的{type_name}ID，请检查后重试。")
        return

    # 解锁物品
    if target_type == "rod":
        result = plugin.inventory_service.unlock_rod(user_id, int(instance_id))
    else:
        result = plugin.inventory_service.unlock_accessory(user_id, int(instance_id))

    if result["success"]:
        yield event.plain_result(result["message"])
    else:
        yield event.plain_result(f"❌ 解锁失败：{result['message']}")


async def coins(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户金币信息"""
    user_id = plugin._get_effective_user_id(event)
    if user := plugin.user_repo.get_by_id(user_id):
        yield event.plain_result(f"💰 您的金币余额：{user.coins} 金币")
    else:
        yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")


async def premium(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看用户高级货币信息"""
    user_id = plugin._get_effective_user_id(event)
    if user := plugin.user_repo.get_by_id(user_id):
        yield event.plain_result(f"💎 您的高级货币余额：{user.premium_currency}")
    else:
        yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
