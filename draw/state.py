"""
狀態面板 - 遊戲風格美化版
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw

from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
    get_rarity_color,
)
from .styles import load_font
from .text_utils import normalize_display_text
from ..core.utils import calculate_after_refine

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def format_rarity_display(rarity: int) -> str:
    """格式化稀有度顯示"""
    if rarity <= 10:
        return "★" * rarity
    else:
        return "★★★★★★★★★★+"


def format_time(seconds: int) -> str:
    """格式化時間"""
    if seconds <= 0:
        return "可立即使用"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}小時{minutes}分鐘"
    return f"{minutes}分鐘"


def _draw_equipment_bonuses(
    draw: ImageDraw.ImageDraw,
    origin: tuple[int, int],
    source: Dict[str, Any],
    font,
) -> None:
    x, y = origin
    lines = []

    def _add_line(label: str, value: float) -> None:
        if value is None:
            return
        if value == 1 or value == 1.0:
            return
        if value == 0:
            return
        if value < 1:
            pct = int(round(value * 100))
            lines.append(f"{label}-{pct}%")
            return
        pct = int(round((value - 1) * 100))
        lines.append(f"{label}+{pct}%")

    _add_line("重量", source.get("weight_modifier"))
    _add_line("品質", source.get("bonus_fish_quality_modifier"))
    _add_line("數量", source.get("bonus_fish_quantity_modifier"))
    _add_line("稀有", source.get("bonus_rare_fish_chance"))
    _add_line("金幣", source.get("bonus_coin_modifier"))

    if not lines:
        return

    for line in lines[:2]:
        draw.text(
            (x, y),
            line,
            font=font,
            fill=GAME_COLORS["text_muted"],
        )
        y += 14


def draw_state_image(
    user_data: Dict[str, Any], data_dir: str, avatar_url: Optional[str] = None
) -> Image.Image:
    """用戶狀態面板 - 遊戲風格"""
    width = 700
    header_h = 100
    section_gap = 15
    footer_h = 50

    y = header_h + 15
    y += 105  # 基本資訊卡片
    y += 35  # 當前裝備標題
    y += 205  # 裝備卡片
    y += 35  # 功能狀態標題
    y += 145  # 狀態卡片
    calculated_height = y + footer_h + 60
    height = calculated_height + SAFETY_MARGIN

    # 創建遊戲風格背景
    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    # 字體
    title_font = load_font(32)
    section_font = load_font(24)
    content_font = load_font(18)
    small_font = load_font(15)
    tiny_font = load_font(13)

    # 標題欄
    nickname = user_data.get("nickname", "未知用戶")
    current_title = user_data.get("current_title")

    # 格式化用戶顯示名稱（包含稱號）
    from ..core.utils import format_user_display_name

    display_name = format_user_display_name(nickname, current_title)

    draw_game_title_bar(
        draw, width, 0, header_h, f"{display_name} 的狀態", title_font, "👤"
    )

    y = header_h + 15

    # 1. 基本資訊卡片
    draw_game_card(
        draw,
        (20, y, width - 20, y + 90),
        radius=12,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
        shadow=True,
    )

    # 金幣
    coins = user_data.get("coins", 0)
    draw.text(
        (35, y + 12), "💰 金幣", font=small_font, fill=GAME_COLORS["text_secondary"]
    )
    draw.text(
        (35, y + 35), f"{coins:,}", font=section_font, fill=GAME_COLORS["accent_gold"]
    )

    # 釣魚次數
    total_fishing = user_data.get("total_fishing_count", 0)
    draw.text(
        (250, y + 12),
        "🎣 釣魚次數",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (250, y + 35),
        f"{total_fishing:,}",
        font=section_font,
        fill=GAME_COLORS["accent_blue"],
    )

    # 今日簽到
    signed_in = user_data.get("signed_in_today", False)
    sign_text = "✅ 已簽到" if signed_in else "❌ 未簽到"
    sign_color = GAME_COLORS["success"] if signed_in else GAME_COLORS["error"]
    draw.text((450, y + 25), sign_text, font=content_font, fill=sign_color)

    y += 105

    # 2. 當前裝備
    draw.text((25, y), "⚔️ 當前裝備", font=section_font, fill=GAME_COLORS["accent_blue"])
    y += 35

    # 裝備卡片
    draw_game_card(
        draw,
        (20, y, width - 20, y + 190),
        radius=12,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    # 魚竿
    rod = user_data.get("current_rod")
    if rod:
        rod_name = rod.get("name", "無魚竿")
        rarity = rod.get("rarity", 1)
        stars = format_rarity_display(rarity)
        color = get_rarity_color(rarity)

        draw.text(
            (35, y + 10), "🎣 魚竿", font=small_font, fill=GAME_COLORS["text_secondary"]
        )
        draw.text(
            (35, y + 32),
            rod_name[:15],
            font=content_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text((35, y + 55), stars, font=tiny_font, fill=color)

        # 耐久
        max_dur = rod.get("max_durability")
        cur_dur = rod.get("current_durability")
        if max_dur:
            dur_pct = cur_dur / max_dur if max_dur > 0 else 0
            dur_color = (
                GAME_COLORS["success"] if dur_pct > 0.3 else GAME_COLORS["warning"]
            )
            draw.text(
                (35, y + 75),
                f"耐久: {cur_dur}/{max_dur}",
                font=tiny_font,
                fill=dur_color,
            )
        else:
            draw.text(
                (35, y + 75),
                "♾️ 無限耐久",
                font=tiny_font,
                fill=GAME_COLORS["accent_blue"],
            )
        _draw_equipment_bonuses(
            draw,
            (35, y + 115),
            rod,
            tiny_font,
        )
    else:
        draw.text(
            (35, y + 32),
            "🎣 無裝備魚竿",
            font=content_font,
            fill=GAME_COLORS["text_muted"],
        )

    # 飾品
    accessory = user_data.get("current_accessory")
    if accessory:
        acc_name = accessory.get("name", "無飾品")
        rarity = accessory.get("rarity", 1)
        stars = format_rarity_display(rarity)
        color = get_rarity_color(rarity)

        draw.text(
            (280, y + 10),
            "💍 飾品",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text(
            (280, y + 32),
            acc_name[:15],
            font=content_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text((280, y + 55), stars, font=tiny_font, fill=color)
        _draw_equipment_bonuses(
            draw,
            (280, y + 95),
            accessory,
            tiny_font,
        )
    else:
        draw.text(
            (280, y + 32),
            "💍 無裝備飾品",
            font=content_font,
            fill=GAME_COLORS["text_muted"],
        )

    # 魚餌
    bait = user_data.get("current_bait")
    if bait:
        bait_name = bait.get("name", "無魚餌")
        draw.text(
            (500, y + 10),
            "🪱 魚餌",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text(
            (500, y + 32),
            bait_name[:10],
            font=content_font,
            fill=GAME_COLORS["text_primary"],
        )

        duration = bait.get("duration_minutes", 0)
        if duration > 0:
            draw.text(
                (500, y + 55),
                f"剩餘 {duration} 分鐘",
                font=tiny_font,
                fill=GAME_COLORS["accent_blue"],
            )
        _draw_equipment_bonuses(
            draw,
            (500, y + 75),
            bait,
            tiny_font,
        )
    else:
        draw.text(
            (500, y + 32),
            "🪱 無使用魚餌",
            font=content_font,
            fill=GAME_COLORS["text_muted"],
        )
    y += 205

    # 3. 功能狀態
    draw.text(
        (25, y), "⚡ 功能狀態", font=section_font, fill=GAME_COLORS["accent_gold"]
    )
    y += 35

    # 狀態卡片
    draw_game_card(
        draw,
        (20, y, width - 20, y + 145),
        radius=12,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    # 自動釣魚
    auto_fishing = user_data.get("auto_fishing_enabled", False)
    auto_text = "🤖 自動釣魚: 已開啟" if auto_fishing else "🤖 自動釣魚: 已關閉"
    auto_color = GAME_COLORS["success"] if auto_fishing else GAME_COLORS["error"]
    draw.text((35, y + 12), auto_text, font=content_font, fill=auto_color)

    # 電魚冷卻
    electric_cd = user_data.get("electric_fish_cooldown_remaining", 0)
    electric_text = format_time(electric_cd)
    electric_color = (
        GAME_COLORS["success"] if electric_cd <= 0 else GAME_COLORS["warning"]
    )
    draw.text(
        (35, y + 40),
        f"⚡ 電魚: {electric_text}",
        font=content_font,
        fill=electric_color,
    )

    # 偷魚冷卻
    steal_cd = user_data.get("steal_cooldown_remaining", 0)
    steal_text = format_time(steal_cd)
    steal_color = GAME_COLORS["success"] if steal_cd <= 0 else GAME_COLORS["warning"]
    draw.text(
        (35, y + 68), f"🦹 偷魚: {steal_text}", font=content_font, fill=steal_color
    )

    # 擦彈次數
    wipe_bomb = user_data.get("wipe_bomb_remaining", 0)
    draw.text(
        (380, y + 12),
        f"💣 擦彈剩餘: {wipe_bomb} 次",
        font=content_font,
        fill=GAME_COLORS["accent_blue"],
    )

    # 命運之輪
    wof_plays = user_data.get("wof_remaining_plays", 0)
    draw.text(
        (380, y + 40),
        f"🎡 命運之輪: {wof_plays} 次",
        font=content_font,
        fill=GAME_COLORS["accent_gold"],
    )

    # 釣魚區域
    zone = user_data.get("fishing_zone", "未知區域")
    draw.text(
        (380, y + 68),
        f"🗺️ 區域: {zone}",
        font=content_font,
        fill=GAME_COLORS["text_secondary"],
    )

    # 通行證過期時間
    zone_pass_expires = user_data.get("zone_pass_expires_at")
    if zone_pass_expires:
        from ..core.utils import get_now

        now = get_now()
        if zone_pass_expires.year >= 9999:
            pass_text = "🎫 通行證: 永久"
            pass_color = GAME_COLORS["accent_gold"]
        elif zone_pass_expires > now:
            remaining = zone_pass_expires - now
            total_seconds = int(remaining.total_seconds())
            if total_seconds < 3600:
                minutes = total_seconds // 60
                pass_text = f"🎫 通行證: {minutes}分鐘"
            elif total_seconds < 86400:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                pass_text = f"🎫 通行證: {hours}時{minutes}分"
            else:
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                pass_text = f"🎫 通行證: {days}天{hours}時"
            pass_color = GAME_COLORS["success"]
        else:
            pass_text = "🎫 通行證: 已過期"
            pass_color = GAME_COLORS["error"]
        draw.text((35, y + 96), pass_text, font=content_font, fill=pass_color)

    y += 145

    # 底部
    draw_game_divider(draw, 30, width - 30, y + 10)
    draw.text(
        (30, y + 25),
        "💡 指令：/狀態 查看詳情  |  /幫助 查看所有指令",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def get_user_state_data(
    user_repo,
    inventory_repo,
    item_template_repo,
    log_repo,
    buff_repo,
    game_config,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    获取用户状态数据

    Args:
        user_repo: 用户仓储
        inventory_repo: 库存仓储
        item_template_repo: 物品模板仓储
        log_repo: 日志仓储
        buff_repo: 用户增益仓储
        game_config: 游戏配置
        user_id: 用户ID

    Returns:
        包含用户状态信息的字典，如果用户不存在则返回None
    """
    import json
    from ..core.utils import get_now, get_today

    # 获取用户基本信息
    user = user_repo.get_by_id(user_id)
    if not user:
        return None

    # 获取当前装备的鱼竿
    current_rod = None
    rod_instance = inventory_repo.get_user_equipped_rod(user_id)
    if not rod_instance and getattr(user, "equipped_rod_instance_id", None):
        rod_instance = inventory_repo.get_user_rod_instance_by_id(
            user_id, user.equipped_rod_instance_id
        )
    if rod_instance:
        rod_template = item_template_repo.get_rod_by_id(rod_instance.rod_id)
        if rod_template:
            # 计算精炼后的最大耐久度，与背包一致：原始 * (1.5)^(精炼等级-1)
            if rod_template.durability is not None:
                refined_max_durability = int(
                    rod_template.durability
                    * (1.5 ** (max(rod_instance.refine_level, 1) - 1))
                )
            else:
                refined_max_durability = None

            # 如果实例是无限耐久，则上限也视为 None
            if rod_instance.current_durability is None:
                refined_max_durability = None

            current_rod = {
                "name": rod_template.name,
                "rarity": rod_template.rarity,
                "refine_level": rod_instance.refine_level,
                "current_durability": rod_instance.current_durability,
                "max_durability": refined_max_durability,
                "description": rod_template.description,
                "bonus_fish_quality_modifier": calculate_after_refine(
                    rod_template.bonus_fish_quality_modifier,
                    refine_level=rod_instance.refine_level,
                    rarity=rod_template.rarity,
                ),
                "bonus_fish_quantity_modifier": calculate_after_refine(
                    rod_template.bonus_fish_quantity_modifier,
                    refine_level=rod_instance.refine_level,
                    rarity=rod_template.rarity,
                ),
                "bonus_rare_fish_chance": calculate_after_refine(
                    rod_template.bonus_rare_fish_chance,
                    refine_level=rod_instance.refine_level,
                    rarity=rod_template.rarity,
                ),
                "weight_modifier": calculate_after_refine(
                    getattr(rod_template, "weight_modifier", 1.0),
                    refine_level=rod_instance.refine_level,
                    rarity=rod_template.rarity,
                ),
            }

    # 获取当前装备的饰品
    current_accessory = None
    accessory_instance = inventory_repo.get_user_equipped_accessory(user_id)
    if not accessory_instance and getattr(user, "equipped_accessory_instance_id", None):
        accessory_instance = inventory_repo.get_user_accessory_instance_by_id(
            user_id, user.equipped_accessory_instance_id
        )
    if accessory_instance:
        accessory_template = item_template_repo.get_accessory_by_id(
            accessory_instance.accessory_id
        )
        if accessory_template:
            current_accessory = {
                "name": accessory_template.name,
                "rarity": accessory_template.rarity,
                "refine_level": accessory_instance.refine_level,
                "description": accessory_template.description,
                "bonus_fish_quality_modifier": calculate_after_refine(
                    accessory_template.bonus_fish_quality_modifier,
                    refine_level=accessory_instance.refine_level,
                    rarity=accessory_template.rarity,
                ),
                "bonus_fish_quantity_modifier": calculate_after_refine(
                    accessory_template.bonus_fish_quantity_modifier,
                    refine_level=accessory_instance.refine_level,
                    rarity=accessory_template.rarity,
                ),
                "bonus_rare_fish_chance": calculate_after_refine(
                    accessory_template.bonus_rare_fish_chance,
                    refine_level=accessory_instance.refine_level,
                    rarity=accessory_template.rarity,
                ),
                "bonus_coin_modifier": calculate_after_refine(
                    accessory_template.bonus_coin_modifier,
                    refine_level=accessory_instance.refine_level,
                    rarity=accessory_template.rarity,
                ),
                "weight_modifier": calculate_after_refine(
                    getattr(accessory_template, "weight_modifier", 1.0),
                    refine_level=accessory_instance.refine_level,
                    rarity=accessory_template.rarity,
                ),
            }

    # 获取当前使用的鱼饵
    current_bait = None
    if user.current_bait_id:
        bait_template = item_template_repo.get_bait_by_id(user.current_bait_id)
        if bait_template:
            # 获取用户的鱼饵库存
            bait_inventory = inventory_repo.get_user_bait_inventory(user_id)
            bait_quantity = bait_inventory.get(user.current_bait_id, 0)
            current_bait = {
                "name": bait_template.name,
                "rarity": bait_template.rarity,
                "quantity": bait_quantity,
                "description": bait_template.description,
                "duration_minutes": bait_template.duration_minutes,
                "success_rate_modifier": bait_template.success_rate_modifier,
                "rare_chance_modifier": bait_template.rare_chance_modifier,
                "garbage_reduction_modifier": bait_template.garbage_reduction_modifier,
                "value_modifier": bait_template.value_modifier,
                "quantity_modifier": bait_template.quantity_modifier,
                "weight_modifier": bait_template.weight_modifier,
            }

    # 获取钓鱼区域信息
    fishing_zone = None
    if user.fishing_zone_id:
        zone = inventory_repo.get_zone_by_id(user.fishing_zone_id)
        if zone:
            fishing_zone = zone.name if hasattr(zone, "name") else str(zone)

    # 计算偷鱼剩余CD时间
    steal_cooldown_remaining = 0
    if user.last_steal_time:
        cooldown_seconds = game_config.get("steal", {}).get("cooldown_seconds", 14400)
        now = get_now()
        # 处理时区问题
        if user.last_steal_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif user.last_steal_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=user.last_steal_time.tzinfo)

        elapsed = (now - user.last_steal_time).total_seconds()
        if elapsed < cooldown_seconds:
            steal_cooldown_remaining = int(cooldown_seconds - elapsed)

    # 计算电鱼CD时间
    electric_fish_cooldown_remaining = 0
    if hasattr(user, "last_electric_fish_time") and user.last_electric_fish_time:
        cooldown_seconds = game_config.get("electric_fish", {}).get(
            "cooldown_seconds", 7200
        )
        now = get_now()
        if user.last_electric_fish_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif user.last_electric_fish_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=user.last_electric_fish_time.tzinfo)

        elapsed = (now - user.last_electric_fish_time).total_seconds()
        if elapsed < cooldown_seconds:
            electric_fish_cooldown_remaining = int(cooldown_seconds - elapsed)

    # 获取当前称号
    current_title = None
    if hasattr(user, "current_title_id") and user.current_title_id:
        try:
            # 尝试从各种可能的来源获取称号信息
            title_info = None
            if hasattr(item_template_repo, "get_title_by_id"):
                title_info = item_template_repo.get_title_by_id(user.current_title_id)

            if title_info:
                current_title = {
                    "id": user.current_title_id,
                    "name": title_info.name
                    if hasattr(title_info, "name")
                    else str(title_info),
                    "display_format": title_info.display_format
                    if hasattr(title_info, "display_format")
                    else "{name}",
                }
            else:
                # 如果无法获取详细信息，至少显示称号ID
                current_title = {
                    "id": user.current_title_id,
                    "name": f"称号#{user.current_title_id}",
                    "display_format": "{name}",
                }
        except:
            # 如果获取称号失败，忽略
            current_title = None

    # 获取总钓鱼次数
    total_fishing_count = getattr(user, "total_fishing_count", 0)

    # 检查今日是否签到
    signed_in_today = False
    if hasattr(user, "last_login_time") and user.last_login_time:
        today = get_now().date()
        last_login_date = (
            user.last_login_time.date()
            if hasattr(user.last_login_time, "date")
            else user.last_login_time
        )
        signed_in_today = last_login_date == today

    # 计算擦弹剩余次数
    wipe_bomb_remaining = 0
    # 确保 user 对象有新添加的字段，做向后兼容
    if hasattr(user, "last_wipe_bomb_date") and hasattr(
        user, "wipe_bomb_attempts_today"
    ):
        base_max_attempts = game_config.get("wipe_bomb", {}).get(
            "max_attempts_per_day", 3
        )
        extra_attempts = 0
        boost_buff = buff_repo.get_active_by_user_and_type(
            user_id, "WIPE_BOMB_ATTEMPTS_BOOST"
        )
        if boost_buff and boost_buff.payload:
            try:
                extra_attempts = json.loads(boost_buff.payload).get("amount", 0)
            except json.JSONDecodeError:
                pass

        total_max_attempts = base_max_attempts + extra_attempts

        today_str = get_today().strftime("%Y-%m-%d")
        used_attempts_today = 0
        # 如果记录的日期是今天，就使用记录的次数；否则次数为0
        if user.last_wipe_bomb_date == today_str:
            used_attempts_today = user.wipe_bomb_attempts_today

        wipe_bomb_remaining = max(0, total_max_attempts - used_attempts_today)
    else:
        # 如果数据库中的用户数据还没有新字段（例如，尚未迁移），提供一个默认值
        wipe_bomb_remaining = game_config.get("wipe_bomb", {}).get(
            "max_attempts_per_day", 3
        )

    # 计算命运之轮剩余次数
    wheel_of_fate_daily_limit = game_config.get("wheel_of_fate_daily_limit", 3)
    wof_remaining_plays = 0
    if hasattr(user, "last_wof_date") and hasattr(user, "wof_plays_today"):
        today_str = get_today().strftime("%Y-%m-%d")
        if user.last_wof_date == today_str:
            wof_remaining_plays = max(
                0, wheel_of_fate_daily_limit - user.wof_plays_today
            )
        else:
            wof_remaining_plays = wheel_of_fate_daily_limit
    else:
        # 兼容旧数据，给予最大次数
        wof_remaining_plays = wheel_of_fate_daily_limit

    # 获取鱼塘信息
    pond_info = None
    try:
        # 使用与inventory_service.get_user_fish_pond相同的逻辑获取鱼塘信息
        inventory_items = inventory_repo.get_fish_inventory(user_id)
        total_value = inventory_repo.get_fish_inventory_value(user_id)

        # 计算总鱼数
        total_count = (
            sum(item.quantity for item in inventory_items) if inventory_items else 0
        )

        if total_count > 0 or total_value > 0:
            pond_info = {"total_count": total_count, "total_value": total_value}
        else:
            pond_info = {"total_count": 0, "total_value": 0}

    except Exception as e:
        # 如果获取鱼塘信息失败，设置为默认值
        pond_info = {"total_count": 0, "total_value": 0}

    return {
        "user_id": user.user_id,
        "nickname": user.nickname or user.user_id,
        "coins": user.coins,
        "premium_currency": getattr(user, "premium_currency", 0),
        "current_rod": current_rod,
        "current_accessory": current_accessory,
        "current_bait": current_bait,
        "auto_fishing_enabled": user.auto_fishing_enabled,
        "steal_cooldown_remaining": steal_cooldown_remaining,
        "electric_fish_cooldown_remaining": electric_fish_cooldown_remaining,
        "fishing_zone": fishing_zone,
        "current_title": current_title,
        "total_fishing_count": total_fishing_count,
        "signed_in_today": signed_in_today,
        "wipe_bomb_remaining": wipe_bomb_remaining,
        "pond_info": pond_info,
        "wof_remaining_plays": wof_remaining_plays,
        "zone_pass_expires_at": user.zone_pass_expires_at,
    }
