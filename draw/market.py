from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font


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
        return "💀已腐敗"
    if remain.total_seconds() <= 86400:
        h = int(remain.total_seconds() // 3600)
        m = int((remain.total_seconds() % 3600) // 60)
        return f"⚠️{h}小時{m}分"
    d = remain.days
    h = int(remain.seconds // 3600)
    return f"⏰{d}天{h}小時"


def _to_rows(
    grouped_items: Dict[str, Iterable[Any]],
) -> List[Tuple[str, str, List[str]]]:
    sections: List[Tuple[str, str, List[str]]] = []
    mapping = [
        ("rod", "🎣", "魚竿"),
        ("accessory", "💍", "飾品"),
        ("commodity", "📦", "大宗商品"),
        ("item", "🎁", "道具"),
        ("fish", "🐟", "魚類"),
    ]

    for key, emoji, label in mapping:
        rows: List[str] = []
        for item in list(grouped_items.get(key, []))[:12]:
            code = _market_display_code(item)
            name = str(_get_attr(item, "item_name", "未知商品"))
            price = int(_get_attr(item, "price", 0) or 0)
            qty = int(_get_attr(item, "quantity", 1) or 1)
            refine = int(_get_attr(item, "refine_level", 1) or 1)
            seller = (
                "🎭匿名賣家"
                if _get_attr(item, "is_anonymous", False)
                else str(_get_attr(item, "seller_nickname", "未知賣家"))
            )
            quality = (
                " ✨高品質"
                if int(_get_attr(item, "quality_level", 0) or 0) == 1
                else ""
            )
            refine_text = f" 精{refine}" if refine > 1 else ""
            qty_text = f" x{qty}" if qty > 1 else ""
            expire_text = ""
            if key == "commodity":
                expire_text = _format_expire(_get_attr(item, "expires_at"))
                if expire_text:
                    expire_text = f"｜{expire_text}"
            rows.append(
                f"{name}{quality}{refine_text}{qty_text}  ID:{code}  {price:,}金幣  {seller}{expire_text}"
            )
        if rows:
            sections.append((emoji, label, rows))
    return sections


def draw_market_list_image(grouped_items: Dict[str, Iterable[Any]]) -> Image.Image:
    sections = _to_rows(grouped_items)
    row_h = 34
    sec_head_h = 38
    header_h = 98
    footer_h = 82

    total_rows = sum(len(rows) for _, _, rows in sections)
    total_sections = len(sections)
    height = header_h + total_rows * row_h + total_sections * sec_head_h + footer_h
    width = 1280

    image = create_vertical_gradient(width, height, (239, 248, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(34)
    head_font = load_font(22)
    body_font = load_font(18)
    small_font = load_font(16)

    draw.text((28, 24), "🛒 市場商品列表", font=title_font, fill=(38, 62, 86))
    draw.line((28, 76, width - 28, 76), fill=(176, 204, 229), width=2)

    y = 94
    for emoji, label, rows in sections:
        draw.rounded_rectangle(
            (24, y, width - 24, y + sec_head_h - 6),
            radius=10,
            fill=(250, 253, 255),
            outline=(210, 225, 238),
        )
        draw.text((36, y + 8), f"{emoji} {label}", font=head_font, fill=(46, 73, 102))
        y += sec_head_h

        for line in rows:
            draw.rounded_rectangle(
                (30, y, width - 30, y + row_h - 6),
                radius=8,
                fill=(255, 255, 255),
                outline=(224, 234, 243),
            )
            draw.text((42, y + 6), line[:110], font=body_font, fill=(61, 86, 113))
            y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 16),
        "💡 掛單有效期 5 天，逾期自動下架返還",
        font=small_font,
        fill=(63, 89, 112),
    )
    draw.text(
        (30, height - footer_h + 42),
        "💡 購買示例：/購買 C5",
        font=small_font,
        fill=(63, 89, 112),
    )

    return image
