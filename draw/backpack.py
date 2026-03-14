"""
背包界面 - 遊戲風格美化版
優化版本：顯示精煉等級、裝備狀態、鎖定狀態等完整信息
支持分頁顯示，避免單張圖片過大
"""

import os
import math
from datetime import datetime
from typing import Dict, Any, List, Tuple
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

# 每頁最大高度（避免圖片過大）
MAX_PAGE_HEIGHT = 3000

# 每行顯示的卡片數量
CARDS_PER_ROW = 3

# 各類型卡片的尺寸配置
CARD_HEIGHTS = {
    "rod": 122,
    "accessory": 122,
    "bait": 82,
    "item": 82,
}

# 各類型卡片行高
ROW_HEIGHTS = {
    "rod": 130,
    "accessory": 130,
    "bait": 90,
    "item": 90,
}


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
    """背包界面 - 遊戲風格優化版（單頁，向後兼容）"""
    pages = draw_backpack_pages(user_data, data_dir)
    return pages[0] if pages else create_game_gradient(880, 500)


def draw_backpack_pages(user_data: Dict[str, Any], data_dir: str) -> List[Image.Image]:
    """繪製背包圖片，支持分頁

    Args:
        user_data: 包含背包數據的字典
        data_dir: 數據目錄路徑

    Returns:
        List[Image.Image]: 圖片頁面列表
    """
    width = 880
    header_h = 100
    section_gap = 16
    footer_h = 50

    rods = user_data.get("rods", [])
    accessories = user_data.get("accessories", [])
    baits = user_data.get("baits", [])
    items = user_data.get("items", [])

    nickname = user_data.get("nickname", "未知用戶")
    current_title = user_data.get("current_title")

    from ..core.utils import format_user_display_name

    display_name = format_user_display_name(nickname, current_title)

    # 構建所有部分的內容
    sections = []

    # 魚竿區域
    sections.append(
        {
            "type": "section_header",
            "title": "🎣 魚竿",
            "color": GAME_COLORS["accent_blue"],
        }
    )
    if rods:
        for rod in rods:
            sections.append({"type": "rod_card", "data": rod})
    else:
        sections.append({"type": "empty_hint", "text": "暫無魚竿"})

    # 飾品區域
    sections.append(
        {
            "type": "section_header",
            "title": "💍 飾品",
            "color": GAME_COLORS["accent_gold"],
        }
    )
    if accessories:
        for acc in accessories:
            sections.append({"type": "accessory_card", "data": acc})
    else:
        sections.append({"type": "empty_hint", "text": "暫無飾品"})

    # 魚餌區域
    sections.append(
        {
            "type": "section_header",
            "title": "🪱 魚餌",
            "color": GAME_COLORS["success"],
        }
    )
    if baits:
        for bait in baits:
            sections.append({"type": "bait_card", "data": bait})
    else:
        sections.append({"type": "empty_hint", "text": "暫無魚餌"})

    # 道具區域
    sections.append(
        {
            "type": "section_header",
            "title": "📦 道具",
            "color": GAME_COLORS["accent_red"],
        }
    )
    if items:
        for item in items:
            sections.append({"type": "item_card", "data": item})
    else:
        sections.append({"type": "empty_hint", "text": "暫無道具"})

    # 計算每頁的內容並生成圖片
    pages = []
    current_page_sections = []
    current_page_height = header_h + footer_h + 30

    def estimate_section_height(section: Dict) -> int:
        """估算單個部分的高度"""
        if section["type"] == "section_header":
            return 36 + section_gap
        elif section["type"] == "empty_hint":
            return 50 + section_gap
        elif section["type"] in ("rod_card", "accessory_card"):
            # 每行3個卡片，計算當前行是否已滿
            return 0  # 卡片高度在繪製時計算
        elif section["type"] in ("bait_card", "item_card"):
            return 0  # 卡片高度在繪製時計算
        return 0

    def render_page(
        page_sections: List[Dict], page_num: int, total_pages: int
    ) -> Image.Image:
        """渲染單頁內容"""
        # 先計算所需高度
        y = header_h + 12
        card_counts = {"rod": 0, "accessory": 0, "bait": 0, "item": 0}

        for section in page_sections:
            if section["type"] == "section_header":
                y += 36 + section_gap
            elif section["type"] == "empty_hint":
                y += 50 + section_gap
            elif section["type"] == "rod_card":
                card_counts["rod"] += 1
            elif section["type"] == "accessory_card":
                card_counts["accessory"] += 1
            elif section["type"] == "bait_card":
                card_counts["bait"] += 1
            elif section["type"] == "item_card":
                card_counts["item"] += 1

        # 計算卡片區域高度
        for card_type, count in card_counts.items():
            if count > 0:
                rows = math.ceil(count / CARDS_PER_ROW)
                y += rows * ROW_HEIGHTS[card_type] + section_gap

        height = y + footer_h + SAFETY_MARGIN

        # 創建圖片
        image = create_game_gradient(width, height)
        draw = ImageDraw.Draw(image)

        title_font = load_font(28)
        section_font = load_font(22)
        content_font = load_font(16)
        small_font = load_font(14)
        tiny_font = load_font(12)

        # 繪製標題
        page_indicator = f" ({page_num}/{total_pages})" if total_pages > 1 else ""
        draw_game_title_bar(
            draw,
            width,
            0,
            header_h,
            f"{display_name} 的背包{page_indicator}",
            title_font,
            "🎒",
        )

        y = header_h + 12

        # 繪製內容
        current_card_type = None
        card_index = 0

        for section in page_sections:
            if section["type"] == "section_header":
                # 如果之前有卡片未完成的行，補齊高度
                if current_card_type and card_index > 0:
                    rows = math.ceil(card_index / CARDS_PER_ROW)
                    y += rows * ROW_HEIGHTS[current_card_type]
                    y += section_gap

                current_card_type = None
                card_index = 0

                draw.text(
                    (24, y), section["title"], font=section_font, fill=section["color"]
                )
                y += 36

            elif section["type"] == "empty_hint":
                current_card_type = None
                card_index = 0
                draw.text(
                    (40, y + 15),
                    section["text"],
                    font=content_font,
                    fill=GAME_COLORS["text_muted"],
                )
                y += 50 + section_gap

            elif section["type"] == "rod_card":
                if current_card_type != "rod":
                    if current_card_type and card_index > 0:
                        rows = math.ceil(card_index / CARDS_PER_ROW)
                        y += rows * ROW_HEIGHTS[current_card_type] + section_gap
                    current_card_type = "rod"
                    card_index = 0

                col = card_index % CARDS_PER_ROW
                row = card_index // CARDS_PER_ROW
                x = 16 + col * 288
                card_y = y + row * ROW_HEIGHTS["rod"]

                _draw_rod_card(
                    draw, x, card_y, section["data"], content_font, tiny_font
                )
                card_index += 1

            elif section["type"] == "accessory_card":
                if current_card_type != "accessory":
                    if current_card_type and card_index > 0:
                        rows = math.ceil(card_index / CARDS_PER_ROW)
                        y += rows * ROW_HEIGHTS[current_card_type] + section_gap
                    current_card_type = "accessory"
                    card_index = 0

                col = card_index % CARDS_PER_ROW
                row = card_index // CARDS_PER_ROW
                x = 16 + col * 288
                card_y = y + row * ROW_HEIGHTS["accessory"]

                _draw_accessory_card(
                    draw, x, card_y, section["data"], content_font, tiny_font
                )
                card_index += 1

            elif section["type"] == "bait_card":
                if current_card_type != "bait":
                    if current_card_type and card_index > 0:
                        rows = math.ceil(card_index / CARDS_PER_ROW)
                        y += rows * ROW_HEIGHTS[current_card_type] + section_gap
                    current_card_type = "bait"
                    card_index = 0

                col = card_index % CARDS_PER_ROW
                row = card_index // CARDS_PER_ROW
                x = 16 + col * 288
                card_y = y + row * ROW_HEIGHTS["bait"]

                _draw_bait_card(
                    draw,
                    x,
                    card_y,
                    section["data"],
                    content_font,
                    small_font,
                    tiny_font,
                )
                card_index += 1

            elif section["type"] == "item_card":
                if current_card_type != "item":
                    if current_card_type and card_index > 0:
                        rows = math.ceil(card_index / CARDS_PER_ROW)
                        y += rows * ROW_HEIGHTS[current_card_type] + section_gap
                    current_card_type = "item"
                    card_index = 0

                col = card_index % CARDS_PER_ROW
                row = card_index // CARDS_PER_ROW
                x = 16 + col * 288
                card_y = y + row * ROW_HEIGHTS["item"]

                _draw_item_card(
                    draw,
                    x,
                    card_y,
                    section["data"],
                    content_font,
                    small_font,
                    tiny_font,
                )
                card_index += 1

        # 補齊最後一個卡片區域
        if current_card_type and card_index > 0:
            rows = math.ceil(card_index / CARDS_PER_ROW)
            y += rows * ROW_HEIGHTS[current_card_type] + section_gap

        # 繪製底部提示
        draw_game_divider(draw, 24, width - 24, y + 8)
        draw.text(
            (24, y + 20),
            "💡 /使用 短碼 | /精煉 短碼 | /出售 短碼",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

        return image

    # 簡化分頁邏輯：如果物品不多，生成單頁
    total_cards = len(rods) + len(accessories) + len(baits) + len(items)
    if total_cards <= 30:
        pages = [render_page(sections, 1, 1)]
    else:
        # 物品較多時，按類型分頁
        # 第一頁：魚竿和飾品
        page1_sections = []
        page1_sections.append(
            {
                "type": "section_header",
                "title": "🎣 魚竿",
                "color": GAME_COLORS["accent_blue"],
            }
        )
        if rods:
            for rod in rods:
                page1_sections.append({"type": "rod_card", "data": rod})
        else:
            page1_sections.append({"type": "empty_hint", "text": "暫無魚竿"})

        page1_sections.append(
            {
                "type": "section_header",
                "title": "💍 飾品",
                "color": GAME_COLORS["accent_gold"],
            }
        )
        if accessories:
            for acc in accessories:
                page1_sections.append({"type": "accessory_card", "data": acc})
        else:
            page1_sections.append({"type": "empty_hint", "text": "暫無飾品"})

        # 第二頁：魚餌和道具
        page2_sections = []
        page2_sections.append(
            {
                "type": "section_header",
                "title": "🪱 魚餌",
                "color": GAME_COLORS["success"],
            }
        )
        if baits:
            for bait in baits:
                page2_sections.append({"type": "bait_card", "data": bait})
        else:
            page2_sections.append({"type": "empty_hint", "text": "暫無魚餌"})

        page2_sections.append(
            {
                "type": "section_header",
                "title": "📦 道具",
                "color": GAME_COLORS["accent_red"],
            }
        )
        if items:
            for item in items:
                page2_sections.append({"type": "item_card", "data": item})
        else:
            page2_sections.append({"type": "empty_hint", "text": "暫無道具"})

        pages = [render_page(page1_sections, 1, 2), render_page(page2_sections, 2, 2)]

    return pages


def _draw_rod_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    card_y: int,
    rod: Dict[str, Any],
    content_font,
    tiny_font,
):
    """繪製魚竿卡片"""
    draw_game_card(
        draw,
        (x, card_y, x + 280, card_y + CARD_HEIGHTS["rod"]),
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

    name_display = f"{display_code} {name[:12]}"
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


def _draw_accessory_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    card_y: int,
    acc: Dict[str, Any],
    content_font,
    tiny_font,
):
    """繪製飾品卡片"""
    draw_game_card(
        draw,
        (x, card_y, x + 280, card_y + CARD_HEIGHTS["accessory"]),
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

    name_display = f"{display_code} {name[:12]}"
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


def _draw_bait_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    card_y: int,
    bait: Dict[str, Any],
    content_font,
    small_font,
    tiny_font,
):
    """繪製魚餌卡片"""
    draw_game_card(
        draw,
        (x, card_y, x + 280, card_y + CARD_HEIGHTS["bait"]),
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
        f"{status_icons}{display_code} {name[:12]}",
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
            (x + 10, card_y + 64),
            effect[:28],
            font=tiny_font,
            fill=GAME_COLORS["text_muted"],
        )


def _draw_item_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    card_y: int,
    item: Dict[str, Any],
    content_font,
    small_font,
    tiny_font,
):
    """繪製道具卡片"""
    draw_game_card(
        draw,
        (x, card_y, x + 280, card_y + CARD_HEIGHTS["item"]),
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
        f"{display_code} {name[:12]}",
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
            effect[:28],
            font=tiny_font,
            fill=GAME_COLORS["text_muted"],
        )


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
