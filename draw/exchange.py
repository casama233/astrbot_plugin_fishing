from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw

from .gradient_utils import create_vertical_gradient
from .styles import load_font


def _line_chart(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    values: List[int],
    color: Tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(
        rect, radius=8, fill=(250, 252, 255), outline=(218, 228, 240)
    )
    if not values:
        draw.text((x0 + 10, y0 + 8), "無資料", font=load_font(14), fill=(135, 150, 168))
        return

    mn = min(values)
    mx = max(values)
    n = max(1, len(values) - 1)
    pad_x = 12
    pad_y = 10
    px0 = x0 + pad_x
    px1 = x1 - pad_x
    py0 = y0 + pad_y
    py1 = y1 - pad_y

    points = []
    for i, v in enumerate(values):
        x = px0 + int((px1 - px0) * (i / n if n else 0))
        if mx == mn:
            y = (py0 + py1) // 2
        else:
            y = py1 - int((v - mn) / (mx - mn) * (py1 - py0))
        points.append((x, y))

    if len(points) >= 2:
        draw.line(points, fill=color, width=3)
    for p in points[-2:]:
        draw.ellipse((p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2), fill=color)

    draw.text(
        (x0 + 8, y1 - 18), f"{mn:,} ~ {mx:,}", font=load_font(13), fill=(111, 129, 147)
    )


def draw_exchange_status_image(
    market_result: Dict[str, Any],
    previous_prices: Dict[str, int],
    recent_history: Dict[str, List[int]] | None = None,
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
        series = []
        if recent_history:
            series = [int(x or 0) for x in (recent_history.get(cid) or [])]
        lines.append((name, int(price), trend, str(desc), series))

    width = 1200
    header_h = 120
    row_h = 94
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
    for name, price, trend, desc, series in lines:
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
        _line_chart(
            draw, (870, y + 8, width - 40, y + row_h - 14), series, (82, 130, 188)
        )
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


def draw_exchange_help_image(
    sections: List[Tuple[str, List[str]]],
    schedule_text: str,
    tax_rate_text: str,
    capacity_text: str,
) -> Image.Image:
    width = 1220
    header_h = 120
    sec_title_h = 34
    row_h = 30
    sec_gap = 14
    footer_h = 80

    content_h = 0
    for _, rows in sections:
        content_h += sec_title_h + max(1, len(rows)) * row_h + sec_gap
    height = header_h + content_h + footer_h

    image = create_vertical_gradient(width, height, (238, 248, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(34)
    sub_font = load_font(16)
    body_font = load_font(18)
    sec_font = load_font(22)

    draw.text((28, 22), "📈 交易所指令總覽", font=title_font, fill=(40, 66, 94))
    draw.text(
        (30, 66),
        f"更新時段: {schedule_text}   |   盈利稅: {tax_rate_text}   |   容量: {capacity_text}",
        font=sub_font,
        fill=(70, 95, 118),
    )
    draw.line((28, 94, width - 28, 94), fill=(176, 204, 229), width=2)

    y = 110
    for sec_name, rows in sections:
        draw.rounded_rectangle(
            (24, y, width - 24, y + sec_title_h),
            radius=10,
            fill=(248, 252, 255),
            outline=(208, 224, 238),
        )
        draw.text((36, y + 6), sec_name, font=sec_font, fill=(49, 75, 102))
        y += sec_title_h + 4
        for row in rows:
            draw.text((42, y + 4), f"• {row}", font=body_font, fill=(66, 90, 118))
            y += row_h
        y += sec_gap

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 24),
        "💡 查行情：/交易所   💡 看持倉：/持倉",
        font=sub_font,
        fill=(63, 89, 112),
    )
    return image


def draw_exchange_history_image(
    labels: List[str],
    series_map: Dict[str, List[int]],
    name_map: Dict[str, str],
    days: int,
) -> Image.Image:
    width = 1240
    header_h = 120
    card_h = 138
    gap = 14
    footer_h = 72
    count = max(1, len(series_map))
    height = header_h + count * (card_h + gap) + footer_h

    image = create_vertical_gradient(width, height, (241, 249, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(33)
    body_font = load_font(18)
    small_font = load_font(15)

    draw.text((28, 20), "📉 交易所歷史走勢", font=title_font, fill=(40, 66, 94))
    draw.text((30, 62), f"觀測窗口：近 {days} 天", font=small_font, fill=(74, 95, 118))
    if labels:
        draw.text(
            (30, 84),
            f"時間點：{labels[0]}  →  {labels[-1]}",
            font=small_font,
            fill=(74, 95, 118),
        )

    y = header_h
    palette = [(66, 129, 185), (56, 158, 132), (198, 110, 86), (128, 121, 184)]
    for idx, (cid, values) in enumerate(series_map.items()):
        name = name_map.get(cid, cid)
        v = [int(x or 0) for x in (values or [])]
        start = v[0] if v else 0
        end = v[-1] if v else 0
        change = end - start
        pct = (change / start * 100) if start > 0 else 0.0
        trend = "📈" if change > 0 else ("📉" if change < 0 else "➖")

        draw.rounded_rectangle(
            (24, y, width - 24, y + card_h),
            radius=12,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw.text(
            (38, y + 12),
            f"{name}  {trend} {change:+,} ({pct:+.1f}%)",
            font=body_font,
            fill=(44, 67, 97),
        )
        draw.text(
            (40, y + 40),
            f"起始: {start:,}    最新: {end:,}",
            font=small_font,
            fill=(95, 114, 133),
        )
        _line_chart(
            draw,
            (300, y + 16, width - 42, y + card_h - 16),
            v,
            palette[idx % len(palette)],
        )
        y += card_h + gap

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 24),
        "💡 指令：/交易所 歷史 [商品] [天數]（1-30）",
        font=small_font,
        fill=(63, 89, 112),
    )
    return image


def draw_exchange_analysis_image(rows: List[Dict[str, Any]], days: int) -> Image.Image:
    width = 1260
    header_h = 118
    row_h = 114
    footer_h = 70
    height = header_h + max(1, len(rows)) * row_h + footer_h

    image = create_vertical_gradient(width, height, (239, 247, 255), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(33)
    body_font = load_font(18)
    small_font = load_font(15)

    draw.text((28, 22), "📊 交易所市場分析", font=title_font, fill=(40, 66, 94))
    draw.text(
        (30, 66),
        f"分析窗口：近 {days} 天（MA / RSI / 波動率）",
        font=small_font,
        fill=(74, 95, 118),
    )
    draw.line((28, 92, width - 28, 92), fill=(176, 204, 229), width=2)

    y = 106
    for row in rows:
        draw.rounded_rectangle(
            (24, y, width - 24, y + row_h - 8),
            radius=12,
            fill=(255, 255, 255),
            outline=(214, 228, 240),
        )
        draw.text(
            (36, y + 10),
            f"{row.get('name', '未知商品')}  |  當前: {int(row.get('last', 0)):,}",
            font=body_font,
            fill=(44, 67, 97),
        )
        draw.text(
            (36, y + 40),
            f"MA3 {row.get('ma3', 0):.0f}  MA5 {row.get('ma5', 0):.0f}  MA7 {row.get('ma7', 0):.0f}  RSI {row.get('rsi', 0):.0f}  波動 {row.get('vol', 0):.1f}%",
            font=small_font,
            fill=(86, 106, 126),
        )
        draw.text(
            (36, y + 66),
            f"趨勢: {row.get('trend', 'stable')}  建議: {row.get('suggestion', '觀望')}",
            font=small_font,
            fill=(86, 106, 126),
        )
        _line_chart(
            draw,
            (860, y + 10, width - 40, y + row_h - 18),
            [int(x or 0) for x in row.get("series", [])],
            (72, 126, 182),
        )
        y += row_h

    draw.line(
        (28, height - footer_h, width - 28, height - footer_h),
        fill=(176, 204, 229),
        width=2,
    )
    draw.text(
        (30, height - footer_h + 22),
        "💡 指令：/交易所 分析 [商品] [天數]",
        font=small_font,
        fill=(63, 89, 112),
    )
    return image


def draw_exchange_result_image(
    title: str, lines: List[str], success: bool = True
) -> Image.Image:
    width = 920
    header_h = 96
    row_h = 34
    footer_h = 56
    height = header_h + max(2, len(lines)) * row_h + footer_h
    top = (236, 250, 242) if success else (255, 244, 244)
    image = create_vertical_gradient(width, height, top, (255, 255, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(30)
    body_font = load_font(18)
    tag = "✅" if success else "❌"
    color = (40, 110, 78) if success else (136, 63, 63)
    draw.text((26, 22), f"{tag} {title}", font=title_font, fill=color)
    draw.line(
        (24, 76, width - 24, 76),
        fill=(206, 223, 214) if success else (235, 214, 214),
        width=2,
    )

    y = 90
    for line in lines:
        draw.text((34, y), f"• {line}", font=body_font, fill=(71, 88, 104))
        y += row_h
    return image
