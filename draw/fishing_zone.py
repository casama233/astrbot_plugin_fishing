from datetime import datetime
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from .game_ui import (
    GAME_COLORS,
    create_game_gradient,
    draw_game_card,
    draw_game_divider,
    draw_game_title_bar,
)
from .styles import load_font


def _fmt_time(dt: Any) -> str:
    if not dt:
        return "-"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)


def _build_zone_badges(zone: Dict[str, Any]) -> str:
    badges: List[str] = []
    if zone.get("whether_in_use"):
        badges.append("✅ 當前")
    if zone.get("requires_pass"):
        badges.append("需通行證")
    if not zone.get("is_active", True):
        badges.append("未開放")
    return " · ".join(badges) if badges else "可用"


def draw_fishing_zones_image(
    zones: List[Dict[str, Any]], nickname: str = ""
) -> Image.Image:
    width = 940
    header_h = 106
    footer_h = 78
    section_gap = 14
    card_h = 154

    if not zones:
        zones = []

    height = header_h + 24 + (len(zones) * (card_h + section_gap)) + footer_h + 24
    height = max(height, 320)

    image = create_game_gradient(width, height)
    draw = ImageDraw.Draw(image)

    title_font = load_font(33)
    section_font = load_font(20)
    body_font = load_font(17)
    small_font = load_font(14)

    title = "釣魚區域"
    if nickname:
        title = f"{nickname} 的釣魚區域"
    draw_game_title_bar(draw, width, 0, header_h, title, title_font, "🌊")

    y = header_h + 18
    for idx, zone in enumerate(zones):
        z_id = zone.get("zone_id", "?")
        name = zone.get("name", "未知區域")
        desc = zone.get("description", "") or ""
        fishing_cost = int(zone.get("fishing_cost", 10) or 10)
        remaining_rare = max(
            0,
            int(zone.get("daily_rare_fish_quota", 0) or 0)
            - int(zone.get("rare_fish_caught_today", 0) or 0),
        )

        card_fill = GAME_COLORS["bg_card"]
        border = GAME_COLORS["border"]
        if zone.get("whether_in_use"):
            card_fill = (46, 64, 92)
            border = GAME_COLORS["border_highlight"]

        draw_game_card(
            draw,
            (22, y, width - 22, y + card_h),
            radius=12,
            fill=card_fill,
            border_color=border,
        )

        badge = _build_zone_badges(zone)
        draw.text(
            (38, y + 12),
            f"ID {z_id} · {name}",
            font=section_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text(
            (width - 280, y + 15),
            badge,
            font=small_font,
            fill=GAME_COLORS["accent_gold"],
        )

        if desc:
            draw.text(
                (38, y + 44),
                desc[:58],
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

        draw.text(
            (38, y + 72),
            f"💰 消耗: {fishing_cost} 金幣/次",
            font=body_font,
            fill=GAME_COLORS["accent_gold"],
        )

        if zone.get("daily_rare_fish_quota", 0):
            draw.text(
                (322, y + 72),
                f"🐟 稀有額度剩餘: {remaining_rare}",
                font=body_font,
                fill=GAME_COLORS["accent_blue"],
            )

        if zone.get("requires_pass"):
            required_item = zone.get("required_item_name") or "通行證"
            draw.text(
                (38, y + 104),
                f"🔑 進入需求: {required_item}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

        if zone.get("available_from") or zone.get("available_until"):
            draw.text(
                (360, y + 104),
                f"⏰ 開放: {_fmt_time(zone.get('available_from'))} ~ {_fmt_time(zone.get('available_until'))}",
                font=small_font,
                fill=GAME_COLORS["text_secondary"],
            )

        y += card_h + section_gap

    draw_game_divider(draw, 30, width - 30, height - footer_h)
    draw.text(
        (30, height - footer_h + 18),
        "💡 切換區域: /釣魚區域 ID   例如: /釣魚區域 3",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
