"""
背包界面 - 遊戲風格美化版
優化版本：顯示精煉等級、裝備狀態、鎖定狀態等完整信息
"""

import os
import math
from datetime import datetime
from typing import Dict, Any, List
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

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def format_rarity_display(rarity: int) -> str:
    """格式化稀有度顯示 - 支持1-10+星"""
    rarity = int(rarity) if rarity else 1
    if rarity <= 0:
        return "★"
    elif rarity <= 10:
        return "★" * rarity
    else:
        return "★" * 10 + "+"


def format_refine_display(refine_level: int) -> str:
    """格式化精煉等級顯示"""
    if refine_level <= 1:
        return ""
    return f"+{refine_level}"


def draw_backpack_image(user_data: Dict[str, Any], data_dir: str) -> Image.Image:
    """背包界面 - 遊戲風格優化版"""
    width = 950
    header_h = 120
    section_gap = 20
    footer_h = 60

    # 計算各區域高度
    rods = user_data.get("rods", [])
    accessories = user_data.get("accessories", [])
    baits = user_data.get("baits", [])
    items = user_data.get("items", [])

    # 卡片高度：魚竿和飾品需要更多空間顯示信息
    rod_rows = math.ceil(len(rods) / 3) if rods else 0
    acc_rows = math.ceil(len(accessories) / 3) if accessories else 0
    bait_rows = math.ceil(len(baits) / 3) if baits else 0
    item_rows = math.ceil(len(items) / 3) if items else 0

    # 每個區域：標題40px + 內容
    # 魚竿/飾品卡片高度160px（增加空間顯示精煉信息）
    rod_h = (40 + rod_rows * 160) if rods else 60
    acc_h = (40 + acc_rows * 160) if accessories else 60
    bait_h = (40 + bait_rows * 110) if baits else 60
    item_h = (40 + item_rows * 110) if items else 60

    calculated_height = (
        header_h + rod_h + acc_h + bait_h + item_h + section_gap * 5 + footer_h + 40
    )
    height = calculated_height + SAFETY_MARGIN

    # 創建遊戲風格背景
    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    # 字體
    title_font = load_font(34)
    section_font = load_font(26)
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
        draw, width, 0, header_h, f"{display_name} 的背包", title_font, "🎒"
    )

    y = header_h + 15

    # 1. 魚竿區域
    draw.text((30, y), "🎣 魚竿", font=section_font, fill=GAME_COLORS["accent_blue"])
    y += 40

    if rods:
        rod_rows = math.ceil(len(rods) / 3)
        rod_section_height = rod_rows * 160

        for i, rod in enumerate(rods):
            col = i % 3
            row = i // 3
            x = 20 + col * 310
            card_y = y + row * 160

            # 卡片背景
            draw_game_card(
                draw,
                (x, card_y, x + 300, card_y + 150),
                radius=10,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            # 第一行：短碼 + 名稱 + 精煉等級
            display_code = rod.get("display_code", "")
            name = rod.get("name", "未知魚竿")
            refine_level = rod.get("refine_level", 1)
            is_equipped = rod.get("is_equipped", False)
            is_locked = rod.get("is_locked", False)

            # 狀態圖標
            status_icons = ""
            if is_equipped:
                status_icons += "⚔️"
            if is_locked:
                status_icons += "🔒"

            # 名稱行（短碼 + 名稱）
            name_display = f"{display_code} {name[:8]}"
            if status_icons:
                name_display = f"{status_icons} {name_display}"
            draw.text(
                (x + 12, card_y + 8),
                name_display,
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            # 精煉等級（顯著顯示）
            if refine_level > 1:
                refine_color = get_rarity_color(min(refine_level + 3, 10))
                draw.text(
                    (x + 220, card_y + 8),
                    f"+{refine_level}",
                    font=content_font,
                    fill=refine_color,
                )

            # 第二行：稀有度
            rarity = rod.get("rarity", 1)
            stars = format_rarity_display(rarity)
            color = get_rarity_color(rarity)
            draw.text((x + 12, card_y + 32), stars, font=tiny_font, fill=color)

            # 第三行起：屬性加成（精煉後的數值）
            attr_y = card_y + 54
            bonus_quality = rod.get("bonus_fish_quality_modifier", 1.0)
            bonus_quantity = rod.get("bonus_fish_quantity_modifier", 1.0)
            bonus_rare = rod.get("bonus_rare_fish_chance", 0)

            if bonus_quality > 1:
                draw.text(
                    (x + 12, attr_y),
                    f"品質+{int((bonus_quality - 1) * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["success"],
                )
                attr_y += 16
            if bonus_quantity > 1:
                draw.text(
                    (x + 12, attr_y),
                    f"數量+{int((bonus_quantity - 1) * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["success"],
                )
                attr_y += 16
            if bonus_rare > 0:
                draw.text(
                    (x + 12, attr_y),
                    f"稀有+{int(bonus_rare * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_gold"],
                )
                attr_y += 16

            # 最後一行：耐久度
            max_dur = rod.get("max_durability")
            cur_dur = rod.get("current_durability")
            dur_y = card_y + 125

            if max_dur:
                # 計算耐久百分比
                if cur_dur is None:
                    draw.text(
                        (x + 12, dur_y),
                        "♾️ 無限",
                        font=tiny_font,
                        fill=GAME_COLORS["accent_blue"],
                    )
                else:
                    dur_percent = (cur_dur / max_dur * 100) if max_dur > 0 else 0
                    if dur_percent > 50:
                        dur_color = GAME_COLORS["success"]
                    elif dur_percent > 20:
                        dur_color = GAME_COLORS["warning"]
                    else:
                        dur_color = GAME_COLORS["error"]
                    draw.text(
                        (x + 12, dur_y),
                        f"耐久 {cur_dur}/{max_dur}",
                        font=tiny_font,
                        fill=dur_color,
                    )
            else:
                draw.text(
                    (x + 12, dur_y),
                    "♾️ 無限",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_blue"],
                )

        y += rod_section_height + section_gap
    else:
        draw.text(
            (50, y + 20), "暫無魚竿", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 60 + section_gap

    # 2. 飾品區域
    draw.text((30, y), "💍 飾品", font=section_font, fill=GAME_COLORS["accent_gold"])
    y += 40

    if accessories:
        acc_rows = math.ceil(len(accessories) / 3)
        acc_section_height = acc_rows * 160

        for i, acc in enumerate(accessories):
            col = i % 3
            row = i // 3
            x = 20 + col * 310
            card_y = y + row * 160

            draw_game_card(
                draw,
                (x, card_y, x + 300, card_y + 150),
                radius=10,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            # 數據
            display_code = acc.get("display_code", "")
            name = acc.get("name", "未知飾品")
            refine_level = acc.get("refine_level", 1)
            is_equipped = acc.get("is_equipped", False)
            is_locked = acc.get("is_locked", False)

            # 狀態圖標
            status_icons = ""
            if is_equipped:
                status_icons += "⚔️"
            if is_locked:
                status_icons += "🔒"

            # 名稱行
            name_display = f"{display_code} {name[:8]}"
            if status_icons:
                name_display = f"{status_icons} {name_display}"
            draw.text(
                (x + 12, card_y + 8),
                name_display,
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            # 精煉等級
            if refine_level > 1:
                refine_color = get_rarity_color(min(refine_level + 3, 10))
                draw.text(
                    (x + 220, card_y + 8),
                    f"+{refine_level}",
                    font=content_font,
                    fill=refine_color,
                )

            # 稀有度
            rarity = acc.get("rarity", 1)
            stars = format_rarity_display(rarity)
            color = get_rarity_color(rarity)
            draw.text((x + 12, card_y + 32), stars, font=tiny_font, fill=color)

            # 屬性加成
            attr_y = card_y + 54
            modifiers = [
                (
                    "bonus_fish_quality_modifier",
                    "品質",
                    lambda v: f"+{int((v - 1) * 100)}%",
                ),
                (
                    "bonus_fish_quantity_modifier",
                    "數量",
                    lambda v: f"+{int((v - 1) * 100)}%",
                ),
                ("bonus_rare_fish_chance", "稀有", lambda v: f"+{int(v * 100)}%"),
                ("bonus_coin_modifier", "金幣", lambda v: f"+{int((v - 1) * 100)}%"),
            ]

            for key, label, fmt in modifiers:
                val = acc.get(key, 1.0 if "modifier" in key else 0)
                if key == "bonus_rare_fish_chance":
                    if val > 0:
                        draw.text(
                            (x + 12, attr_y),
                            f"{label}{fmt(val)}",
                            font=tiny_font,
                            fill=GAME_COLORS["accent_gold"],
                        )
                        attr_y += 16
                elif val > 1:
                    draw.text(
                        (x + 12, attr_y),
                        f"{label}{fmt(val)}",
                        font=tiny_font,
                        fill=GAME_COLORS["success"],
                    )
                    attr_y += 16
                if attr_y > card_y + 115:
                    break

        y += acc_section_height + section_gap
    else:
        draw.text(
            (50, y + 20), "暫無飾品", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 60 + section_gap

    # 3. 魚餌區域
    draw.text((30, y), "🪱 魚餌", font=section_font, fill=GAME_COLORS["success"])
    y += 40

    if baits:
        bait_rows = math.ceil(len(baits) / 3)
        bait_section_height = bait_rows * 110

        for i, bait in enumerate(baits):
            col = i % 3
            row = i // 3
            x = 20 + col * 310
            card_y = y + row * 110

            draw_game_card(
                draw,
                (x, card_y, x + 300, card_y + 100),
                radius=8,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            display_code = bait.get("display_code", "")
            name = bait.get("name", "未知魚餌")
            qty = bait.get("quantity", 0)
            is_equipped = bait.get("is_equipped", False)
            bait_id = int(bait.get("bait_id") or bait.get("id") or 0)
            if not display_code and bait_id > 0:
                display_code = f"B{bait_id}"

            status_icons = "⚔️ " if is_equipped else ""
            draw.text(
                (x + 12, card_y + 8),
                f"{status_icons}{display_code} {name[:8]}",
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            draw.text(
                (x + 12, card_y + 32),
                f"數量: {qty}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

            duration = bait.get("duration_minutes", 0)
            if duration > 0:
                draw.text(
                    (x + 12, card_y + 52),
                    f"⏱️ {duration}分鐘",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_blue"],
                )

            effect = normalize_display_text(bait.get("effect_description"))
            if effect:
                draw.text(
                    (x + 12, card_y + 72),
                    effect[:20],
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

        y += bait_section_height + section_gap
    else:
        draw.text(
            (50, y + 20), "暫無魚餌", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 60 + section_gap

    # 4. 道具區域
    draw.text((30, y), "📦 道具", font=section_font, fill=GAME_COLORS["accent_red"])
    y += 40

    if items:
        item_rows = math.ceil(len(items) / 3)
        item_section_height = item_rows * 110

        for i, item in enumerate(items):
            col = i % 3
            row = i // 3
            x = 20 + col * 310
            card_y = y + row * 110

            draw_game_card(
                draw,
                (x, card_y, x + 300, card_y + 100),
                radius=8,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            display_code = item.get("display_code", "")
            name = item.get("name", "未知道具")
            qty = item.get("quantity", 0)
            item_id = int(item.get("item_id") or item.get("id") or 0)
            if not display_code and item_id > 0:
                display_code = f"D{item_id}"

            draw.text(
                (x + 12, card_y + 8),
                f"{display_code} {name[:8]}",
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            draw.text(
                (x + 12, card_y + 32),
                f"數量: {qty}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

            effect = normalize_display_text(item.get("effect_description"))
            if effect:
                draw.text(
                    (x + 12, card_y + 55),
                    effect[:20],
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

        y += item_section_height + section_gap
    else:
        draw.text(
            (50, y + 20), "暫無道具", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 60 + section_gap

    # 底部提示
    draw_game_divider(draw, 30, width - 30, y + 10)
    draw.text(
        (30, y + 25),
        "💡 使用：/使用 短碼 | 精煉：/精煉 短碼 | 出售：/出售 短碼",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def get_user_backpack_data(
    inventory_service, user_id: str, max_items_per_category: int = 50
) -> Dict[str, Any]:
    rod_result = inventory_service.get_user_rod_inventory(user_id) or {}
    acc_result = inventory_service.get_user_accessory_inventory(user_id) or {}
    bait_result = inventory_service.get_user_bait_inventory(user_id) or {}
    item_result = inventory_service.get_user_item_inventory(user_id) or {}

    rods = list(rod_result.get("rods", []) or [])
    accessories = list(acc_result.get("accessories", []) or [])
    baits = list(bait_result.get("baits", []) or [])
    items = list(item_result.get("items", []) or [])

    for bait in baits:
        if not bait.get("display_code"):
            bait_id = int(bait.get("bait_id") or bait.get("id") or 0)
            if bait_id > 0:
                bait["display_code"] = f"B{bait_id}"

    for item in items:
        if not item.get("display_code"):
            item_id = int(item.get("item_id") or item.get("id") or 0)
            if item_id > 0:
                item["display_code"] = f"D{item_id}"

    total_rods = len(rods)
    total_accessories = len(accessories)
    total_baits = len(baits)
    total_items = len(items)

    rods_filtered = False
    accessories_filtered = False

    if max_items_per_category and total_rods > max_items_per_category:
        rods = [r for r in rods if int(r.get("rarity", 0) or 0) >= 5]
        rods = rods[:max_items_per_category]
        rods_filtered = True
    if max_items_per_category and total_accessories > max_items_per_category:
        accessories = [a for a in accessories if int(a.get("rarity", 0) or 0) >= 5]
        accessories = accessories[:max_items_per_category]
        accessories_filtered = True

    if max_items_per_category and total_baits > max_items_per_category:
        baits = baits[:max_items_per_category]
    if max_items_per_category and total_items > max_items_per_category:
        items = items[:max_items_per_category]

    is_truncated = (
        rods_filtered
        or accessories_filtered
        or total_baits > max_items_per_category
        or total_items > max_items_per_category
    )

    return {
        "rods": rods,
        "accessories": accessories,
        "baits": baits,
        "items": items,
        "total_rods": total_rods,
        "total_accessories": total_accessories,
        "total_baits": total_baits,
        "total_items": total_items,
        "displayed_rods": len(rods),
        "displayed_accessories": len(accessories),
        "is_truncated": is_truncated,
        "rods_filtered": rods_filtered,
        "accessories_filtered": accessories_filtered,
    }
