from typing import Any, Dict, List, Union

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

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def _safe_get(obj: Union[Dict, Any], key: str, default: Any = None) -> Any:
    """安全获取属性或字典值"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def draw_gacha_pool_list_image(pools: List[Any]) -> Image.Image:
    """卡池列表圖片 - 統一遊戲風格版"""
    width = 940
    card_height = 90
    title_bar_height = 60
    footer_height = 80
    spacing = 12
    padding = 24

    title_font = load_font(32)
    body_font = load_font(20)
    small_font = load_font(16)
    
    # 計算高度並添加安全邊距
    num_pools = max(1, len(pools))
    calculated_height = title_bar_height + padding + (card_height + spacing) * num_pools + footer_height + padding
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    y = padding
    draw_game_title_bar(draw, 0, y, width, title_bar_height, "🎰 抽卡池列表", title_font)
    y += title_bar_height + padding

    # 繪製卡池列表
    for idx, pool in enumerate(pools, start=1):
        pid = _safe_get(pool, "gacha_pool_id", "?")
        name = str(_safe_get(pool, "name", "未知卡池"))
        desc = str(_safe_get(pool, "description") or "")
        if _safe_get(pool, "cost_premium_currency"):
            cost_text = f"💎 {_safe_get(pool, 'cost_premium_currency')} 高級貨幣 / 次"
        else:
            cost_text = f"💰 {_safe_get(pool, 'cost_coins', 0)} 金幣 / 次"

        # 使用統一卡片樣式
        draw_game_card(draw, padding, y, width - padding * 2, card_height)
        
        # 卡池信息
        draw.text(
            (padding + 16, y + 12), 
            f"{idx}. ID {pid}｜{name[:20]}", 
            font=body_font, 
            fill=GAME_COLORS["text_primary"]
        )
        draw.text(
            (padding + 16, y + 42), 
            cost_text, 
            font=small_font, 
            fill=GAME_COLORS["text_secondary"]
        )
        if desc:
            draw.text(
                (padding + 16, y + 64), 
                desc[:50], 
                font=small_font, 
                fill=GAME_COLORS["text_tertiary"]
            )
        
        y += card_height + spacing

    # 繪製底部提示
    y = height - footer_height - padding - SAFETY_MARGIN
    draw_game_divider(draw, padding, y, width - padding * 2)
    y += 16
    draw.text(
        (padding + 8, y),
        "💡 查看詳情：/查看卡池 ID",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    y += 28
    draw.text(
        (padding + 8, y),
        "💡 單抽 / 十連：/抽卡 ID /十連 ID [次數]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_gacha_pool_detail_image(
    pool: Union[Dict[str, Any], Any], probabilities: List[Union[Dict[str, Any], Any]]
) -> Image.Image:
    """卡池詳情圖片 - 統一遊戲風格版"""
    width = 980
    item_height = 50
    title_bar_height = 60
    info_section_height = 80
    footer_height = 70
    spacing = 10
    padding = 24

    title_font = load_font(30)
    body_font = load_font(20)
    small_font = load_font(16)
    
    # 計算高度並添加安全邊距
    num_items = max(1, len(probabilities))
    calculated_height = title_bar_height + info_section_height + padding + (item_height + spacing) * num_items + footer_height + padding
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    pool_name = _safe_get(pool, 'name', '卡池詳情')
    y = padding
    draw_game_title_bar(draw, 0, y, width, title_bar_height, f"🎰 {pool_name[:30]}", title_font)
    y += title_bar_height + 12
    
    # 卡池信息區域
    pool_id = _safe_get(pool, 'gacha_pool_id', '?')
    draw.text(
        (padding + 8, y),
        f"ID：{pool_id}",
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    
    cost_premium = _safe_get(pool, "cost_premium_currency")
    if cost_premium:
        cost_text = f"💎 消耗：{cost_premium} 高級貨幣 / 次"
    else:
        cost_coins = _safe_get(pool, 'cost_coins', 0)
        cost_text = f"💰 消耗：{cost_coins} 金幣 / 次"
    
    draw.text(
        (padding + 200, y),
        cost_text,
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    y += 32

    # 描述
    desc = str(_safe_get(pool, "description") or "")
    if desc:
        draw.text(
            (padding + 8, y), 
            f"📖 {desc[:60]}", 
            font=small_font, 
            fill=GAME_COLORS["text_secondary"]
        )
        y += 28
    
    y += 12
    draw_game_divider(draw, padding, y, width - padding * 2)
    y += spacing + 12

    # 概率列表
    for item in probabilities:
        rarity = int(_safe_get(item, "item_rarity", 1) or 1)
        rarity = max(1, min(rarity, 10))  # 限制在1-10星範圍
        stars = "⭐" * rarity
        name = _safe_get(item, "item_name", "未知物品")
        prob = _safe_get(item, "probability", 0)
        try:
            ptext = f"{float(prob) * 100:.3f}%"
        except Exception:
            ptext = str(prob)

        # 使用統一卡片樣式
        draw_game_card(draw, padding, y, width - padding * 2, item_height)
        
        # 使用統一稀有度顏色
        rarity_color = get_rarity_color(rarity)
        draw.text(
            (padding + 16, y + 14), 
            f"{stars} {name[:35]}", 
            font=small_font, 
            fill=rarity_color
        )
        draw.text(
            (width - 200, y + 14), 
            f"機率：{ptext}", 
            font=small_font, 
            fill=GAME_COLORS["text_secondary"]
        )
        y += item_height + spacing

    # 底部提示
    y = height - footer_height - padding - SAFETY_MARGIN
    draw_game_divider(draw, padding, y, width - padding * 2)
    y += 20
    draw.text(
        (padding + 8, y),
        f"💡 抽卡：/抽卡 {pool_id}   十連：/十連 {pool_id}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
