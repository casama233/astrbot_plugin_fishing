from typing import List

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_divider,
    draw_game_title_bar,
    GAME_COLORS,
)
from .styles import load_font


def draw_text_list_image(
    title: str,
    rows: List[str],
    subtitle: str = "",
    footer: str = "",
) -> Image.Image:
    width = 880
    header_h = 70
    row_h = 38
    card_gap = 6
    footer_h = 60 if footer else 16

    if not rows:
        rows = ["暫無資料"]

    title_font = load_font(26)
    sub_font = load_font(16)
    body_font = load_font(17)

    content_bottom = header_h + 10 + len(rows) * (row_h + card_gap)
    bottom_pad = 16
    height = content_bottom + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, title, title_font, "📜")

    if subtitle:
        draw.text(
            (24, header_h - 14),
            subtitle,
            font=sub_font,
            fill=GAME_COLORS["text_secondary"],
        )

    y = header_h + 10
    for line in rows:
        draw_game_card(
            draw,
            (16, y, width - 16, y + row_h),
            radius=8,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
            shadow=True,
        )
        draw.text(
            (28, y + 9), line[:100], font=body_font, fill=GAME_COLORS["text_primary"]
        )
        y += row_h + card_gap

    if footer:
        footer_y = content_bottom + 4
        draw_game_divider(draw, 20, width - 20, footer_y)
        draw.text(
            (24, footer_y + 12),
            footer,
            font=sub_font,
            fill=GAME_COLORS["text_secondary"],
        )

    return image


def draw_game_card_list_image(
    title: str,
    sections: List[dict],
    subtitle: str = "",
    footer: str = "",
    icon: str = "📋",
) -> Image.Image:
    width = 880
    header_h = 100
    section_head_h = 30
    row_h = 28
    section_gap = 10
    footer_h = 60 if footer else 18

    title_font = load_font(27)
    section_font = load_font(18)
    body_font = load_font(15)
    small_font = load_font(13)

    if not sections:
        sections = [{"title": "內容", "rows": ["暫無資料"]}]

    total_rows = sum(len(s.get("rows", []) or []) for s in sections)
    card_h = (
        len(sections) * (section_head_h + 10)
        + total_rows * row_h
        + (len(sections) - 1) * section_gap
        + 20
    )
    height = header_h + card_h + footer_h + 18

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, title, title_font, icon)
    if subtitle:
        draw.text(
            (24, 72), subtitle[:70], font=small_font, fill=GAME_COLORS["text_secondary"]
        )

    y = header_h + 10
    draw_game_card(
        draw,
        (16, y, width - 16, y + card_h),
        radius=10,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    y += 12
    for sec in sections:
        sec_title = sec.get("title", "")
        rows = sec.get("rows", []) or ["暫無資料"]
        draw.text(
            (28, y), sec_title[:50], font=section_font, fill=GAME_COLORS["accent_gold"]
        )
        y += section_head_h
        for row in rows:
            draw_game_card(
                draw,
                (24, y, width - 24, y + row_h - 4),
                radius=6,
                fill=GAME_COLORS["bg_light"],
                border_color=GAME_COLORS["border"],
                shadow=False,
            )
            draw.text(
                (36, y + 5),
                str(row)[:100],
                font=body_font,
                fill=GAME_COLORS["text_primary"],
            )
            y += row_h
        y += section_gap

    if footer:
        divider_y = height - footer_h
        draw_game_divider(draw, 24, width - 24, divider_y)
        draw.text(
            (24, divider_y + 14),
            footer[:100],
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

    return image
