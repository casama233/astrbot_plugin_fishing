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

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


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
    """商店列表 - 遊戲風格（優化版）"""
    width = 880
    row_h = 65
    header_h = 80
    footer_h = 70

    title_font = load_font(28)
    head_font = load_font(22)
    body_font = load_font(18)
    sub_font = load_font(15)

    bottom_pad = 16
    calculated_height = header_h + max(1, len(shops)) * row_h + footer_h + bottom_pad
    height = calculated_height + SAFETY_MARGIN

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, "商店", title_font, "🛒")

    y = header_h + 10

    for idx, shop in enumerate(shops, start=1):
        stype = shop.get("shop_type", "normal")
        tname, tcolor = _get_shop_type_style(stype)

        is_active = shop.get("is_active", False)
        status = "🟢" if is_active else "🔴"
        status_color = GAME_COLORS["success"] if is_active else GAME_COLORS["error"]

        name = str(shop.get("name", "未知商店"))
        sid = shop.get("shop_id", "?")
        desc = normalize_display_text(shop.get("description"))

        card_y2 = y + row_h - 8
        draw_game_card(
            draw,
            (16, y, width - 16, card_y2),
            radius=10,
            fill=GAME_COLORS["bg_card"],
            border_color=tcolor if stype != "normal" else GAME_COLORS["border"],
            shadow=True,
        )

        draw.text(
            (32, y + 8), f"#{idx}", font=sub_font, fill=GAME_COLORS["accent_blue"]
        )
        draw.text(
            (65, y + 6), f"{name}", font=head_font, fill=GAME_COLORS["text_primary"]
        )

        draw.rounded_rectangle(
            (32, y + 32, 32 + len(tname) * 14 + 12, y + 50),
            radius=5,
            fill=GAME_COLORS["bg_light"],
            outline=tcolor,
            width=1,
        )
        draw.text((38, y + 34), tname, font=sub_font, fill=tcolor)

        draw.text(
            (width - 140, y + 8),
            f"ID:{sid} {status}",
            font=body_font,
            fill=GAME_COLORS["text_secondary"],
        )

        if desc:
            draw.text(
                (180, y + 35), desc[:30], font=sub_font, fill=GAME_COLORS["text_muted"]
            )

        y += row_h

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 24, width - 24, footer_y + 10)
    draw.text(
        (24, footer_y + 22),
        f"💡 查看：/商店 商店ID  |  購買：/商店購買 商店ID 商品ID",
        font=sub_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_shop_detail_image(
    shop: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> Image.Image:
    """商店詳情 - 遊戲風格（雙行顯示優化版）"""
    width = 880
    cols = 2
    card_w = (width - 48) // cols
    card_h = 105
    header_h = 80
    footer_h = 50

    title_font = load_font(28)
    name_font = load_font(20)
    body_font = load_font(17)
    sub_font = load_font(15)

    num_items = max(1, len(items))
    rows = math.ceil(num_items / cols)
    bottom_pad = 16
    height = int(header_h + rows * card_h + footer_h + bottom_pad + SAFETY_MARGIN)

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    sname = str(shop.get("name", "未知商店"))
    sid = shop.get("shop_id", "?")
    sdesc = normalize_display_text(shop.get("description"))

    draw_game_title_bar(draw, width, 0, header_h, f"🛍️ {sname}", title_font, "")

    if sdesc:
        draw.text((24, 50), sdesc[:40], font=body_font, fill=GAME_COLORS["text_muted"])
    else:
        draw.text(
            (24, 50), f"ID: {sid}", font=body_font, fill=GAME_COLORS["text_secondary"]
        )

    y = header_h + 8

    for idx, entry in enumerate(items):
        col = idx % cols
        row = idx // cols
        x = 16 + col * (card_w + 16)
        card_y = y + row * card_h

        item = entry.get("item", {})
        costs = entry.get("costs", []) or []
        rewards = entry.get("rewards", []) or []
        stock_total = item.get("stock_total")
        stock_sold = int(item.get("stock_sold", 0) or 0)

        if stock_total is None:
            stock_text = "♾️"
            stock_color = GAME_COLORS["accent_blue"]
        else:
            remaining = stock_total - stock_sold
            stock_text = f"{remaining}/{stock_total}"
            stock_color = (
                GAME_COLORS["warning"]
                if remaining < stock_total * 0.2
                else GAME_COLORS["success"]
            )

        ctext_parts = []
        for c in costs[:2]:
            ctype = c.get("cost_type")
            amount = c.get("cost_amount", 0)
            if ctype == "coins":
                ctext_parts.append(f"💰{amount:,}")
            elif ctype == "premium":
                ctext_parts.append(f"💎{amount:,}")
            else:
                ctext_parts.append(f"{amount}")
        ctext = " + ".join(ctext_parts) if ctext_parts else "🎁免費"

        draw_game_card(
            draw,
            (x, card_y, x + card_w, card_y + card_h - 4),
            radius=10,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        item_id = item.get("item_id", "?")
        item_name = item.get("name", "未知商品")

        draw.text(
            (x + 10, card_y + 8),
            f"#{item_id} {item_name[:8]}",
            font=name_font,
            fill=GAME_COLORS["text_primary"],
        )

        draw.text(
            (x + 10, card_y + 34),
            ctext,
            font=body_font,
            fill=GAME_COLORS["accent_gold"],
        )

        draw.text(
            (x + 10, card_y + 58),
            f"📦{stock_text}",
            font=body_font,
            fill=stock_color,
        )

        if rewards:
            reward_text = ""
            r = rewards[0]
            rtype = r.get("reward_type", "")
            rname = str(r.get("name", ""))[:6]
            rqty = r.get("reward_amount", 1)
            if rtype == "rod":
                reward_text = f"🎣{rname}x{rqty}"
            elif rtype == "bait":
                reward_text = f"🪱{rname}x{rqty}"
            elif rtype == "accessory":
                reward_text = f"💍{rname}x{rqty}"
            elif rtype == "item":
                reward_text = f"🎁{rname}x{rqty}"
            elif rtype == "coins":
                reward_text = f"💰{rqty}"
            if reward_text:
                if len(rewards) > 1:
                    reward_text += f" +{len(rewards) - 1}"
                draw.text(
                    (x + 10, card_y + 80),
                    reward_text,
                    font=sub_font,
                    fill=GAME_COLORS["accent_green"],
                )

        limit_text = ""
        if item.get("per_user_limit") is not None:
            limit_text = f"限{item['per_user_limit']}"
        elif item.get("per_user_daily_limit") is not None:
            limit_text = f"日限{item['per_user_daily_limit']}"
        if limit_text:
            draw.text(
                (x + card_w - 50, card_y + 58),
                limit_text,
                font=sub_font,
                fill=GAME_COLORS["text_secondary"],
            )

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 24, width - 24, footer_y + 6)
    draw.text(
        (24, footer_y + 16),
        f"💡 /商店購買 {sid} 商品ID [數量]",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
