import math
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import FONT_PATH_BOLD
from .text_utils import normalize_display_text, draw_text_smart, load_font_with_cjk_fallback


def _format_cost(cost: Dict[str, Any]) -> str:
    ctype = cost.get("cost_type")
    amount = cost.get("cost_amount", 0)
    if ctype == "coins":
        return f"💰{amount}金幣"
    if ctype == "premium":
        return f"💎{amount}高級貨幣"
    if ctype == "item":
        return f"🎁道具x{amount}"
    if ctype == "fish":
        return f"🐟魚類x{amount}"
    if ctype == "rod":
        return f"🎣魚竿x{amount}"
    if ctype == "accessory":
        return f"💍飾品x{amount}"
    return f"{ctype}:{amount}"


def draw_shop_list_image(shops: List[Dict[str, Any]]) -> Image.Image:
    width = 940
    row_h = 66
    header_h = 96
    footer_h = 86
    height = header_h + max(1, len(shops)) * row_h + footer_h

    image = create_vertical_gradient(width, height, (236, 247, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 34)
    head_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 22)
    body_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 20)
    sub_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 16)

    draw_text_smart(draw, (28, 26), "🛒 商店列表", font=title_font, fill=(40, 66, 94))
    draw.line((28, 76, width - 28, 76), fill=(176, 204, 229), width=2)

    y = header_h - 8
    for idx, shop in enumerate(shops, start=1):
        stype = shop.get("shop_type", "normal")
        tname = (
            "一般" if stype == "normal" else ("高級" if stype == "premium" else "限時")
        )
        status = "🟢營業中" if shop.get("is_active") else "🔴已關閉"
        name = str(shop.get("name", "未知商店"))
        sid = shop.get("shop_id", "?")
        desc = normalize_display_text(shop.get("description"))

        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 10),
            radius=10,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw_text_smart(draw, (36, y + 10), f"{idx}. {name}", font=head_font, fill=(34, 56, 82))
        draw_text_smart(
            draw,
            (460, y + 12),
            f"ID:{sid}  [{tname}]  {status}",
            font=body_font,
            fill=(58, 88, 116),
        )
        if desc:
            draw_text_smart(draw, (38, y + 38), desc[:58], font=sub_font, fill=(109, 129, 147))
        y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw_text_smart(
        draw,
        (30, height - footer_h + 16),
        "💡 查看詳情：/商店 商店ID",
        font=sub_font,
        fill=(63, 89, 112),
    )
    draw_text_smart(
        draw,
        (30, height - footer_h + 42),
        "💡 購買商品：/商店購買 商店ID 商品ID [數量]",
        font=sub_font,
        fill=(63, 89, 112),
    )

    return image


def draw_shop_detail_image(
    shop: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> Image.Image:
    width = 980
    card_h = 104
    header_h = 120
    footer_h = 74
    height = header_h + max(1, len(items)) * card_h + footer_h

    image = create_vertical_gradient(width, height, (239, 248, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 32)
    body_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 20)
    small_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 16)

    sname = str(shop.get("name", "未知商店"))
    sid = shop.get("shop_id", "?")
    sdesc = normalize_display_text(shop.get("description"))

    draw_text_smart(draw, (28, 20), f"🛍️ {sname}", font=title_font, fill=(40, 66, 94))
    draw_text_smart(draw, (30, 60), f"ID: {sid}", font=body_font, fill=(76, 98, 120))
    if sdesc:
        draw_text_smart(draw, (130, 60), sdesc[:68], font=body_font, fill=(76, 98, 120))
    draw.line((28, 96, width - 28, 96), fill=(176, 204, 229), width=2)

    y = 112
    for entry in items:
        item = entry.get("item", {})
        costs = entry.get("costs", []) or []
        stock_total = item.get("stock_total")
        stock_sold = int(item.get("stock_sold", 0) or 0)
        stock_text = "無限" if stock_total is None else f"{stock_sold}/{stock_total}"

        limit_parts = []
        if item.get("per_user_limit") is not None:
            limit_parts.append(f"每人限購 {item.get('per_user_limit')}")
        if item.get("per_user_daily_limit") is not None:
            limit_parts.append(f"每日限購 {item.get('per_user_daily_limit')}")
        limit_text = "｜".join(limit_parts) if limit_parts else "無"

        ctext = " + ".join(_format_cost(c) for c in costs[:3])
        if len(costs) > 3:
            ctext += " + ..."

        draw.rounded_rectangle(
            (24, y, width - 24, y + card_h - 12),
            radius=10,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw_text_smart(
            draw,
            (36, y + 10),
            f"#{item.get('item_id', '?')}  {item.get('name', '未知商品')}",
            font=body_font,
            fill=(34, 56, 82),
        )
        draw_text_smart(
            draw,
            (36, y + 40),
            f"價格：{ctext or '免費'}",
            font=small_font,
            fill=(67, 92, 116),
        )
        draw_text_smart(
            draw,
            (36, y + 64),
            f"庫存：{stock_text}   限購：{limit_text}",
            font=small_font,
            fill=(67, 92, 116),
        )
        desc = normalize_display_text(item.get("description"))
        if desc:
            draw_text_smart(draw, (520, y + 40), desc[:34], font=small_font, fill=(109, 129, 147))
        y += card_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw_text_smart(
        draw,
        (30, height - footer_h + 22),
        f"💡 購買：/商店購買 {sid} 商品ID [數量]",
        font=small_font,
        fill=(63, 89, 112),
    )

    return image
