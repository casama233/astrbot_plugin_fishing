from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def _safe_get(obj: Union[Dict, Any], key: str, default: Any = None) -> Any:
    """安全获取属性或字典值"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def draw_gacha_pool_list_image(pools: List[Any]) -> Image.Image:
    """卡池列表圖片 - 優化版"""
    width = 940
    row_h = 76
    header_h = 102
    footer_h = 84

    title_font = load_font(34)
    body_font = load_font(20)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    small_h = measure.textbbox((0, 0), "測", font=small_font)[3]
    row_h = max(row_h, body_h + small_h + 28)
    bottom_pad = 24
    
    # 計算高度並添加安全邊距
    calculated_height = header_h + max(1, len(pools)) * row_h + footer_h + bottom_pad
    height = calculated_height + SAFETY_MARGIN

    image = create_vertical_gradient(width, int(height), (243, 246, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw.text((28, 24), "🎰 抽卡池列表", font=title_font, fill=(52, 58, 103))
    draw.line((28, 78, width - 28, 78), fill=(184, 194, 240), width=2)

    y = 94
    for idx, pool in enumerate(pools, start=1):
        pid = _safe_get(pool, "gacha_pool_id", "?")
        name = str(_safe_get(pool, "name", "未知卡池"))
        desc = str(_safe_get(pool, "description") or "")
        if _safe_get(pool, "cost_premium_currency"):
            cost_text = f"💎 {_safe_get(pool, 'cost_premium_currency')} 高級貨幣 / 次"
        else:
            cost_text = f"💰 {_safe_get(pool, 'cost_coins', 0)} 金幣 / 次"

        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 10),
            radius=10,
            fill=(255, 255, 255),
            outline=(221, 226, 247),
        )
        draw.text(
            (36, y + 10), f"{idx}. ID {pid}｜{name[:20]}", font=body_font, fill=(50, 63, 105)
        )
        draw.text((38, y + 40), cost_text, font=small_font, fill=(83, 99, 143))
        if desc:
            draw.text((390, y + 40), desc[:44], font=small_font, fill=(112, 122, 156))
        y += row_h

    footer_y = height - footer_h - bottom_pad - SAFETY_MARGIN
    draw.line((28, footer_y, width - 28, footer_y), fill=(184, 194, 240), width=2)
    draw.text(
        (30, footer_y + 16),
        "💡 查看詳情：/查看卡池 ID",
        font=small_font,
        fill=(74, 92, 134),
    )
    draw.text(
        (30, footer_y + 42),
        "💡 單抽 / 十連：/抽卡 ID /十連 ID [次數]",
        font=small_font,
        fill=(74, 92, 134),
    )

    return image


def draw_gacha_pool_detail_image(
    pool: Union[Dict[str, Any], Any], probabilities: List[Union[Dict[str, Any], Any]]
) -> Image.Image:
    """卡池詳情圖片 - 優化版（統一處理字典和對象）"""
    width = 980
    row_h = 44
    header_h = 146
    footer_h = 70

    title_font = load_font(30)
    body_font = load_font(20)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    small_h = measure.textbbox((0, 0), "測", font=small_font)[3]
    row_h = max(row_h, small_h + 18)
    bottom_pad = 24
    
    # 計算高度並添加安全邊距
    calculated_height = header_h + max(1, len(probabilities)) * row_h + footer_h + bottom_pad
    height = calculated_height + SAFETY_MARGIN

    image = create_vertical_gradient(width, int(height), (242, 245, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 標題
    pool_name = _safe_get(pool, 'name', '卡池詳情')
    draw.text(
        (28, 20),
        f"🎰 {pool_name[:30]}",
        font=title_font,
        fill=(52, 58, 103),
    )
    
    # ID 和消耗
    pool_id = _safe_get(pool, 'gacha_pool_id', '?')
    draw.text(
        (30, 56),
        f"ID：{pool_id}",
        font=body_font,
        fill=(76, 86, 128),
    )
    
    cost_premium = _safe_get(pool, "cost_premium_currency")
    if cost_premium:
        draw.text(
            (180, 56),
            f"💎 消耗：{cost_premium} 高級貨幣 / 次",
            font=body_font,
            fill=(76, 86, 128),
        )
    else:
        cost_coins = _safe_get(pool, 'cost_coins', 0)
        draw.text(
            (180, 56),
            f"💰 消耗：{cost_coins} 金幣 / 次",
            font=body_font,
            fill=(76, 86, 128),
        )

    # 描述
    desc = str(_safe_get(pool, "description") or "")
    if desc:
        draw.text((30, 86), f"📖 {desc[:60]}", font=small_font, fill=(110, 118, 152))

    draw.line((28, 118, width - 28, 118), fill=(184, 194, 240), width=2)

    # 概率列表
    y = 132
    for item in probabilities:
        rarity = int(_safe_get(item, "item_rarity", 1) or 1)
        stars = "⭐" * max(1, min(rarity, 10))
        name = _safe_get(item, "item_name", "未知物品")
        prob = _safe_get(item, "probability", 0)
        try:
            ptext = f"{float(prob) * 100:.3f}%"
        except Exception:
            ptext = str(prob)

        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 8),
            radius=8,
            fill=(255, 255, 255),
            outline=(221, 226, 247),
        )
        draw.text((36, y + 10), f"{stars} {name[:35]}", font=small_font, fill=(54, 68, 111))
        draw.text(
            (width - 180, y + 10), f"機率：{ptext}", font=small_font, fill=(82, 96, 142)
        )
        y += row_h

    # 底部提示
    footer_y = height - footer_h - bottom_pad - SAFETY_MARGIN
    draw.line(
        (28, footer_y, width - 28, footer_y),
        fill=(184, 194, 240),
        width=2,
    )
    draw.text(
        (30, footer_y + 24),
        f"💡 抽卡：/抽卡 {pool_id}   十連：/十連 {pool_id}",
        font=small_font,
        fill=(74, 92, 134),
    )

    return image
