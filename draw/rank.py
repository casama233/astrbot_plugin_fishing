import os

from PIL import Image, ImageDraw
from typing import List, Dict
from astrbot.api import logger
from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
)
from .styles import load_font


def get_text_metrics(text, font, draw):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    return bbox, (text_width, text_height)


def format_large_number(number):
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return f"{number / 1000:.1f}K".replace(".0K", "K")
    elif number < 1000000000:
        return f"{number / 1000000:.1f}M".replace(".0M", "M")
    else:
        return f"{number / 1000000000:.1f}B".replace(".0B", "B")


def format_weight(grams):
    if grams < 1000:
        return f"{grams}g"

    kg = grams / 1000

    if kg < 1000:
        return f"{kg:.1f}kg".replace(".0kg", "kg")
    elif kg < 1000000:
        return f"{kg / 1000:.1f}Kkg".replace(".0Kkg", "Kkg")
    elif kg < 1000000000:
        return f"{kg / 1000000:.1f}Mkg".replace(".0Mkg", "Mkg")
    else:
        return f"{kg / 1000000000:.1f}Bkg".replace(".0Bkg", "Bkg")


def draw_fishing_ranking(
    user_data: List[Dict], output_path: str, ranking_type: str = "coins"
):
    width = 850
    header_h = 80
    card_h = 75
    card_margin = 10
    footer_h = 50
    padding = 25

    top_users = user_data[:10] if len(user_data) > 10 else user_data

    calculated_height = (
        header_h + (card_h + card_margin) * len(top_users) + footer_h + padding * 3 + 30
    )

    image = create_game_gradient(width, calculated_height)
    draw = ImageDraw.Draw(image)

    try:
        title_font = load_font(32)
        rank_font = load_font(28)
        name_font = load_font(20)
        regular_font = load_font(16)
        small_font = load_font(14)
    except IOError:
        logger.warning("字体加载失败，使用默认字体")
        title_font = rank_font = name_font = regular_font = small_font = None

    title_text = "钓鱼排行榜 TOP10"
    if ranking_type == "max_coins":
        title_text = "金币历史最高 TOP10"
    elif ranking_type == "fish_count":
        title_text = "钓获数量排行榜 TOP10"
    elif ranking_type == "total_weight_caught":
        title_text = "钓获重量排行榜 TOP10"

    draw_game_title_bar(draw, width, 0, header_h, title_text, title_font, "🏆")

    rank_colors = [
        GAME_COLORS["accent_gold"],
        (192, 192, 192),
        (205, 127, 50),
    ]

    trophy_symbols = []
    try:
        gold_trophy = Image.open(
            os.path.join(os.path.dirname(__file__), "resource", "gold.png")
        ).resize((36, 36))
        silver_trophy = Image.open(
            os.path.join(os.path.dirname(__file__), "resource", "silver.png")
        ).resize((32, 32))
        bronze_trophy = Image.open(
            os.path.join(os.path.dirname(__file__), "resource", "bronze.png")
        ).resize((32, 32))
        trophy_symbols = [gold_trophy, silver_trophy, bronze_trophy]
    except Exception as e:
        logger.warning(f"加载奖杯图片失败: {e}")
        trophy_symbols = []

    current_y = header_h + 15

    for idx, user in enumerate(top_users):
        nickname = user.get("nickname", "未知用户")
        title_info = user.get("title_info")
        coins = user.get("coins", 0)
        max_coins = user.get("max_coins", 0)
        fish_count = user.get("fish_count", 0)
        fishing_rod = user.get("fishing_rod", "普通鱼竿")
        accessory = user.get("accessory", "无饰品")
        total_weight = user.get("total_weight_caught", 0)

        card_y1 = current_y
        card_y2 = card_y1 + card_h

        if idx < 3:
            card_color = (
                rank_colors[idx][0] // 4 + 20,
                rank_colors[idx][1] // 4 + 20,
                rank_colors[idx][2] // 4 + 20,
            )
            border_color = rank_colors[idx]
        else:
            card_color = GAME_COLORS["bg_card"]
            border_color = GAME_COLORS["border"]

        draw_game_card(
            draw,
            (padding, card_y1, width - padding, card_y2),
            radius=10,
            fill=card_color,
            border_color=border_color,
            border_width=2,
        )

        rank_x = padding + 15
        if idx < 3 and len(trophy_symbols) > idx:
            trophy_img = trophy_symbols[idx]
            trophy_y = card_y1 + (card_h - trophy_img.height) // 2
            image.paste(
                trophy_img,
                (rank_x, trophy_y),
                trophy_img if trophy_img.mode == "RGBA" else None,
            )
        else:
            rank_text = f"#{idx + 1}"
            rank_color = GAME_COLORS["text_muted"]
            rank_y = (
                card_y1
                + (card_h - get_text_metrics(rank_text, rank_font, draw)[1][1]) // 2
            )
            draw.text((rank_x, rank_y), rank_text, font=rank_font, fill=rank_color)

        name_x = padding + 60
        name_y = card_y1 + 12

        from ..core.utils import format_user_display_name

        display_name = format_user_display_name(nickname, title_info)

        if len(display_name) > 18:
            display_name = display_name[:16] + "..."
        draw.text(
            (name_x, name_y),
            display_name,
            font=name_font,
            fill=GAME_COLORS["text_primary"],
        )

        info_y = name_y + get_text_metrics(display_name, name_font, draw)[1][1] + 8

        weight_str = format_weight(total_weight)
        fish_text = f"钓获: {format_large_number(fish_count)}条 ({weight_str})"
        draw.text(
            (name_x, info_y),
            fish_text,
            font=regular_font,
            fill=GAME_COLORS["text_secondary"],
        )

        card_center = width // 2

        if ranking_type == "max_coins":
            max_str = format_large_number(max_coins)
            curr_str = format_large_number(coins)
            coins_text = f"最高:{max_str} 当前:{curr_str}"
            coins_font = small_font
        else:
            coins_text = f"金币: {format_large_number(coins)}"
            coins_font = regular_font

        coins_x = card_center - 60
        draw.text(
            (coins_x, info_y),
            coins_text,
            font=coins_font,
            fill=GAME_COLORS["accent_gold"],
        )

        rod_display = fishing_rod if len(fishing_rod) <= 6 else fishing_rod[:5] + ".."
        acc_display = accessory if len(accessory) <= 6 else accessory[:5] + ".."
        equip_text = f"{rod_display} / {acc_display}"

        equip_x = width - padding - 180
        draw.text(
            (equip_x, info_y),
            equip_text,
            font=small_font,
            fill=GAME_COLORS["text_tertiary"],
        )

        current_y = card_y2 + card_margin

    footer_y = current_y + 10
    draw_game_divider(draw, padding, width - padding, footer_y)

    footer_text = "💡 可用：/排行榜 数量 /排行榜 重量 /排行榜 历史"
    draw.text(
        (padding + 10, footer_y + 12),
        footer_text,
        font=small_font,
        fill=GAME_COLORS["text_muted"],
    )

    try:
        image.save(output_path)
        logger.info(f"排行榜图片已保存到 {output_path}")
    except Exception as e:
        logger.error(f"保存排行榜图片失败: {e}")
        raise e
