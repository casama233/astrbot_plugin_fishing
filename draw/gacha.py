from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font


def draw_gacha_pool_list_image(pools: List[Dict[str, Any]]) -> Image.Image:
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
    height = header_h + max(1, len(pools)) * row_h + footer_h + bottom_pad

    image = create_vertical_gradient(width, height, (243, 246, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw.text((28, 24), "🎰 抽卡池列表", font=title_font, fill=(52, 58, 103))
    draw.line((28, 78, width - 28, 78), fill=(184, 194, 240), width=2)

    y = 94
    for idx, pool in enumerate(pools, start=1):
        pid = pool.get("gacha_pool_id", "?")
        name = str(pool.get("name", "未知卡池"))
        desc = str(pool.get("description") or "")
        if pool.get("cost_premium_currency"):
            cost_text = f"💎 {pool.get('cost_premium_currency')} 高級貨幣 / 次"
        else:
            cost_text = f"💰 {pool.get('cost_coins', 0)} 金幣 / 次"

        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 10),
            radius=10,
            fill=(255, 255, 255),
            outline=(221, 226, 247),
        )
        draw.text(
            (36, y + 10), f"{idx}. ID {pid}｜{name}", font=body_font, fill=(50, 63, 105)
        )
        draw.text((38, y + 40), cost_text, font=small_font, fill=(83, 99, 143))
        if desc:
            draw.text((390, y + 40), desc[:44], font=small_font, fill=(112, 122, 156))
        y += row_h

    footer_y = height - footer_h - bottom_pad
    draw.line((28, footer_y, width - 28, footer_y), fill=(184, 194, 240), width=2)
    draw.text(
        (30, footer_y + 16),
        "💡 查看詳情：/查看卡池 ID",
        font=small_font,
        fill=(74, 92, 134),
    )
    draw.text(
        (30, footer_y + 42),
        "💡 單抽 / 十連：/抽卡 ID   /十連 ID [次數]",
        font=small_font,
        fill=(74, 92, 134),
    )

    return image


def draw_gacha_pool_detail_image(
    pool: Dict[str, Any], probabilities: List[Dict[str, Any]]
) -> Image.Image:
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
    height = header_h + max(1, len(probabilities)) * row_h + footer_h + bottom_pad

    image = create_vertical_gradient(width, height, (242, 245, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw.text(
        (28, 20),
        f"🎰 {pool.get('name', '卡池詳情')}",
        font=title_font,
        fill=(52, 58, 103),
    )
    draw.text(
        (30, 56),
        f"ID：{pool.get('gacha_pool_id', '?')}",
        font=body_font,
        fill=(76, 86, 128),
    )
    if pool.get("cost_premium_currency"):
        draw.text(
            (180, 56),
            f"💎 消耗：{pool.get('cost_premium_currency')} 高級貨幣 / 次",
            font=body_font,
            fill=(76, 86, 128),
        )
    else:
        draw.text(
            (180, 56),
            f"💰 消耗：{pool.get('cost_coins', 0)} 金幣 / 次",
            font=body_font,
            fill=(76, 86, 128),
        )

    desc = str(pool.get("description") or "")
    if desc:
        draw.text((30, 86), f"📖 {desc[:60]}", font=small_font, fill=(110, 118, 152))

    draw.line((28, 118, width - 28, 118), fill=(184, 194, 240), width=2)

    y = 132
    for item in probabilities:
        rarity = int(item.get("item_rarity", 1) or 1)
        stars = "⭐" * max(1, min(rarity, 10))
        name = item.get("item_name", "未知物品")
        prob = item.get("probability", 0)
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
        draw.text((36, y + 10), f"{stars} {name}", font=small_font, fill=(54, 68, 111))
        draw.text(
            (width - 180, y + 10), f"機率：{ptext}", font=small_font, fill=(82, 96, 142)
        )
        y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(184, 194, 240),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 24),
        f"💡 抽卡：/抽卡 {pool.get('gacha_pool_id', 1)}   十連：/十連 {pool.get('gacha_pool_id', 1)}",
        font=small_font,
        fill=(74, 92, 134),
    )

    return image
