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
    width = 880
    header_h = 100
    section_gap = 16
    footer_h = 50

    rods = user_data.get("rods", [])
    accessories = user_data.get("accessories", [])
    baits = user_data.get("baits", [])
    items = user_data.get("items", [])

    rod_rows = math.ceil(len(rods) / 3) if rods else 0
    acc_rows = math.ceil(len(accessories) / 3) if accessories else 0
    bait_rows = math.ceil(len(baits) / 3) if baits else 0
    item_rows = math.ceil(len(items) / 3) if items else 0

    rod_h = (36 + rod_rows * 130) if rods else 50
    acc_h = (36 + acc_rows * 130) if accessories else 50
    bait_h = (36 + bait_rows * 90) if baits else 50
    item_h = (36 + item_rows * 90) if items else 50

    calculated_height = (
        header_h + rod_h + acc_h + bait_h + item_h + section_gap * 5 + footer_h + 30
    )
    height = calculated_height + SAFETY_MARGIN

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(28)
    section_font = load_font(22)
    content_font = load_font(16)
    small_font = load_font(14)
    tiny_font = load_font(12)

    nickname = user_data.get("nickname", "未知用戶")
    current_title = user_data.get("current_title")

    from ..core.utils import format_user_display_name

    display_name = format_user_display_name(nickname, current_title)

    draw_game_title_bar(
        draw, width, 0, header_h, f"{display_name} 的背包", title_font, "🎒"
    )

    y = header_h + 12

    draw.text((24, y), "🎣 魚竿", font=section_font, fill=GAME_COLORS["accent_blue"])
    y += 36

    if rods:
        rod_rows = math.ceil(len(rods) / 3)
        rod_section_height = rod_rows * 130

        for i, rod in enumerate(rods):
            col = i % 3
            row = i // 3
            x = 16 + col * 288
            card_y = y + row * 130

            draw_game_card(
                draw,
                (x, card_y, x + 280, card_y + 122),
                radius=8,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            display_code = rod.get("display_code", "")
            name = rod.get("name", "未知魚竿")
            refine_level = rod.get("refine_level", 1)
            is_equipped = rod.get("is_equipped", False)
            is_locked = rod.get("is_locked", False)

            status_icons = ""
            if is_equipped:
                status_icons += "⚔️"
            if is_locked:
                status_icons += "🔒"

            name_display = f"{display_code} {name[:7]}"
            if status_icons:
                name_display = f"{status_icons} {name_display}"
            draw.text(
                (x + 10, card_y + 6),
                name_display,
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            if refine_level > 1:
                refine_color = get_rarity_color(min(refine_level + 3, 10))
                draw.text(
                    (x + 200, card_y + 6),
                    f"+{refine_level}",
                    font=content_font,
                    fill=refine_color,
                )

            rarity = rod.get("rarity", 1)
            stars = format_rarity_display(rarity)
            color = get_rarity_color(rarity)
            draw.text((x + 10, card_y + 28), stars, font=tiny_font, fill=color)

            attr_y = card_y + 48
            bonus_quality = rod.get("bonus_fish_quality_modifier", 1.0)
            bonus_quantity = rod.get("bonus_fish_quantity_modifier", 1.0)
            bonus_rare = rod.get("bonus_rare_fish_chance", 0)

            if bonus_quality > 1:
                draw.text(
                    (x + 10, attr_y),
                    f"品質+{int((bonus_quality - 1) * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["success"],
                )
                attr_y += 14
            if bonus_quantity > 1:
                draw.text(
                    (x + 10, attr_y),
                    f"數量+{int((bonus_quantity - 1) * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["success"],
                )
                attr_y += 14
            if bonus_rare > 0:
                draw.text(
                    (x + 10, attr_y),
                    f"稀有+{int(bonus_rare * 100)}%",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_gold"],
                )
                attr_y += 14

            max_dur = rod.get("max_durability")
            cur_dur = rod.get("current_durability")
            dur_y = card_y + 105

            if max_dur:
                if cur_dur is None:
                    draw.text(
                        (x + 10, dur_y),
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
                        (x + 10, dur_y),
                        f"耐久 {cur_dur}/{max_dur}",
                        font=tiny_font,
                        fill=dur_color,
                    )
            else:
                draw.text(
                    (x + 10, dur_y),
                    "♾️ 無限",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_blue"],
                )

        y += rod_section_height + section_gap
    else:
        draw.text(
            (40, y + 15), "暫無魚竿", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 50 + section_gap

    draw.text((24, y), "💍 飾品", font=section_font, fill=GAME_COLORS["accent_gold"])
    y += 36

    if accessories:
        acc_rows = math.ceil(len(accessories) / 3)
        acc_section_height = acc_rows * 130

        for i, acc in enumerate(accessories):
            col = i % 3
            row = i // 3
            x = 16 + col * 288
            card_y = y + row * 130

            draw_game_card(
                draw,
                (x, card_y, x + 280, card_y + 122),
                radius=8,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            display_code = acc.get("display_code", "")
            name = acc.get("name", "未知飾品")
            refine_level = acc.get("refine_level", 1)
            is_equipped = acc.get("is_equipped", False)
            is_locked = acc.get("is_locked", False)

            status_icons = ""
            if is_equipped:
                status_icons += "⚔️"
            if is_locked:
                status_icons += "🔒"

            name_display = f"{display_code} {name[:7]}"
            if status_icons:
                name_display = f"{status_icons} {name_display}"
            draw.text(
                (x + 10, card_y + 6),
                name_display,
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            if refine_level > 1:
                refine_color = get_rarity_color(min(refine_level + 3, 10))
                draw.text(
                    (x + 200, card_y + 6),
                    f"+{refine_level}",
                    font=content_font,
                    fill=refine_color,
                )

            rarity = acc.get("rarity", 1)
            stars = format_rarity_display(rarity)
            color = get_rarity_color(rarity)
            draw.text((x + 10, card_y + 28), stars, font=tiny_font, fill=color)

            attr_y = card_y + 48
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
                            (x + 10, attr_y),
                            f"{label}{fmt(val)}",
                            font=tiny_font,
                            fill=GAME_COLORS["accent_gold"],
                        )
                        attr_y += 14
                elif val > 1:
                    draw.text(
                        (x + 10, attr_y),
                        f"{label}{fmt(val)}",
                        font=tiny_font,
                        fill=GAME_COLORS["success"],
                    )
                    attr_y += 14
                if attr_y > card_y + 100:
                    break

        y += acc_section_height + section_gap
    else:
        draw.text(
            (40, y + 15), "暫無飾品", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 50 + section_gap

    draw.text((24, y), "🪱 魚餌", font=section_font, fill=GAME_COLORS["success"])
    y += 36

    if baits:
        bait_rows = math.ceil(len(baits) / 3)
        bait_section_height = bait_rows * 90

        for i, bait in enumerate(baits):
            col = i % 3
            row = i // 3
            x = 16 + col * 288
            card_y = y + row * 90

            draw_game_card(
                draw,
                (x, card_y, x + 280, card_y + 82),
                radius=6,
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
                (x + 10, card_y + 6),
                f"{status_icons}{display_code} {name[:7]}",
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            draw.text(
                (x + 10, card_y + 28),
                f"數量: {qty}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

            duration = bait.get("duration_minutes", 0)
            if duration > 0:
                draw.text(
                    (x + 10, card_y + 46),
                    f"⏱️ {duration}分鐘",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_blue"],
                )

            effect = normalize_display_text(bait.get("effect_description"))
            if effect:
                draw.text(
                    (x + 10, card_y + 62),
                    effect[:18],
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

        y += bait_section_height + section_gap
    else:
        draw.text(
            (40, y + 15), "暫無魚餌", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 50 + section_gap

    draw.text((24, y), "📦 道具", font=section_font, fill=GAME_COLORS["accent_red"])
    y += 36

    if items:
        item_rows = math.ceil(len(items) / 3)
        item_section_height = item_rows * 90

        for i, item in enumerate(items):
            col = i % 3
            row = i // 3
            x = 16 + col * 288
            card_y = y + row * 90

            draw_game_card(
                draw,
                (x, card_y, x + 280, card_y + 82),
                radius=6,
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
                (x + 10, card_y + 6),
                f"{display_code} {name[:7]}",
                font=content_font,
                fill=GAME_COLORS["text_primary"],
            )

            draw.text(
                (x + 10, card_y + 28),
                f"數量: {qty}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

            effect = normalize_display_text(item.get("effect_description"))
            if effect:
                draw.text(
                    (x + 10, card_y + 48),
                    effect[:18],
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

        y += item_section_height + section_gap
    else:
        draw.text(
            (40, y + 15), "暫無道具", font=content_font, fill=GAME_COLORS["text_muted"]
        )
        y += 50 + section_gap

    draw_game_divider(draw, 24, width - 24, y + 8)
    draw.text(
        (24, y + 20),
        "💡 /使用 短碼 | /精煉 短碼 | /出售 短碼",
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
