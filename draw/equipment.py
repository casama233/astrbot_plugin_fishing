import math
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font
from .text_utils import normalize_display_text


def _star(rarity: int) -> str:
    r = int(rarity or 1)
    if r <= 10:
        return "⭐" * max(1, r)
    return "⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐+"


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
    width = 980
    card_h = 116
    header_h = 110
    footer_h = 78

    title_font = load_font(32)
    body_font = load_font(20)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    small_h = measure.textbbox((0, 0), "測", font=small_font)[3]
    card_h = max(card_h, body_h + small_h * 2 + 44)
    bottom_pad = 24
    height = header_h + max(1, len(entries)) * card_h + footer_h + bottom_pad

    image = create_vertical_gradient(width, height, (238, 248, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    icon = "🎣" if kind == "rod" else "💍"
    draw.text((28, 22), f"{icon} {title}", font=title_font, fill=(40, 66, 94))
    draw.line((28, 78, width - 28, 78), fill=(176, 204, 229), width=2)

    y = 94
    for i, e in enumerate(entries, start=1):
        code = e.get("display_code") or f"ID{e.get('instance_id', '?')}"
        name = str(e.get("name", "未知裝備"))
        rarity = _star(e.get("rarity", 1))
        refine = int(e.get("refine_level", 1) or 1)
        equipped = "✅已裝備" if e.get("is_equipped") else ""
        locked = "🔒已鎖定" if e.get("is_locked") else "🔓未鎖定"

        bq = e.get("bonus_fish_quality_modifier", 1)
        bn = e.get("bonus_fish_quantity_modifier", 1)
        br = e.get("bonus_rare_fish_chance", 1)

        draw.rounded_rectangle(
            (24, y, width - 24, y + card_h - 12),
            radius=10,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw.text(
            (36, y + 8), f"{i}. {name}  {rarity}", font=body_font, fill=(34, 56, 82)
        )
        draw.text(
            (36, y + 36),
            f"ID：{code}   精煉：{refine}   {locked} {equipped}",
            font=small_font,
            fill=(66, 92, 116),
        )
        draw.text(
            (36, y + 62),
            f"品質加成：{_pct(bq)}   數量加成：{_pct(bn)}   稀有加成：{_pct(br)}",
            font=small_font,
            fill=(66, 92, 116),
        )

        desc = normalize_display_text(e.get("description"))
        if desc:
            draw.text(
                (36, y + 84),
                f"說明：{desc[:70]}",
                font=small_font,
                fill=(110, 129, 147),
            )
        y += card_h

    footer_y = height - footer_h - bottom_pad
    draw.line((28, footer_y, width - 28, footer_y), fill=(176, 204, 229), width=2)
    if kind == "rod":
        draw.text(
            (30, footer_y + 24),
            "💡 快速操作：/使用 R短碼   /精煉 R短碼   /出售 R短碼",
            font=small_font,
            fill=(63, 89, 112),
        )
    else:
        draw.text(
            (30, footer_y + 24),
            "💡 快速操作：/使用 A短碼   /精煉 A短碼   /出售 A短碼",
            font=small_font,
            fill=(63, 89, 112),
        )

    return image
