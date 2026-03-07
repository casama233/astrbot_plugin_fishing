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
    width = 1180
    header_h = 118
    row_h = 34
    card_gap = 8
    footer_h = 68 if footer else 20

    if not rows:
        rows = ["暫無資料"]

    title_font = load_font(32)
    sub_font = load_font(16)
    body_font = load_font(18)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    row_h = max(row_h, body_h + 14)
    content_bottom = 104 + len(rows) * (row_h + card_gap)
    bottom_pad = 24
    height = content_bottom + footer_h + bottom_pad
    image = create_vertical_gradient(width, height, (241, 249, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw.text((26, 20), title, font=title_font, fill=(40, 66, 94))
    if subtitle:
        draw.text((28, 64), subtitle, font=sub_font, fill=(76, 98, 121))
    draw.line((24, 90, width - 24, 90), fill=(178, 204, 228), width=2)

    y = 104
    for line in rows:
        draw.rounded_rectangle(
            (22, y, width - 22, y + row_h),
            radius=9,
            fill=(255, 255, 255),
            outline=(219, 232, 243),
        )
        draw.text((34, y + 7), line[:130], font=body_font, fill=(64, 88, 114))
        y += row_h + card_gap

    if footer:
        footer_y = content_bottom + 8
        draw.line(
            (24, footer_y, width - 24, footer_y),
            fill=(178, 204, 228),
            width=2,
        )
        draw.text((28, footer_y + 20), footer, font=sub_font, fill=(76, 98, 121))

    return image


def draw_game_card_list_image(
    title: str,
    sections: List[dict],
    subtitle: str = "",
    footer: str = "",
    icon: str = "📋",
) -> Image.Image:
    width = 980
    header_h = 116
    section_head_h = 34
    row_h = 32
    section_gap = 14
    footer_h = 80 if footer else 24

    title_font = load_font(33)
    section_font = load_font(20)
    body_font = load_font(16)
    small_font = load_font(14)

    if not sections:
        sections = [{"title": "內容", "rows": ["暫無資料"]}]

    total_rows = sum(len(s.get("rows", []) or []) for s in sections)
    card_h = (
        len(sections) * (section_head_h + 12)
        + total_rows * row_h
        + (len(sections) - 1) * section_gap
        + 24
    )
    height = header_h + card_h + footer_h + 24

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, title, title_font, icon)
    if subtitle:
        draw.text(
            (28, 84), subtitle[:80], font=small_font, fill=GAME_COLORS["text_secondary"]
        )

    y = header_h + 14
    draw_game_card(
        draw,
        (20, y, width - 20, y + card_h),
        radius=12,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    y += 14
    for sec in sections:
        sec_title = sec.get("title", "")
        rows = sec.get("rows", []) or ["暫無資料"]
        draw.text(
            (34, y), sec_title[:60], font=section_font, fill=GAME_COLORS["accent_gold"]
        )
        y += section_head_h
        for row in rows:
            draw_game_card(
                draw,
                (30, y, width - 30, y + row_h - 4),
                radius=8,
                fill=GAME_COLORS["bg_light"],
                border_color=GAME_COLORS["border"],
                shadow=False,
            )
            draw.text(
                (42, y + 6),
                str(row)[:120],
                font=body_font,
                fill=GAME_COLORS["text_primary"],
            )
            y += row_h
        y += section_gap

    if footer:
        divider_y = height - footer_h
        draw_game_divider(draw, 30, width - 30, divider_y)
        draw.text(
            (30, divider_y + 18),
            footer[:120],
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

    return image
