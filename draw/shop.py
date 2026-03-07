"""
商店界面 - 遊戲風格美化版
"""

import math
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
)
from .styles import load_font
from .text_utils import normalize_display_text


def _format_cost(cost: Dict[str, Any]) -> str:
    """格式化價格顯示"""
    ctype = cost.get("cost_type")
    amount = cost.get("cost_amount", 0)
    if ctype == "coins":
        return f"💰 {amount:,} 金幣"
    if ctype == "premium":
        return f"💎 {amount:,} 高級貨幣"
    if ctype == "item":
        return f"🎁 道具 x{amount}"
    if ctype == "fish":
        return f"🐟 魚類 x{amount}"
    if ctype == "rod":
        return f"🎣 魚竿 x{amount}"
    if ctype == "accessory":
        return f"💍 飾品 x{amount}"
    return f"{ctype}:{amount}"


def _get_shop_type_style(stype: str) -> tuple:
    """獲取商店類型樣式"""
    styles = {
        "normal": ("一般", GAME_COLORS["text_secondary"]),
        "premium": ("高級", GAME_COLORS["accent_gold"]),
        "limited": ("限時", GAME_COLORS["accent_red"]),
    }
    return styles.get(stype, ("一般", GAME_COLORS["text_secondary"]))


def draw_shop_list_image(shops: List[Dict[str, Any]]) -> Image.Image:
    """商店列表 - 遊戲風格"""
    width = 960
    row_h = 75
    header_h = 100
    footer_h = 90
    height = header_h + max(1, len(shops)) * row_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(36)
    head_font = load_font(24)
    body_font = load_font(20)
    sub_font = load_font(16)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "商店列表", title_font, "🛒")

    y = header_h + 12

    for idx, shop in enumerate(shops, start=1):
        stype = shop.get("shop_type", "normal")
        tname, tcolor = _get_shop_type_style(stype)

        is_active = shop.get("is_active", False)
        status = "🟢 營業中" if is_active else "🔴 休息中"
        status_color = GAME_COLORS["success"] if is_active else GAME_COLORS["error"]

        name = str(shop.get("name", "未知商店"))
        sid = shop.get("shop_id", "?")
        desc = normalize_display_text(shop.get("description"))

        # 商店卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h - 12),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
            shadow=True,
        )

        # 序號和名稱
        draw.text(
            (40, y + 12), f"{idx}.", font=head_font, fill=GAME_COLORS["accent_blue"]
        )
        draw.text((75, y + 12), name, font=head_font, fill=GAME_COLORS["text_primary"])

        # 商店類型標籤
        draw.rounded_rectangle(
            (40, y + 42, 40 + len(tname) * 18 + 16, y + 62),
            radius=6,
            fill=GAME_COLORS["bg_light"],
            outline=tcolor,
            width=1,
        )
        draw.text((48, y + 44), tname, font=sub_font, fill=tcolor)

        # ID 和狀態
        draw.text(
            (width - 200, y + 15),
            f"ID: {sid}",
            font=body_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text((width - 200, y + 40), status, font=sub_font, fill=status_color)

        # 描述
        if desc:
            draw.text(
                (200, y + 44), desc[:45], font=sub_font, fill=GAME_COLORS["text_muted"]
            )

        y += row_h

    # 底部提示
    draw_game_divider(draw, 30, width - 30, height - footer_h + 15)
    draw.text(
        (30, height - footer_h + 30),
        "💡 查看詳情：/商店 商店ID",
        font=sub_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (30, height - footer_h + 55),
        "💡 購買商品：/商店購買 商店ID 商品ID [數量]",
        font=sub_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_shop_detail_image(
    shop: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> Image.Image:
    """商店詳情 - 遊戲風格"""
    width = 1000
    card_h = 115
    header_h = 130
    footer_h = 80
    height = header_h + max(1, len(items)) * card_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(34)
    body_font = load_font(22)
    small_font = load_font(16)

    sname = str(shop.get("name", "未知商店"))
    sid = shop.get("shop_id", "?")
    sdesc = normalize_display_text(shop.get("description"))

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, sname, title_font, "🛍️")

    # 商店資訊
    draw.text(
        (35, 72), f"商店 ID: {sid}", font=body_font, fill=GAME_COLORS["text_secondary"]
    )

    if sdesc:
        draw.text((250, 72), sdesc[:55], font=body_font, fill=GAME_COLORS["text_muted"])

    y = header_h + 15

    for entry in items:
        item = entry.get("item", {})
        costs = entry.get("costs", []) or []
        stock_total = item.get("stock_total")
        stock_sold = int(item.get("stock_sold", 0) or 0)

        if stock_total is None:
            stock_text = "♾️ 無限"
            stock_color = GAME_COLORS["accent_blue"]
        else:
            remaining = stock_total - stock_sold
            stock_text = f"📦 剩餘 {remaining}/{stock_total}"
            stock_color = (
                GAME_COLORS["warning"]
                if remaining < stock_total * 0.2
                else GAME_COLORS["success"]
            )

        limit_parts = []
        if item.get("per_user_limit") is not None:
            limit_parts.append(f"每人限 {item.get('per_user_limit')}")
        if item.get("per_user_daily_limit") is not None:
            limit_parts.append(f"每日限 {item.get('per_user_daily_limit')}")
        limit_text = " ｜ ".join(limit_parts) if limit_parts else "無限制"

        ctext = " + ".join(_format_cost(c) for c in costs[:2])
        if len(costs) > 2:
            ctext += " + ..."

        # 商品卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + card_h - 15),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        item_id = item.get("item_id", "?")
        item_name = item.get("name", "未知商品")

        # 商品 ID 標籤
        draw.rounded_rectangle(
            (35, y + 12, 80, y + 36), radius=6, fill=GAME_COLORS["bg_light"]
        )
        draw.text(
            (42, y + 14),
            f"#{item_id}",
            font=small_font,
            fill=GAME_COLORS["accent_blue"],
        )

        # 商品名稱
        draw.text(
            (95, y + 10), item_name, font=body_font, fill=GAME_COLORS["text_primary"]
        )

        # 價格
        if ctext:
            draw.text(
                (35, y + 45),
                f"💵 {ctext}",
                font=small_font,
                fill=GAME_COLORS["accent_gold"],
            )
        else:
            draw.text(
                (35, y + 45), "🎁 免費", font=small_font, fill=GAME_COLORS["success"]
            )

        # 存貨
        draw.text((35, y + 70), stock_text, font=small_font, fill=stock_color)

        # 限購
        draw.text(
            (250, y + 70),
            f"🚫 限購: {limit_text}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

        # 描述
        desc = normalize_display_text(item.get("description"))
        if desc:
            draw.text(
                (400, y + 45),
                desc[:35],
                font=small_font,
                fill=GAME_COLORS["text_muted"],
            )

        y += card_h

    # 底部
    draw_game_divider(draw, 30, width - 30, height - footer_h + 15)
    draw.text(
        (30, height - footer_h + 30),
        f"💡 購買指令：/商店購買 {sid} 商品ID [數量]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
