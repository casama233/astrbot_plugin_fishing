"""
交易所界面 - 遊戲風格美化版
"""

from typing import Any, Dict, List, Tuple

from datetime import datetime

from PIL import Image, ImageDraw

from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
)
from .styles import load_font


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


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
    n = len(values)
    pad_x = 12
    pad_y = 10
    px0 = x0 + pad_x
    px1 = x1 - pad_x
    py0 = y0 + pad_y
    py1 = y1 - pad_y

    points = []
    for i, v in enumerate(values):
        # 正確計算 X 坐標：將區間分為 (n-1) 等分
        if n == 1:
            x = (px0 + px1) // 2  # 只有一個點時放在中間
        else:
            x = px0 + int((px1 - px0) * i / (n - 1))

        # 計算 Y 坐標
        if mx == mn:
            y = (py0 + py1) // 2
        else:
            y = py1 - int((v - mn) * (py1 - py0) / (mx - mn))
        points.append((x, y))

    # 繪製線條
    if len(points) >= 2:
        draw.line(points, fill=color, width=3)
    elif len(points) == 1:
        # 只有一個點時，畫一個點
        p = points[0]
        draw.ellipse(
            (p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3),
            fill=color,
            outline=GAME_COLORS["text_primary"],
        )
        return

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
        name = info.get("name") or f"商品{cid}"
        desc = info.get("description") or ""
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
    header_h = 140
    row_h = 100
    footer_h = 70
    sentiment_h = 70
    title_font = load_font(36)
    body_font = load_font(22)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    row_h = max(row_h, body_h + 52)
    bottom_pad = 24
    height = header_h + sentiment_h + max(1, len(lines)) * row_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, "交易所行情", title_font, "📈")

    # 更新時間
    draw.text(
        (30, 64),
        f"更新時間: {market_result.get('date', 'N/A')}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    # 下次價格更新時間（如果有）
    next_update = market_result.get("next_price_update")
    if next_update:
        draw.text(
            (320, 64),
            f"下次更新: {next_update}",
            font=small_font,
            fill=GAME_COLORS["text_tertiary"],
        )

    # 市場情緒區塊
    y = header_h + 10
    market_sentiment = market_result.get("market_sentiment", "neutral")
    price_trend = market_result.get("price_trend", "stable")
    supply_demand = market_result.get("supply_demand", "平衡")

    sentiment_emoji = {"bullish": "🚀", "bearish": "🐻", "neutral": "➖"}.get(
        market_sentiment, "➖"
    )
    sentiment_name = {"bullish": "看漲", "bearish": "看跌", "neutral": "中立"}.get(
        market_sentiment, "中立"
    )
    sentiment_color = {
        "bullish": GAME_COLORS["success"],
        "bearish": GAME_COLORS["error"],
        "neutral": GAME_COLORS["text_muted"],
    }.get(market_sentiment, GAME_COLORS["text_muted"])

    trend_emoji = {"up": "📈", "down": "📉", "stable": "➖"}.get(price_trend, "➖")
    trend_name = {"up": "上漲", "down": "下跌", "stable": "平穩"}.get(
        price_trend, "平穩"
    )

    draw.text(
        (40, y + 10),
        f"📊 市場情緒: {sentiment_emoji} {sentiment_name}",
        font=body_font,
        fill=sentiment_color,
    )
    draw.text(
        (340, y + 10),
        f"📈 價格趨勢: {trend_emoji} {trend_name}",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (640, y + 10),
        f"⚖️ 供需狀態: {supply_demand}",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )

    y += sentiment_h + 10

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
    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 10)
    draw.text(
        (30, footer_y + 30),
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
    """我的庫存 - 遊戲風格（包含保質期狀態）"""

    rows = []
    for commodity_id, data in inventory.items():
        name = data.get("name", commodity_id)
        qty = int(data.get("total_quantity", 0) or 0)
        cost = int(data.get("total_cost", 0) or 0)
        price = int(current_prices.get(commodity_id, 0) or 0)

        # 檢查是否有過期商品
        items = data.get("items", [])
        expired_qty = 0
        valid_qty = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            expires_at = _parse_dt(item.get("expires_at"))
            quantity = item.get("quantity", 0)
            if expires_at:
                if expires_at <= datetime.now():
                    expired_qty += quantity
                else:
                    valid_qty += quantity
            else:
                valid_qty += quantity

        # 計算價值（過期商品價值為 0）
        value = valid_qty * price
        pnl = value - cost
        is_all_expired = (expired_qty + valid_qty > 0) and (valid_qty == 0)
        has_expired = expired_qty > 0

        rows.append(
            (
                name,
                qty,
                cost,
                value,
                pnl,
                expired_qty,
                valid_qty,
                is_all_expired,
                has_expired,
            )
        )

    width = 1160
    header_h = 160
    row_h = 60
    footer_h = 70
    title_font = load_font(34)
    body_font = load_font(20)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    row_h = max(row_h, body_h + 36)
    bottom_pad = 24
    height = header_h + max(1, len(rows)) * row_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

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

    for (
        name,
        qty,
        cost,
        value,
        pnl,
        expired_qty,
        valid_qty,
        is_all_expired,
        has_expired,
    ) in rows:
        # 卡片背景
        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h + 10),
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

        # 商品名稱（如果全部過期，添加標記）
        name_display = str(name)[:18]
        if is_all_expired:
            name_display = "💀 " + name_display + " [已腐敗]"
        elif has_expired:
            name_display = "⚠️ " + name_display + f" (過期{expired_qty}個)"

        draw.text(
            (40, y + 15),
            name_display,
            font=body_font,
            fill=GAME_COLORS["text_primary"]
            if not is_all_expired
            else GAME_COLORS["text_muted"],
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
    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 10)
    draw.text(
        (30, footer_y + 25),
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
    title_font = load_font(36)
    sub_font = load_font(16)
    body_font = load_font(18)
    sec_font = load_font(24)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    sec_h = measure.textbbox((0, 0), "測", font=sec_font)[3]
    row_h = max(row_h, body_h + 12)
    sec_title_h = max(sec_title_h, sec_h + 12)
    content_h = 0
    for _, rows in sections:
        content_h += sec_title_h + max(1, len(rows)) * row_h + sec_gap
    bottom_pad = 24
    height = header_h + content_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

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

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 10)
    draw.text(
        (30, footer_y + 28),
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
    """歷史走勢 - 所有商品在同一圖表中"""
    width = 1200
    header_h = 100
    chart_h = 400
    legend_h = 80
    footer_h = 60
    bottom_pad = 20

    title_font = load_font(32)
    body_font = load_font(18)
    small_font = load_font(14)
    legend_font = load_font(16)

    height = header_h + chart_h + legend_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, "交易所歷史走勢", title_font, "📉")

    draw.text(
        (30, 60),
        f"觀測窗口：近 {days} 天",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    if labels:
        draw.text(
            (200, 60),
            f"時間範圍：{labels[0]} → {labels[-1]}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )

    chart_y = header_h + 10
    chart_rect = (40, chart_y, width - 40, chart_y + chart_h - 20)

    draw_game_card(
        draw,
        chart_rect,
        radius=12,
        fill=GAME_COLORS["bg_card"],
        border_color=GAME_COLORS["border"],
    )

    palette = [
        GAME_COLORS["accent_blue"],
        GAME_COLORS["success"],
        GAME_COLORS["accent_red"],
        GAME_COLORS["accent_gold"],
        GAME_COLORS["error"],
        (128, 0, 128),
    ]

    all_values = []
    for values in series_map.values():
        all_values.extend([int(x or 0) for x in (values or [])])

    if not all_values:
        draw.text(
            (width // 2 - 50, chart_y + chart_h // 2),
            "暫無數據",
            font=body_font,
            fill=GAME_COLORS["text_muted"],
        )
    else:
        min_val = min(all_values)
        max_val = max(all_values)
        val_range = max_val - min_val if max_val != min_val else 1

        pad_left = 80
        pad_right = 20
        pad_top = 30
        pad_bottom = 40

        plot_x0 = chart_rect[0] + pad_left
        plot_x1 = chart_rect[2] - pad_right
        plot_y0 = chart_rect[1] + pad_top
        plot_y1 = chart_rect[3] - pad_bottom

        draw.text(
            (plot_x0 - 5, plot_y0 - 20),
            f"價格",
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )
        draw.text(
            (plot_x0 - 10, plot_y0),
            f"{max_val:,}",
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )
        draw.text(
            (plot_x0 - 10, plot_y1 - 15),
            f"{min_val:,}",
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )

        num_points = max(len(v) for v in series_map.values()) if series_map else 0
        if num_points > 1:
            step = (plot_x1 - plot_x0) / (num_points - 1)
        else:
            step = 0

        for i in range(0, num_points, max(1, num_points // 5)):
            x = plot_x0 + i * step
            if i < len(labels):
                draw.text(
                    (x - 20, plot_y1 + 5),
                    labels[i][-5:] if len(labels[i]) > 5 else labels[i],
                    font=small_font,
                    fill=GAME_COLORS["text_muted"],
                )

        draw.line(
            (plot_x0, plot_y1, plot_x1, plot_y1), fill=GAME_COLORS["border"], width=1
        )
        draw.line(
            (plot_x0, plot_y0, plot_x0, plot_y1), fill=GAME_COLORS["border"], width=1
        )

        legend_items = []
        for idx, (cid, values) in enumerate(series_map.items()):
            name = name_map.get(cid) or f"商品{cid}"
            v = [int(x or 0) for x in (values or [])]
            if not v:
                continue

            color = palette[idx % len(palette)]
            points = []
            for i, val in enumerate(v):
                x = plot_x0 + i * step if num_points > 1 else (plot_x0 + plot_x1) // 2
                y = plot_y1 - int((val - min_val) / val_range * (plot_y1 - plot_y0))
                points.append((x, y))

            if len(points) >= 2:
                draw.line(points, fill=color, width=3)
            elif len(points) == 1:
                draw.ellipse(
                    (
                        points[0][0] - 4,
                        points[0][1] - 4,
                        points[0][0] + 4,
                        points[0][1] + 4,
                    ),
                    fill=color,
                )

            start = v[0] if v else 0
            end = v[-1] if v else 0
            change = end - start
            pct = (change / start * 100) if start > 0 else 0.0
            legend_items.append((name, color, start, end, change, pct))

        legend_y = chart_y + chart_h + 10
        cols = 2
        col_width = (width - 80) // cols

        for idx, (name, color, start, end, change, pct) in enumerate(legend_items):
            col = idx % cols
            row = idx // cols
            x = 40 + col * col_width
            y = legend_y + row * 35

            draw.ellipse((x, y + 5, x + 14, y + 19), fill=color)

            trend = "📈" if change > 0 else ("📉" if change < 0 else "➖")
            trend_color = (
                GAME_COLORS["success"]
                if change > 0
                else (GAME_COLORS["error"] if change < 0 else GAME_COLORS["text_muted"])
            )

            draw.text(
                (x + 20, y),
                f"{name}",
                font=legend_font,
                fill=GAME_COLORS["text_primary"],
            )
            draw.text(
                (x + 120, y),
                f"{trend} {change:+,} ({pct:+.1f}%)",
                font=small_font,
                fill=trend_color,
            )

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 5)
    draw.text(
        (30, footer_y + 18),
        "💡 指令：/交易所 歷史 [商品] [天數]（1-30）| 數值越低線條越靠下",
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
    title_font = load_font(36)
    body_font = load_font(18)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    small_h = measure.textbbox((0, 0), "測", font=small_font)[3]
    row_h = max(row_h, body_h + small_h + 40)
    bottom_pad = 24
    height = header_h + max(1, len(rows)) * row_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

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
    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 10)
    draw.text(
        (30, footer_y + 28),
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
    safety_margin = 50  # 添加安全邊距

    title_font = load_font(32)
    body_font = load_font(18)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    row_h = max(row_h, body_h + 12)
    bottom_pad = 20

    # 計算實際需要的行數（考慮換行符）
    total_lines = 0
    for line in lines:
        # 計算每行文字因為換行符產生的實際行數
        line_count = line.count("\n") + 1
        total_lines += line_count

    # 使用實際行數計算高度，並添加安全邊距
    calculated_height = header_h + max(2, total_lines) * row_h + footer_h + bottom_pad
    height = calculated_height + safety_margin

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    tag = "✅" if success else "❌"
    color = GAME_COLORS["success"] if success else GAME_COLORS["error"]

    # 標題欄
    draw_game_title_bar(draw, width, 0, header_h, title, title_font, tag)

    # 分隔線
    draw.line((30, 80, width - 30, 80), fill=color, width=2)

    y = 100
    for line in lines:
        # 處理多行文字（按換行符分割）
        sub_lines = line.split("\n")
        for sub_line in sub_lines:
            draw.text(
                (45, y),
                f"• {sub_line}",
                font=body_font,
                fill=GAME_COLORS["text_secondary"],
            )
            y += row_h

    return image


def draw_exchange_stats_image(
    total_quantity: int,
    total_cost: int,
    total_value: int,
    profit_loss: int,
    profit_rate: float,
    commodity_details: List[Dict[str, Any]],
    commodities_info: Dict[str, Any],
) -> Image.Image:
    """交易統計 - 遊戲風格"""
    width = 1200
    header_h = 160
    row_h = 70
    footer_h = 70
    title_font = load_font(34)
    body_font = load_font(20)
    small_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_h = measure.textbbox((0, 0), "測", font=body_font)[3]
    row_h = max(row_h, body_h + 40)
    bottom_pad = 24
    height = header_h + max(1, len(commodity_details)) * row_h + footer_h + bottom_pad

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    draw_game_title_bar(draw, width, 0, header_h, "我的交易統計", title_font, "📊")

    is_profit = profit_loss >= 0
    pnl_color = GAME_COLORS["success"] if is_profit else GAME_COLORS["error"]
    pnl_icon = "📈" if is_profit else "📉"

    draw.text(
        (30, 65),
        f"📦 總持倉: {total_quantity}個  |  💰 總成本: {total_cost:,} 金幣",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    draw.text(
        (30, 90),
        f"💎 當前價值: {total_value:,} 金幣  |  {pnl_icon} 盈虧: {profit_loss:+,} ({profit_rate:+.1f}%)",
        font=small_font,
        fill=pnl_color,
    )

    draw.text(
        (30, 118),
        "─" * 50,
        font=small_font,
        fill=GAME_COLORS["border"],
    )

    y = header_h + 10

    draw.text((40, y - 25), "商品", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((200, y - 25), "數量", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((300, y - 25), "成本", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((450, y - 25), "價值", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((600, y - 25), "盈虧", font=small_font, fill=GAME_COLORS["text_muted"])
    draw.text((800, y - 25), "狀態", font=small_font, fill=GAME_COLORS["text_muted"])

    for detail in commodity_details:
        name = detail["name"]
        qty = detail["quantity"]
        cost = detail["cost"]
        value = detail["value"]
        pnl = detail["pnl"]
        pnl_pct = detail["pnl_pct"]
        expired = detail["expired"]
        expiring = detail["expiring_soon"]

        draw_game_card(
            draw,
            (20, y, width - 20, y + row_h),
            radius=10,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
        )

        draw.text(
            (40, y + 15),
            str(name)[:10],
            font=body_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text(
            (200, y + 15),
            f"{qty}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text(
            (300, y + 15),
            f"{cost:,}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        draw.text(
            (450, y + 15),
            f"{value:,}",
            font=small_font,
            fill=GAME_COLORS["accent_gold"],
        )

        item_pnl_color = GAME_COLORS["success"] if pnl >= 0 else GAME_COLORS["error"]
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        draw.text(
            (600, y + 15),
            f"{pnl_emoji} {pnl:+,} ({pnl_pct:+.1f}%)",
            font=small_font,
            fill=item_pnl_color,
        )

        status_text = ""
        status_color = GAME_COLORS["text_secondary"]
        if expired > 0:
            status_text = f"💀 過期{expired}個"
            status_color = GAME_COLORS["error"]
        elif expiring > 0:
            status_text = f"⚠️ 將過期{expiring}個"
            status_color = (
                GAME_COLORS["warning"]
                if "warning" in GAME_COLORS
                else GAME_COLORS["accent_gold"]
            )
        else:
            status_text = "✅ 正常"

        draw.text(
            (800, y + 15),
            status_text,
            font=small_font,
            fill=status_color,
        )

        y += row_h

    footer_y = height - footer_h - bottom_pad
    draw_game_divider(draw, 30, width - 30, footer_y + 10)
    draw.text(
        (30, footer_y + 25),
        "💡 查詳情：/持倉 | 看分析：/交易所 分析",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
