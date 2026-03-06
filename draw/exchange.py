from typing import Any, Dict

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font


def draw_exchange_status_image(
    market_result: Dict[str, Any], previous_prices: Dict[str, int]
) -> Image.Image:
    prices = market_result.get("prices", {}) or {}
    commodities = market_result.get("commodities", {}) or {}
    lines = []
    for cid, price in prices.items():
        info = commodities.get(cid, {})
        name = info.get("name", cid)
        desc = info.get("description", "")
        prev = previous_prices.get(cid)
        if prev and prev > 0:
            change = price - prev
            pct = (change / prev) * 100
            if change > 0:
                trend = f"📈 +{change:,} ({pct:+.1f}%)"
            elif change < 0:
                trend = f"📉 {change:,} ({pct:+.1f}%)"
            else:
                trend = "➖ 0 (0.0%)"
        else:
            trend = "🆕 新價格"
        lines.append((name, int(price), trend, str(desc)))

    width = 1120
    header_h = 120
    row_h = 72
    footer_h = 72
    height = header_h + max(1, len(lines)) * row_h + footer_h

    image = create_vertical_gradient(width, height, (239, 248, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(34)
    body_font = load_font(21)
    small_font = load_font(16)

    draw.text((28, 22), "📈 交易所行情", font=title_font, fill=(40, 66, 94))
    draw.text(
        (30, 64),
        f"更新時間: {market_result.get('date', 'N/A')}",
        font=small_font,
        fill=(72, 95, 118),
    )
    draw.line((28, 94, width - 28, 94), fill=(176, 204, 229), width=2)

    y = 108
    for name, price, trend, desc in lines:
        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 8),
            radius=10,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw.text((36, y + 9), f"{name}", font=body_font, fill=(34, 56, 82))
        draw.text((260, y + 9), f"{price:,} 金幣", font=body_font, fill=(34, 56, 82))
        draw.text((500, y + 9), trend, font=small_font, fill=(67, 92, 116))
        if desc:
            draw.text((36, y + 40), desc[:72], font=small_font, fill=(109, 129, 147))
        y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 24),
        "💡 交易：/交易所 買入 [商品] [數量]、/交易所 賣出 [商品] [數量]",
        font=small_font,
        fill=(63, 89, 112),
    )

    return image


def draw_exchange_inventory_image(
    inventory: Dict[str, Any],
    current_prices: Dict[str, int],
    analysis: Dict[str, Any],
    capacity: int,
    current_total_quantity: int,
) -> Image.Image:
    rows = []
    for commodity_id, data in inventory.items():
        name = data.get("name", commodity_id)
        qty = int(data.get("total_quantity", 0) or 0)
        cost = int(data.get("total_cost", 0) or 0)
        price = int(current_prices.get(commodity_id, 0) or 0)
        value = qty * price
        pnl = value - cost
        rows.append((name, qty, cost, value, pnl))

    width = 1160
    header_h = 152
    row_h = 52
    footer_h = 76
    height = header_h + max(1, len(rows)) * row_h + footer_h

    image = create_vertical_gradient(width, height, (243, 247, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(32)
    body_font = load_font(20)
    small_font = load_font(16)

    draw.text((28, 20), "📦 我的交易所庫存", font=title_font, fill=(44, 61, 101))
    draw.text(
        (30, 60),
        f"總盈虧: {analysis.get('profit_loss', 0):+,}  |  總成本: {analysis.get('total_cost', 0):,}",
        font=small_font,
        fill=(77, 91, 133),
    )
    draw.text(
        (30, 84),
        f"當前價值: {analysis.get('total_current_value', 0):,}  |  盈利率: {analysis.get('profit_rate', 0):+.1f}%",
        font=small_font,
        fill=(77, 91, 133),
    )
    draw.text(
        (30, 108),
        f"持倉容量: {current_total_quantity} / {capacity}",
        font=small_font,
        fill=(77, 91, 133),
    )
    draw.line((28, 134, width - 28, 134), fill=(184, 194, 240), width=2)

    y = 146
    for name, qty, cost, value, pnl in rows:
        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 8),
            radius=10,
            fill=(255, 255, 255),
            outline=(221, 226, 247),
        )
        draw.text((36, y + 10), str(name)[:18], font=body_font, fill=(50, 63, 105))
        draw.text((300, y + 10), f"數量: {qty}", font=small_font, fill=(83, 99, 143))
        draw.text((430, y + 10), f"成本: {cost:,}", font=small_font, fill=(83, 99, 143))
        draw.text(
            (620, y + 10), f"價值: {value:,}", font=small_font, fill=(83, 99, 143)
        )
        trend = "📈" if pnl > 0 else ("📉" if pnl < 0 else "➖")
        draw.text(
            (820, y + 10),
            f"盈虧: {pnl:+,} {trend}",
            font=small_font,
            fill=(83, 99, 143),
        )
        y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(184, 194, 240),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 24),
        "💡 快捷：/交易所 買入 [商品] [數量]  |  /交易所 賣出 [商品] [數量]",
        font=small_font,
        fill=(74, 92, 134),
    )
    return image
