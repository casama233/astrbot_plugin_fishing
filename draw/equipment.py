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

SAFETY_MARGIN = 50


def _star(rarity: int) -> str:
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
        return f"{v * 100:.0f}%"
    return f"{(v - 1) * 100:.0f}%"


def draw_equipment_image(
    title: str, entries: List[Dict[str, Any]], kind: str = "rod"
) -> Image.Image:
    width = 880
    cols = 2
    card_w = (width - 48) // cols
    card_h = 140
    header_h = 80
    footer_h = 55
    gap = 12

    title_font = load_font(26)
    name_font = load_font(20)
    body_font = load_font(17)
    sub_font = load_font(15)

    num_items = max(1, len(entries))
    rows = math.ceil(num_items / cols)
    bottom_pad = 16
    calculated_height = header_h + rows * (card_h + gap) + footer_h + bottom_pad
    height = calculated_height + SAFETY_MARGIN

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    icon = "🎣" if kind == "rod" else "💍"
    draw_game_title_bar(draw, width, 0, header_h, title, title_font, icon)

    for idx, e in enumerate(entries):
        col = idx % cols
        row = idx // cols
        x = 16 + col * (card_w + gap)
        y = header_h + 8 + row * (card_h + gap)

        code = e.get("display_code") or f"ID{e.get('instance_id', '?')}"
        name = str(e.get("name", "未知裝備"))
        rarity_val = int(e.get("rarity", 1) or 1)
        rarity = _star(rarity_val)
        rarity_color = get_rarity_color(rarity_val)
        refine = int(e.get("refine_level", 1) or 1)
        equipped = "⚔️" if e.get("is_equipped") else ""
        locked = "🔒" if e.get("is_locked") else ""

        bq = e.get("bonus_fish_quality_modifier", 1)
        bn = e.get("bonus_fish_quantity_modifier", 1)
        br = e.get("bonus_rare_fish_chance", 0)

        draw_game_card(
            draw,
            (x, y, x + card_w, y + card_h - 4),
            radius=10,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        name_display = f"{equipped}{locked} {name[:8]}"
        draw.text(
            (x + 10, y + 8),
            name_display,
            font=name_font,
            fill=GAME_COLORS["text_primary"],
        )

        if refine > 1:
            refine_color = get_rarity_color(min(refine + 3, 10))
            draw.text(
                (x + card_w - 45, y + 8),
                f"+{refine}",
                font=name_font,
                fill=refine_color,
            )

        draw.text((x + 10, y + 34), rarity, font=body_font, fill=rarity_color)

        draw.text(
            (x + 10, y + 58),
            f"ID:{code}",
            font=body_font,
            fill=GAME_COLORS["text_secondary"],
        )

        attrs = []
        if bq > 1:
            attrs.append(f"品質+{_pct(bq)}")
        if bn > 1:
            attrs.append(f"數量+{_pct(bn)}")
        if br > 0:
            attrs.append(f"稀有+{_pct(br)}")
        attr_text = " ".join(attrs) if attrs else "無加成"
        draw.text(
            (x + 10, y + 82), attr_text, font=sub_font, fill=GAME_COLORS["success"]
        )

        max_dur = e.get("max_durability")
        cur_dur = e.get("current_durability")
        dur_y = y + card_h - 24

        if max_dur:
            if cur_dur is None:
                draw.text(
                    (x + 10, dur_y),
                    "♾️ 無限",
                    font=sub_font,
                    fill=GAME_COLORS["accent_blue"],
                )
            else:
                dur_percent = (cur_dur / max_dur * 100) if max_dur > 0 else 0
                dur_color = (
                    GAME_COLORS["success"]
                    if dur_percent > 50
                    else GAME_COLORS["warning"]
                    if dur_percent > 20
                    else GAME_COLORS["error"]
                )
                draw.text(
                    (x + 10, dur_y),
                    f"耐久 {cur_dur}/{max_dur}",
                    font=sub_font,
                    fill=dur_color,
                )
        else:
            draw.text(
                (x + 10, dur_y),
                "♾️ 無限",
                font=sub_font,
                fill=GAME_COLORS["accent_blue"],
            )

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 24, width - 24, footer_y + 6)
    tip = (
        "💡 /使用 R短碼 | /精煉 R短碼 | /出售 R短碼"
        if kind == "rod"
        else "💡 /使用 A短碼 | /精煉 A短碼 | /出售 A短碼"
    )
    draw.text(
        (24, footer_y + 18), tip, font=sub_font, fill=GAME_COLORS["text_secondary"]
    )

    return image
