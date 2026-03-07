from typing import List

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
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
        draw.text(
            (28, footer_y + 20), footer, font=sub_font, fill=(76, 98, 121)
        )

    return image
