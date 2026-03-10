"""
鱼塘展示 - 精美的鱼塘风格界面
"""

import math
from typing import Dict, Any, List
from PIL import Image, ImageDraw

from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    GAME_COLORS,
    get_rarity_color,
)
from .styles import load_font

SAFETY_MARGIN = 50


def format_rarity_display(rarity: int) -> str:
    """格式化稀有度顯示"""
    rarity = int(rarity) if rarity else 1
    if rarity <= 0:
        return "★"
    elif rarity <= 10:
        return "★" * rarity
    else:
        return "★" * 10 + "+"


def draw_pond_image(
    user_data: Dict[str, Any],
    fishes: List[Dict[str, Any]],
    stats: Dict[str, Any],
    capacity_info: Dict[str, Any] = None,
) -> Image.Image:
    """
    繪製魚塘展示圖片

    Args:
        user_data: 用戶數據（包含 nickname 和 current_title）
        fishes: 魚類列表
        stats: 統計數據（total_count, total_value）
        capacity_info: 容量信息（current, max）
    """
    width = 900
    header_h = 120
    section_gap = 20
    footer_h = 80

    # 按稀有度分組
    fishes_by_rarity = {}
    for fish in fishes:
        rarity = fish.get("rarity", 0)
        if rarity not in fishes_by_rarity:
            fishes_by_rarity[rarity] = []
        fishes_by_rarity[rarity].append(fish)

    # 計算每個稀有度區域的高度
    section_heights = []
    for rarity in sorted(fishes_by_rarity.keys(), reverse=True):
        fish_list = fishes_by_rarity[rarity]
        rows = math.ceil(len(fish_list) / 3)
        section_h = 40 + (rows * 90) + 10
        section_heights.append(section_h)

    if not fishes:
        section_heights = [120]

    calculated_height = (
        header_h
        + sum(section_heights)
        + section_gap * len(section_heights)
        + footer_h
        + 40
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

    from ..core.utils import format_user_display_name

    display_name = format_user_display_name(nickname, current_title)

    draw_game_title_bar(
        draw, width, 0, header_h, f"{display_name} 的魚塘", title_font, "🐠"
    )

    # 統計信息欄
    stats_y = header_h - 45
    total_count = stats.get("total_count", 0)
    total_value = stats.get("total_value", 0)

    # 容量信息
    if capacity_info:
        current_cap = capacity_info.get("current", total_count)
        max_cap = capacity_info.get("max", 100)
        cap_text = f"🐟 {total_count}/{max_cap} 條"
    else:
        cap_text = f"🐟 {total_count} 條"

    draw.text(
        (30, stats_y),
        cap_text,
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (220, stats_y),
        f"💰 總價值: {total_value:,} 金幣",
        font=small_font,
        fill=GAME_COLORS["accent_gold"],
    )

    y = header_h + 15

    if not fishes:
        draw_game_card(
            draw,
            (20, y, width - 20, y + 100),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        empty_text = "🐟 您的魚塘是空的"
        draw.text(
            (width // 2 - 100, y + 25),
            empty_text,
            font=section_font,
            fill=GAME_COLORS["text_secondary"],
        )

        hint_text = "💡 快去釣魚吧！使用 /釣魚 開始"
        draw.text(
            (width // 2 - 150, y + 60),
            hint_text,
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )

        y += 120
    else:
        for rarity in sorted(fishes_by_rarity.keys(), reverse=True):
            fish_list = fishes_by_rarity[rarity]

            # 稀有度標題
            rarity_stars = format_rarity_display(rarity)
            rarity_color = get_rarity_color(rarity)

            draw.text(
                (30, y),
                f"{rarity_stars} 稀有度 {rarity}",
                font=section_font,
                fill=rarity_color,
            )
            y += 35

            # 卡片网格
            cards_per_row = 3
            card_width = (width - 60) // cards_per_row
            card_height = 80

            for i, fish in enumerate(fish_list):
                col = i % cards_per_row
                row = i // cards_per_row

                x1 = 20 + col * (card_width + 10)
                y1 = y + row * (card_height + 10)
                x2 = x1 + card_width - 10
                y2 = y1 + card_height

                # 卡片背景
                draw_game_card(
                    draw,
                    (x1, y1, x2, y2),
                    radius=10,
                    fill=GAME_COLORS["bg_card"],
                    border_color=rarity_color,
                )

                # 魚名稱
                fish_name = fish.get("name", "未知")
                quality_level = fish.get("quality_level", 0)
                if quality_level == 1:
                    fish_name += " ✨"

                draw.text(
                    (x1 + 15, y1 + 12),
                    fish_name,
                    font=content_font,
                    fill=GAME_COLORS["text_primary"],
                )

                # 數量和價值
                quantity = fish.get("quantity", 0)
                actual_value = fish.get("actual_value", 0)

                draw.text(
                    (x1 + 15, y1 + 38),
                    f"x{quantity}",
                    font=small_font,
                    fill=GAME_COLORS["accent_gold"],
                )

                draw.text(
                    (x1 + 80, y1 + 38),
                    f"💰{actual_value}/個",
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

                # ID
                fish_id = int(fish.get("fish_id", 0) or 0)
                if quality_level == 1:
                    fcode = f"F{fish_id}H"
                else:
                    fcode = f"F{fish_id}"

                draw.text(
                    (x1 + 15, y1 + 58),
                    f"ID: {fcode}",
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

            # 更新 y 位置
            rows = math.ceil(len(fish_list) / cards_per_row)
            y += rows * (card_height + 10) + 15

    return image


def get_user_pond_data(inventory_service, user_id: str) -> Dict[str, Any]:
    """
    獲取用戶魚塘數據，用於繪製圖片

    Args:
        inventory_service: 庫存服務
        user_id: 用戶ID

    Returns:
        dict: 包含 fishes 和 stats 的數據
    """
    pond_data = inventory_service.get_user_fish_pond(user_id)

    if not pond_data:
        return {
            "fishes": [],
            "stats": {"total_count": 0, "total_value": 0},
        }

    return {
        "fishes": pond_data.get("fishes", []),
        "stats": pond_data.get("stats", {"total_count": 0, "total_value": 0}),
    }
