import math
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .game_ui import (
    GAME_COLORS,
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    get_rarity_color,
)
from .styles import load_font
from .text_utils import normalize_display_text

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def _star(rarity: int) -> str:
    """格式化星級顯示 - 支持1-10+星"""
    r = int(rarity or 1)
    if r <= 0:
        return "⭐"
    elif r <= 10:
        return "⭐" * r
    else:
        return "⭐" * 10 + "+"


def _pct(mod: Any) -> str:
    try:
        v = float(mod)
    except Exception:
        return "0%"
    if v < 1:
        return f"{v * 100:.2f}%"
    return f"{(v - 1) * 100:.2f}%"


def draw_equipment_image(
    title: str, entries: List[Dict[str, Any]], kind: str = "rod"
) -> Image.Image:
    """裝備列表圖片 - 統一遊戲風格版"""
    width = 980
    card_h = 120
    title_bar_height = 60
    footer_h = 70
    padding = 24

    title_font = load_font(32)
    body_font = load_font(20)
    small_font = load_font(16)
    tiny_font = load_font(14)
    
    # 計算高度並添加安全邊距
    num_items = max(1, len(entries))
    calculated_height = title_bar_height + padding + (card_h + 10) * num_items + footer_h + padding
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    icon = "🎣" if kind == "rod" else "💍"
    y = padding
    draw_game_title_bar(draw, 0, y, width, title_bar_height, f"{icon} {title}", title_font)
    y += title_bar_height + padding

    # 繪製裝備列表
    for i, e in enumerate(entries, start=1):
        code = e.get("display_code") or f"ID{e.get('instance_id', '?')}"
        name = str(e.get("name", "未知裝備"))
        rarity_val = int(e.get("rarity", 1) or 1)
        rarity = _star(rarity_val)
        rarity_color = get_rarity_color(rarity_val)
        refine = int(e.get("refine_level", 1) or 1)
        equipped = "✅已裝備" if e.get("is_equipped") else ""
        locked = "🔒已鎖定" if e.get("is_locked") else "🔓未鎖定"

        bq = e.get("bonus_fish_quality_modifier", 1)
        bn = e.get("bonus_fish_quantity_modifier", 1)
        br = e.get("bonus_rare_fish_chance", 1)

        # 使用統一卡片樣式
        draw_game_card(draw, padding, y, width - padding * 2, card_h)
        
        # 裝備名稱和星級
        draw.text(
            (padding + 16, y + 10), 
            f"{i}. {name}", 
            font=body_font, 
            fill=GAME_COLORS["text_primary"]
        )
        draw.text(
            (padding + 16, y + 36), 
            rarity, 
            font=small_font, 
            fill=rarity_color
        )
        
        # 短碼、精煉、狀態
        draw.text(
            (padding + 16, y + 60),
            f"ID：{code}   精煉：+{refine}   {locked} {equipped}",
            font=tiny_font,
            fill=GAME_COLORS["text_secondary"],
        )
        
        # 屬性加成
        draw.text(
            (padding + 16, y + 82),
            f"品質+{_pct(bq)}   數量+{_pct(bn)}   稀有+{_pct(br)}",
            font=tiny_font,
            fill=GAME_COLORS["success"],
        )

        y += card_h + 10

    # 底部提示
    y = height - footer_h - padding - SAFETY_MARGIN
    draw_game_divider(draw, padding, y, width - padding * 2)
    y += 20
    if kind == "rod":
        draw.text(
            (padding + 8, y),
            "💡 快速操作：/使用 R短碼   /精煉 R短碼   /出售 R短碼",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
    else:
        draw.text(
            (padding + 8, y),
            "💡 快速操作：/使用 A短碼   /精煉 A短碼   /出售 A短碼",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

    return image
