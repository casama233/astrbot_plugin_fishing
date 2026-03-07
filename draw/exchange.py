"""
交易所界面 - 遊戲風格美化版
"""

from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw

from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
)
from .styles import load_font


def _line_chart(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    values: List[int],
    color: Tuple[int, int, int],
) -> None:
    """繪製迷你走勢圖"""
    x0, y0, x1, y1 = rect

    # 圖表背景卡片
    draw.rounded_rectangle(
        rect, radius=8, fill=GAME_COLORS["bg_light"], outline=GAME_COLORS["border"]
    )

    if not values:
        draw.text(
            (x0 + 10, y0 + 8),
            "無資料",
            font=load_font(14),
            fill=GAME_COLORS["text_muted"],
        )
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

    # 繪製線條
    if len(points) >= 2:
        draw.line(points, fill=color, width=3)

    # 繪製端點
    for p in points[-2:]:
        draw.ellipse(
            (p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3),
            fill=color,
            outline=GAME_COLORS["text_primary"],
        )

    # 價格範圍
    draw.text(
        (x0 + 8, y1 - 20),
        f"{mn:,} ~ {mx:,}",
        font=load_font(13),
        fill=GAME_COLORS["text_secondary"],
    )


def draw_exchange_status_image(
    market_result: Dict[str, Any],
    previous_prices: Dict[str, int],
    recent_history: Dict[str, List[int]] | None = None,
) -> Image.Image:
    """交易所行情 - 遊戲風格"""
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
                trend_color = GAME_COLORS["success"]
            elif change < 0:
                trend = f"📉 {change:,} ({pct:+.1f}%)"
                trend_color = GAME_COLORS["error"]
            else:
                trend = "➖ 0 (0.0%)"
                trend_color = GAME_COLORS["text_muted"]
        else:
            trend = "🆕 新價格"
            trend_color = GAME_COLORS["accent_blue"]

        series = []
        if recent_history:
            series = [int(x or 0) for x in (recent_history.get(cid) or [])]
        lines.append((name, int(price), trend, str(desc), series, trend_color))

    width = 1200
    header_h = 100
    row_h = 100
    footer_h = 70
    height = header_h + max(1, len(lines)) * row_h + footer_h

    # 遊戲風格深色背景
    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(36)
    body_font = load_font(22)
    small_font = load_font(16)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "交易所行情", title_font, "📈")

    # 更新時間
    draw.text(
        (30, 64),
        f"更新時間: {market_result.get('date', 'N/A')}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    y = header_h + 10

    for name, price, trend, desc, series, trend_color in lines:
        # 商品卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h - 10),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
            shadow=True,
        )

        # 商品名稱
        draw.text(
            (40, y + 12), f"📦 {name}", font=body_font, fill=GAME_COLORS["text_primary"]
        )

        # 價格
        draw.text(
            (280, y + 12),
            f"{price:,} 金幣",
            font=body_font,
            fill=GAME_COLORS["accent_gold"],
        )

        # 漲跌趨勢
        draw.text((480, y + 12), trend, font=small_font, fill=trend_color)

        # 描述
        if desc:
            draw.text(
                (40, y + 45),
                desc[:60],
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

        # 走勢圖
        _line_chart(
            draw,
            (850, y + 8, width - 35, y + row_h - 18),
            series,
            trend_color
            if trend_color != GAME_COLORS["text_muted"]
            else GAME_COLORS["accent_blue"],
        )

        y += row_h

    # 底部提示
    draw_game_divider(draw, 30, width - 30, height - footer_h + 10)
    draw.text(
        (30, height - footer_h + 30),
        "💡 交易指令：/交易所 買入 [商品] [數量]  |  /交易所 賣出 [商品] [數量]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_exchange_inventory_image(
    inventory: Dict[str, Any],
    current_prices: Dict[str, int],
    analysis: Dict[str, Any],
    capacity: int,
    current_total_quantity: int,
) -> Image.Image:
    """我的庫存 - 遊戲風格"""
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
    header_h = 160
    row_h = 60
    footer_h = 70
    height = header_h + max(1, len(rows)) * row_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(34)
    body_font = load_font(20)
    small_font = load_font(16)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "我的交易所庫存", title_font, "📦")

    # 統計資訊
    pnl_total = analysis.get("profit_loss", 0)
    pnl_color = GAME_COLORS["success"] if pnl_total >= 0 else GAME_COLORS["error"]

    draw.text(
        (30, 70),
        f"總盈虧: ",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (95, 70),
        f"{pnl_total:+,}",
        font=small_font,
        fill=pnl_color,
    )

    draw.text(
        (200, 70),
        f"總成本: {analysis.get('total_cost', 0):,}  |  當前價值: {analysis.get('total_current_value', 0):,}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    draw.text(
        (30, 95),
        f"盈利率: {analysis.get('profit_rate', 0):+.1f}%  |  持倉容量: {current_total_quantity} / {capacity}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    y = header_h + 10

    # 表頭
    draw.text((40, y - 25), "商品名稱", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((320, y - 25), "數量", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((450, y - 25), "成本", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((620, y - 25), "價值", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((800, y - 25), "盈虧", font=small_font, fill=GAME_COLORS["text_muted"])

    for name, qty, cost, value, pnl in rows:
        # 卡片背景
        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h - 8),
            radius=10,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        trend = "📈" if pnl > 0 else ("📉" if pnl < 0 else "➖")
        pnl_color = (
            GAME_COLORS["success"]
            if pnl > 0
            else (GAME_COLORS["error"] if pnl < 0 else GAME_COLORS["text_muted"])
        )

        draw.text(
            (40, y + 15),
            str(name)[:18],
            font=body_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text(
            (320, y + 15), f"{qty}", font=small_font, fill=GAME_COLORS["text_secondary"]
        )
        draw.text(
            (450, y + 15),
            f"{cost:,}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text(
            (620, y + 15),
            f"{value:,}",
            font=small_font,
            fill=GAME_COLORS["accent_gold"],
        )
        draw.text(
            (800, y + 15),
            f"{pnl:+,} {trend}",
            font=small_font,
            fill=pnl_color,
        )

        y += row_h

    # 底部
    draw_game_divider(draw, 30, width - 30, height - footer_h + 10)
    draw.text(
        (30, height - footer_h + 25),
        "💡 快捷指令：/交易所 買入 [商品] [數量]  |  /交易所 賣出 [商品] [數量]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_exchange_help_image(
    sections: List[Tuple[str, List[str]]],
    schedule_text: str,
    tax_rate_text: str,
    capacity_text: str,
) -> Image.Image:
    """指令總覽 - 遊戲風格"""
    width = 1220
    header_h = 120
    sec_title_h = 40
    row_h = 32
    sec_gap = 16
    footer_h = 80

    content_h = 0
    for _, rows in sections:
        content_h += sec_title_h + max(1, len(rows)) * row_h + sec_gap
    height = header_h + content_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(36)
    sub_font = load_font(16)
    body_font = load_font(18)
    sec_font = load_font(24)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "交易所指令總覽", title_font, "📈")

    draw.text(
        (30, 70),
        f"更新時段: {schedule_text}   |   盈利稅: {tax_rate_text}   |   容量: {capacity_text}",
        font=sub_font,
        fill=GAME_COLORS["text_secondary"],
    )

    y = header_h + 15

    for sec_name, rows in sections:
        # 分類標題卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + sec_title_h),
            radius=8,
            fill=GAME_COLORS["bg_light"],
            border_color=GAME_COLORS["border_highlight"],
        )
        draw.text(
            (40, y + 8), f"▸ {sec_name}", font=sec_font, fill=GAME_COLORS["accent_blue"]
        )

        y += sec_title_h + 8

        for row in rows:
            draw.text(
                (50, y + 5),
                f"• {row}",
                font=body_font,
                fill=GAME_COLORS["text_secondary"],
            )
            y += row_h

        y += sec_gap

    # 底部
    draw_game_divider(draw, 30, width - 30, height - footer_h + 10)
    draw.text(
        (30, height - footer_h + 28),
        "💡 查行情：/交易所   💡 看持倉：/持倉",
        font=sub_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_exchange_history_image(
    labels: List[str],
    series_map: Dict[str, List[int]],
    name_map: Dict[str, str],
    days: int,
) -> Image.Image:
    """歷史走勢 - 遊戲風格"""
    width = 1240
    header_h = 120
    card_h = 150
    gap = 16
    footer_h = 75
    count = max(1, len(series_map))
    height = header_h + count * (card_h + gap) + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(36)
    body_font = load_font(18)
    small_font = load_font(16)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "交易所歷史走勢", title_font, "📉")

    draw.text(
        (30, 70),
        f"觀測窗口：近 {days} 天",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    if labels:
        draw.text(
            (30, 92),
            f"時間點：{labels[0]}  →  {labels[-1]}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

    y = header_h + 15
    palette = [
        GAME_COLORS["accent_blue"],
        GAME_COLORS["success"],
        GAME_COLORS["accent_red"],
        GAME_COLORS["accent_gold"],
    ]

    for idx, (cid, values) in enumerate(series_map.items()):
        name = name_map.get(cid, cid)
        v = [int(x or 0) for x in (values or [])]
        start = v[0] if v else 0
        end = v[-1] if v else 0
        change = end - start
        pct = (change / start * 100) if start > 0 else 0.0
        trend = "📈" if change > 0 else ("📉" if change < 0 else "➖")
        trend_color = (
            GAME_COLORS["success"]
            if change > 0
            else (GAME_COLORS["error"] if change < 0 else GAME_COLORS["text_muted"])
        )

        # 卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + card_h),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        # 商品名和趨勢
        draw.text(
            (40, y + 15),
            f"{name}  {trend} {change:+,} ({pct:+.1f}%)",
            font=body_font,
            fill=trend_color,
        )

        # 起始/最新價格
        draw.text(
            (45, y + 45),
            f"起始: {start:,}    最新: {end:,}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

        # 走勢圖
        _line_chart(
            draw,
            (320, y + 20, width - 35, y + card_h - 20),
            v,
            palette[idx % len(palette)],
        )

        y += card_h + gap

    # 底部
    draw_game_divider(draw, 30, width - 30, height - footer_h + 10)
    draw.text(
        (30, height - footer_h + 28),
        "💡 指令：/交易所 歷史 [商品] [天數]（1-30）",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_exchange_analysis_image(rows: List[Dict[str, Any]], days: int) -> Image.Image:
    """市場分析 - 遊戲風格"""
    width = 1260
    header_h = 120
    row_h = 120
    footer_h = 75
    height = header_h + max(1, len(rows)) * row_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(36)
    body_font = load_font(18)
    small_font = load_font(16)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "交易所市場分析", title_font, "📊")

    draw.text(
        (30, 70),
        f"分析窗口：近 {days} 天（MA / RSI / 波動率）",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    y = header_h + 15

    for row in rows:
        # 卡片
        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h - 10),
            radius=12,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        # 商品名和當前價
        draw.text(
            (40, y + 12),
            f"📦 {row.get('name', '未知商品')}  |  當前: {int(row.get('last', 0)):,}",
            font=body_font,
            fill=GAME_COLORS["text_primary"],
        )

        # 技術指標
        draw.text(
            (40, y + 42),
            f"MA3 {row.get('ma3', 0):.0f}  MA5 {row.get('ma5', 0):.0f}  MA7 {row.get('ma7', 0):.0f}  RSI {row.get('rsi', 0):.0f}  波動 {row.get('vol', 0):.1f}%",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

        # 趨勢和建議
        suggestion = row.get("suggestion", "觀望")
        suggestion_color = GAME_COLORS["accent_gold"]
        if "買入" in suggestion or "買" in suggestion:
            suggestion_color = GAME_COLORS["success"]
        elif "賣出" in suggestion or "賣" in suggestion:
            suggestion_color = GAME_COLORS["error"]

        draw.text(
            (40, y + 68),
            f"趨勢: {row.get('trend', 'stable')}  |  建議: {suggestion}",
            font=small_font,
            fill=suggestion_color,
        )

        # 走勢圖
        _line_chart(
            draw,
            (880, y + 12, width - 35, y + row_h - 22),
            [int(x or 0) for x in row.get("series", [])],
            GAME_COLORS["accent_blue"],
        )

        y += row_h

    # 底部
    draw_game_divider(draw, 30, width - 30, height - footer_h + 10)
    draw.text(
        (30, height - footer_h + 28),
        "💡 指令：/交易所 分析 [商品] [天數]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_exchange_result_image(
    title: str, lines: List[str], success: bool = True
) -> Image.Image:
    """交易結果 - 遊戲風格"""
    width = 920
    header_h = 100
    row_h = 36
    footer_h = 60
    height = header_h + max(2, len(lines)) * row_h + footer_h

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(32)
    body_font = load_font(18)

    tag = "✅" if success else "❌"
    color = GAME_COLORS["success"] if success else GAME_COLORS["error"]

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, title, title_font, tag)

    # 分隔線
    draw.line((30, 80, width - 30, 80), fill=color, width=2)

    y = 100
    for line in lines:
        draw.text(
            (45, y), f"• {line}", font=body_font, fill=GAME_COLORS["text_secondary"]
        )
        y += row_h

    return image
