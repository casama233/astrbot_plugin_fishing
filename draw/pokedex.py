import os
from PIL import Image, ImageDraw
from typing import List, Dict, Any
from astrbot.api import logger
from datetime import datetime

from .utils import get_user_avatar, get_fish_icon
from .game_ui import (
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    GAME_COLORS,
    get_rarity_color,
)
from .styles import load_font

def format_weight(g):
    """将克转换为更易读的单位 (kg, t)"""
    if g is None:
        return "0g"
    if g >= 1000000:
        return f"{g / 1000000:.2f}t"
    if g >= 1000:
        return f"{g / 1000:.2f}kg"
    return f"{g}g"

# --- 布局 ---
IMG_WIDTH = 1200
PADDING = 20
CORNER_RADIUS = 12
HEADER_HEIGHT = 120
FISH_CARD_HEIGHT = 90   # 增加高度以適應更好的顯示
FISH_CARD_MARGIN = 12   # 增加間距
FISH_PER_PAGE = 15      # 每頁顯示15個，更易閱讀


# 导入优化的渐变生成函数
from .gradient_utils import create_vertical_gradient

def draw_rounded_rectangle(draw, bbox, radius, fill=None, outline=None, width=1):
    """優化的圓角矩形繪製 - 已由 game_ui 統一管理，此處保留兼容"""
    from .game_ui import draw_game_card
    if fill and not outline:
        draw_game_card(draw, bbox, radius=radius, fill=fill, border_color=None, shadow=False)
    elif fill and outline:
        draw_game_card(draw, bbox, radius=radius, fill=fill, border_color=outline, shadow=False)
    else:
        # 原始實現作為後備
        x1, y1, x2, y2 = bbox
        if fill is not None:
            draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
            draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
            draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
            draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)
        if outline is not None and width > 0:
            draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
            draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
            draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
            draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)
            draw.arc([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=outline, width=width)
            draw.arc([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=outline, width=width)
            draw.arc([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=outline, width=width)
            draw.arc([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=outline, width=width)


async def draw_pokedex(pokedex_data: Dict[str, Any], user_info: Dict[str, Any], output_path: str, page: int = 1, data_dir: str = None):
    """
    繪製圖鑒圖片 - 遊戲風格統一版本
    """
    pokedex_list = pokedex_data.get("pokedex", [])
    total_pages = (len(pokedex_list) + FISH_PER_PAGE - 1) // FISH_PER_PAGE
    
    # 驗證頁碼
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages

    start_index = (page - 1) * FISH_PER_PAGE
    end_index = start_index + FISH_PER_PAGE
    page_fishes = pokedex_list[start_index:end_index]

    # 頁腳高度和安全邊距
    FOOTER_HEIGHT = 80
    SAFETY_MARGIN = 50
    
    calculated_height = HEADER_HEIGHT + (FISH_CARD_HEIGHT + FISH_CARD_MARGIN) * len(page_fishes) + PADDING * 2 + FOOTER_HEIGHT
    img_height = calculated_height + SAFETY_MARGIN
    
    # 創建遊戲風格漸變背景
    img = create_game_gradient(IMG_WIDTH, img_height)
    draw = ImageDraw.Draw(img)
    
    # 使用統一的字體
    title_font = load_font(36)
    subtitle_font = load_font(20)
    body_font = load_font(18)
    small_font = load_font(16)

    # 繪製標題欄 - 使用遊戲風格
    nickname = user_info.get('nickname', '玩家')
    current_title = user_info.get('current_title')
    
    from ..core.utils import format_user_display_name
    display_name = format_user_display_name(nickname, current_title)
    
    header_text = f"{display_name}的圖鑒"
    draw_game_title_bar(draw, IMG_WIDTH, 0, HEADER_HEIGHT, header_text, title_font, "📖")
    
    # 進度信息
    progress_text = f"收集進度: {pokedex_data.get('unlocked_fish_count', 0)} / {pokedex_data.get('total_fish_count', 0)}"
    draw.text(
        (30, 70),
        progress_text,
        font=subtitle_font,
        fill=GAME_COLORS["text_secondary"],
    )
    
    # 頁碼信息
    page_text = f"第 {page} / {total_pages} 頁"
    draw.text(
        (IMG_WIDTH - 200, 70),
        page_text,
        font=subtitle_font,
        fill=GAME_COLORS["text_secondary"],
    )

    # 繪製魚卡片
    current_y = HEADER_HEIGHT + PADDING
    for i, fish in enumerate(page_fishes):
        card_y1 = current_y
        card_y2 = card_y1 + FISH_CARD_HEIGHT
        
        # 繪製魚卡片 - 使用遊戲風格
        draw_game_card(
            draw,
            (PADDING, card_y1, IMG_WIDTH - PADDING, card_y2),
            radius=CORNER_RADIUS,
            fill=GAME_COLORS["bg_card"],
            border_color=GAME_COLORS["border"],
            shadow=True,
        )
        
        # 左側內容區域
        left_pane_x = PADDING + 20
        
        # 嘗試加載並顯示魚類圖標
        icon_size = 60
        icon_x = left_pane_x
        icon_y = card_y1 + (FISH_CARD_HEIGHT - icon_size) // 2
        icon_url = fish.get("icon_url")
        if icon_url and data_dir:
            try:
                fish_icon = await get_fish_icon(icon_url, data_dir, icon_size)
                if fish_icon:
                    img.paste(fish_icon, (icon_x, icon_y), fish_icon)
                    left_pane_x += icon_size + 15
            except Exception as e:
                logger.warning(f"加載魚類圖標失敗: {e}, URL: {icon_url}")
        
        # 魚名和稀有度
        name_y = card_y1 + 15
        draw.text(
            (left_pane_x, name_y),
            fish.get("name", "未知魚"),
            font=subtitle_font,
            fill=GAME_COLORS["text_primary"],
        )
        
        # 稀有度星星 - 使用統一的稀有度顏色系統
        rarity = fish.get("rarity", 1)
        rarity_text = "★" * min(rarity, 10)  # 最多顯示10顆星
        if rarity > 10:
            rarity_text += f"+{rarity - 10}"
        rarity_color = get_rarity_color(rarity)
        draw.text(
            (left_pane_x, name_y + 28),
            rarity_text,
            font=body_font,
            fill=rarity_color,
        )
        
        # 右側統計信息
        stats_x = PADDING + 480
        stats_y = card_y1 + 12
        
        # 重量紀錄
        min_w = fish.get('min_weight', 0)
        max_w = fish.get('max_weight', 0)
        weight_text = f"⚖ 重量: {format_weight(min_w)} ~ {format_weight(max_w)}"
        draw.text(
            (stats_x, stats_y),
            weight_text,
            font=small_font,
            fill=GAME_COLORS["accent_gold"],
        )
        
        # 累計捕獲
        total_w = fish.get('total_weight', 0)
        caught_text = f"🎣 捕獲: {fish.get('total_caught', 0)} 條 ({format_weight(total_w)})"
        draw.text(
            (stats_x, stats_y + 22),
            caught_text,
            font=small_font,
            fill=GAME_COLORS["accent_blue"],
        )

        # 首次捕獲
        first_caught_time = fish.get('first_caught_time')
        if isinstance(first_caught_time, datetime):
            first_caught_text = f"⭐ 首次: {first_caught_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            first_caught_text = f"⭐ 首次: {str(first_caught_time).split('.')[0] if first_caught_time else '未知'}"
        draw.text(
            (stats_x, stats_y + 44),
            first_caught_text,
            font=small_font,
            fill=GAME_COLORS["success"],
        )
        
        # 描述
        desc_y = card_y1 + FISH_CARD_HEIGHT - 22
        desc_text = fish.get("description", "")[:80]  # 限制長度
        draw.text(
            (left_pane_x, desc_y),
            desc_text,
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )

        current_y = card_y2 + FISH_CARD_MARGIN

    # 繪製頁腳 - 使用遊戲風格
    footer_y = img_height - FOOTER_HEIGHT
    draw_game_divider(draw, 30, IMG_WIDTH - 30, footer_y + 10)
    
    # 翻頁提示
    if total_pages > 1:
        footer_text = f"💡 翻頁指令：/圖鑒 [頁碼]  |  當前第 {page} / {total_pages} 頁"
    else:
        footer_text = "💡 繼續釣魚解鎖更多魚類！"
    
    draw.text(
        (30, footer_y + 30),
        footer_text,
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    # 應用整個圖片的圓角遮罩
    def apply_rounded_corners(image, corner_radius=20):
        """為整個圖片應用圓角"""
        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, image.size[0], image.size[1]], corner_radius, fill=255)
        
        output = Image.new("RGBA", image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        
        return output

    try:
        logger.info(f"準備將圖鑒圖片保存至: {output_path}")
        rounded_img = apply_rounded_corners(img, 20)
        rounded_img.save(output_path)
        logger.info(f"圖鑒圖片已成功保存至 {output_path}")
    except Exception as e:
        logger.error(f"保存圖鑒圖片失敗: {e}", exc_info=True)
        raise
