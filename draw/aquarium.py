"""
水族箱展示 - 精美的水族館風格界面
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

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def format_rarity_display(rarity: int) -> str:
    """格式化稀有度顯示"""
    if rarity <= 10:
        return "★" * rarity
    else:
        return "★★★★★★★★★★+"


def draw_aquarium_image(
    user_data: Dict[str, Any], fishes: List[Dict[str, Any]], stats: Dict[str, Any]
) -> Image.Image:
    """
    繪製水族箱展示圖片
    
    Args:
        user_data: 用戶數據（包含 nickname 和 current_title）
        fishes: 魚類列表
        stats: 統計數據（total_count, capacity, total_value, available_space）
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
        # 每個魚類卡片高度約 80px，每行3個
        rows = math.ceil(len(fish_list) / 3)
        section_h = 40 + (rows * 90) + 10  # 標題 + 卡片行 + 間距
        section_heights.append(section_h)

    # 如果沒有魚，顯示空狀態
    if not fishes:
        section_heights = [120]  # 空狀態提示區域

    calculated_height = (
        header_h + sum(section_heights) + section_gap * len(section_heights) + footer_h + 40
    )
    height = calculated_height + SAFETY_MARGIN

    # 創建遊戲風格背景（使用深藍色調，模擬水族箱）
    image = create_game_gradient(width, height, color_scheme="aquarium")
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
        draw, width, 0, header_h, f"{display_name} 的水族箱", title_font, "🐠"
    )

    # 統計信息欄（在標題下方）
    stats_y = header_h - 45
    draw.text(
        (30, stats_y),
        f"🐟 {stats['total_count']}/{stats['capacity']} 條",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (200, stats_y),
        f"💰 總價值: {stats['total_value']:,} 金幣",
        font=small_font,
        fill=GAME_COLORS["accent_gold"],
    )
    draw.text(
        (500, stats_y),
        f"📦 剩餘空間: {stats['available_space']} 條",
        font=small_font,
        fill=GAME_COLORS["accent_blue"],
    )

    y = header_h + 15

    # 如果沒有魚，顯示空狀態
    if not fishes:
        draw_game_card(
            draw,
            (20, y, width - 20, y + 100),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )
        
        empty_text = "🐠 您的水族箱是空的"
        draw.text(
            (width // 2 - 120, y + 25),
            empty_text,
            font=section_font,
            fill=GAME_COLORS["text_secondary"],
        )
        
        hint_text = "💡 使用 /放入水族箱 <魚ID> 來添加魚類"
        draw.text(
            (width // 2 - 200, y + 60),
            hint_text,
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )
        
        y += 120
    else:
        # 按稀有度從高到低顯示
        for rarity in sorted(fishes_by_rarity.keys(), reverse=True):
            fish_list = fishes_by_rarity[rarity]
            
            # 稀有度標題
            stars = format_rarity_display(rarity)
            rarity_color = get_rarity_color(rarity)
            
            draw.text(
                (30, y),
                f"{stars} 稀有度",
                font=section_font,
                fill=rarity_color,
            )
            y += 40

            # 繪製魚類卡片（每行3個）
            card_width = 280
            card_height = 80
            cards_per_row = 3
            x_start = 20
            x_gap = 10

            for idx, fish in enumerate(fish_list):
                row = idx // cards_per_row
                col = idx % cards_per_row
                
                card_x = x_start + col * (card_width + x_gap)
                card_y = y + row * (card_height + 10)

                # 繪製魚類卡片
                draw_game_card(
                    draw,
                    (card_x, card_y, card_x + card_width, card_y + card_height),
                    radius=8,
                    fill=GAME_COLORS["bg_light"],
                    border_color=rarity_color,
                    shadow=True,
                )

                # 魚類名稱
                fish_name = fish.get("name", "未知魚類")
                if len(fish_name) > 10:
                    fish_name = fish_name[:9] + "..."
                
                # 品質標識
                quality_level = fish.get("quality_level", 0)
                quality_display = " ✨" if quality_level == 1 else ""
                
                draw.text(
                    (card_x + 10, card_y + 8),
                    f"{fish_name}{quality_display}",
                    font=content_font,
                    fill=GAME_COLORS["text_primary"],
                )

                # 數量和價值
                quantity = fish.get("quantity", 0)
                actual_value = fish.get("actual_value", 0)
                
                draw.text(
                    (card_x + 10, card_y + 32),
                    f"數量: {quantity} 條",
                    font=small_font,
                    fill=GAME_COLORS["text_secondary"],
                )
                
                draw.text(
                    (card_x + 10, card_y + 52),
                    f"價值: {actual_value:,} 金幣/條",
                    font=tiny_font,
                    fill=GAME_COLORS["accent_gold"],
                )

                # 魚ID（右上角）
                fish_id = fish.get("fish_id", 0)
                if quality_level == 1:
                    fcode = f"F{fish_id}H"
                else:
                    fcode = f"F{fish_id}"
                
                draw.text(
                    (card_x + card_width - 60, card_y + 8),
                    fcode,
                    font=tiny_font,
                    fill=GAME_COLORS["text_muted"],
                )

            # 更新y位置到下一個稀有度區域
            rows = math.ceil(len(fish_list) / cards_per_row)
            y += rows * (card_height + 10) + section_gap

    # 底部操作提示
    y += 20
    draw.text(
        (30, y),
        "💡 操作提示",
        font=section_font,
        fill=GAME_COLORS["accent_blue"],
    )
    y += 35

    draw_game_card(
        draw,
        (20, y, width - 20, y + footer_h - 20),
        radius=10,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    hints = [
        "• /放入水族箱 <魚ID> [數量] - 將魚從魚塘放入水族箱",
        "• /移出水族箱 <魚ID> [數量] - 將魚從水族箱移回魚塘",
        "• /升級水族箱 - 擴大水族箱容量",
    ]

    hint_y = y + 10
    for hint in hints:
        draw.text(
            (35, hint_y),
            hint,
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        hint_y += 20

    return image
