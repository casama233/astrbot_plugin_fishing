import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw

from .game_ui import (
    GAME_COLORS,
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
)
from .styles import load_font

SAFETY_MARGIN = 50


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _to_base36(n: int) -> str:
    if n < 0:
        return "0"
    if n == 0:
        return "0"
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


def _market_display_code(item: Any) -> str:
    item_type = str(_get_attr(item, "item_type", ""))
    item_instance_id = _get_attr(item, "item_instance_id")
    market_id = int(_get_attr(item, "market_id", 0) or 0)

    if item_type == "rod" and item_instance_id:
        return f"R{_to_base36(int(item_instance_id))}"
    if item_type == "accessory" and item_instance_id:
        return f"A{_to_base36(int(item_instance_id))}"
    if item_type == "commodity" and item_instance_id:
        return f"C{_to_base36(int(item_instance_id))}"
    return f"M{_to_base36(market_id)}"


def _format_expire(expires_at: Any) -> str:
    if not isinstance(expires_at, datetime):
        return ""
    remain = expires_at - datetime.now()
    if remain.total_seconds() <= 0:
        return "💀"
    if remain.total_seconds() <= 86400:
        h = int(remain.total_seconds() // 3600)
        return f"⚠️{h}h"
    d = remain.days
    return f"⏰{d}d"


def _get_rarity_stars(rarity: int) -> str:
    r = int(rarity or 1)
    if r <= 0:
        return "★"
    elif r <= 5:
        return "★" * r
    else:
        return "★" * 5 + "+"


def draw_market_list_image(grouped_items: Dict[str, Iterable[Any]]) -> Image.Image:
    width = 880
    cols = 2
    card_w = (width - 48) // cols
    card_h = 75
    header_h = 80
    section_gap = 16
    footer_h = 55

    title_font = load_font(26)
    section_font = load_font(20)
    name_font = load_font(17)
    body_font = load_font(15)

    sections_data = []
    mapping = [
        ("rod", "🎣", "魚竿"),
        ("accessory", "💍", "飾品"),
        ("commodity", "📦", "大宗商品"),
        ("item", "🎁", "道具"),
        ("fish", "🐟", "魚類"),
    ]

    for key, emoji, label in mapping:
        items_list = list(grouped_items.get(key, []))[:12]
        if items_list:
            processed = []
            for item in items_list:
                code = _market_display_code(item)
                name = str(_get_attr(item, "item_name", "未知商品"))
                price = int(_get_attr(item, "price", 0) or 0)
                qty = int(_get_attr(item, "quantity", 1) or 1)
                refine = int(_get_attr(item, "refine_level", 1) or 1)
                rarity = int(_get_attr(item, "rarity", 1) or 1)
                expire_text = ""
                if key == "commodity":
                    expire_text = _format_expire(_get_attr(item, "expires_at"))
                processed.append(
                    {
                        "code": code,
                        "name": name,
                        "price": price,
                        "qty": qty,
                        "refine": refine,
                        "rarity": rarity,
                        "expire": expire_text,
                    }
                )
            rows = math.ceil(len(processed) / cols)
            sections_data.append((emoji, label, processed, rows))

    total_item_rows = sum(rows for _, _, _, rows in sections_data)
    total_sections = len(sections_data)
    bottom_pad = 16
    calculated_height = (
        header_h
        + total_sections * 36
        + total_item_rows * (card_h + 8)
        + (total_sections - 1) * section_gap
        + footer_h
        + bottom_pad
    )
    height = calculated_height + SAFETY_MARGIN

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, "市場", title_font, "🛒")

    y = header_h + 10

    for emoji, label, items, rows_count in sections_data:
        draw.text(
            (24, y + 6),
            f"{emoji} {label}",
            font=section_font,
            fill=GAME_COLORS["accent_gold"],
        )
        y += 36

        for idx, item in enumerate(items):
            col = idx % cols
            row = idx // cols
            x = 16 + col * (card_w + 16)
            card_y = y + row * (card_h + 8)

            draw_game_card(
                draw,
                (x, card_y, x + card_w, card_y + card_h - 4),
                radius=8,
                fill=GAME_COLORS["bg_card"],
                border_color=GAME_COLORS["border"],
            )

            name_display = item["name"][:8]
            if item["qty"] > 1:
                name_display += f" x{item['qty']}"
            draw.text(
                (x + 10, card_y + 6),
                name_display,
                font=name_font,
                fill=GAME_COLORS["text_primary"],
            )

            if item["refine"] > 1:
                draw.text(
                    (x + card_w - 40, card_y + 6),
                    f"+{item['refine']}",
                    font=name_font,
                    fill=GAME_COLORS["accent_gold"],
                )

            price_text = f"💰{item['price']:,}"
            draw.text(
                (x + 10, card_y + 28),
                price_text,
                font=body_font,
                fill=GAME_COLORS["accent_gold"],
            )

            code_text = f"ID:{item['code']}"
            draw.text(
                (x + 10, card_y + 48),
                code_text,
                font=body_font,
                fill=GAME_COLORS["text_secondary"],
            )

            if item["expire"]:
                draw.text(
                    (x + card_w - 50, card_y + 48),
                    item["expire"],
                    font=body_font,
                    fill=GAME_COLORS["warning"],
                )

        y += rows_count * (card_h + 8) + section_gap

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 24, width - 24, footer_y + 6)
    draw.text(
        (24, footer_y + 18),
        "💡 掛單5天有效 | 購買：/購買 短碼",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
