"""
遊戲風格UI組件庫
提供統一的遊戲風格視覺元素
"""

from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple, List, Optional


def create_game_gradient(
    width: int,
    height: int,
    top_color: Tuple[int, int, int] = (25, 35, 55),
    bottom_color: Tuple[int, int, int] = (45, 55, 85),
    color_scheme: str = "default",
) -> Image.Image:
    """創建遊戲風格深色漸層背景
    
    Args:
        width: 寬度
        height: 高度
        top_color: 頂部顏色（當 color_scheme="default" 時使用）
        bottom_color: 底部顏色（當 color_scheme="default" 時使用）
        color_scheme: 配色方案 ("default", "aquarium")
    """
    # 根據配色方案選擇顏色
    if color_scheme == "aquarium":
        # 水族箱主題：深藍色調
        top_color = (15, 35, 65)
        bottom_color = (25, 55, 95)
    
    image = Image.new("RGB", (width, height), bottom_color)
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / height
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 疊加柔和光斑，提升層次感
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    
    if color_scheme == "aquarium":
        # 水族箱主題：藍綠色光斑
        glow_draw.ellipse(
            (-width // 4, -height // 3, width // 2, height // 2),
            fill=(70, 145, 220, 65),
        )
        glow_draw.ellipse(
            (width // 2, -height // 5, width + width // 4, height // 2),
            fill=(95, 195, 195, 45),
        )
    else:
        # 默認主題
        glow_draw.ellipse(
            (-width // 4, -height // 3, width // 2, height // 2),
            fill=(90, 145, 220, 55),
        )
        glow_draw.ellipse(
            (width // 2, -height // 5, width + width // 4, height // 2),
            fill=(255, 195, 95, 35),
        )
    
    glow = glow.filter(ImageFilter.GaussianBlur(46))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

    # 淡淡的網格線，讓版面更精緻
    draw = ImageDraw.Draw(image)
    grid_color = (72, 92, 128)
    for x in range(0, width, 48):
        draw.line((x, 0, x, height), fill=grid_color, width=1)
    for y in range(0, height, 48):
        draw.line((0, y, width, y), fill=grid_color, width=1)

    return image


def draw_game_card(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    radius: int = 12,
    fill: Tuple[int, int, int] = (35, 45, 65),
    border_color: Tuple[int, int, int] = (80, 120, 180),
    border_width: int = 2,
    shadow: bool = True,
) -> None:
    """繪製遊戲風格卡片（帶邊框和陰影）"""
    x1, y1, x2, y2 = bbox

    # 繪製陰影
    if shadow:
        shadow_offset = 3
        draw.rounded_rectangle(
            (
                x1 + shadow_offset,
                y1 + shadow_offset,
                x2 + shadow_offset,
                y2 + shadow_offset,
            ),
            radius=radius,
            fill=(20, 25, 35),
        )

    # 繪製卡片主體
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=fill,
        outline=border_color,
        width=border_width,
    )

    # 頂部高光線
    draw.line(
        (x1 + radius, y1 + 1, x2 - radius, y1 + 1),
        fill=(min(255, fill[0] + 26), min(255, fill[1] + 26), min(255, fill[2] + 26)),
        width=1,
    )


def draw_game_button(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    text: str,
    font,
    radius: int = 8,
    fill: Tuple[int, int, int] = (60, 100, 160),
    border_color: Tuple[int, int, int] = (100, 150, 220),
    text_color: Tuple[int, int, int] = (255, 255, 255),
) -> None:
    """繪製遊戲風格按鈕"""
    x1, y1, x2, y2 = bbox

    # 繪製立體效果（底部陰影）
    draw.rounded_rectangle(
        (x1, y1 + 3, x2, y2),
        radius=radius,
        fill=(fill[0] - 20, fill[1] - 20, fill[2] - 20),
    )

    # 繪製按鈕主體
    draw.rounded_rectangle(
        (x1, y1, x2, y2 - 3), radius=radius, fill=fill, outline=border_color, width=2
    )

    # 繪製文字（居中）
    bbox_text = draw.textbbox((0, 0), text, font=font)
    text_w = bbox_text[2] - bbox_text[0]
    text_h = bbox_text[3] - bbox_text[1]
    text_x = (x1 + x2 - text_w) // 2
    text_y = (y1 + y2 - text_h) // 2 - 1
    draw.text((text_x, text_y), text, font=font, fill=text_color)


def draw_game_title_bar(
    draw: ImageDraw.ImageDraw,
    width: int,
    y: int,
    height: int = 50,
    title: str = "",
    font=None,
    icon: str = "",
) -> None:
    """繪製遊戲風格標題欄"""
    # 標題欄背景
    draw.rectangle((0, y, width, y + height), fill=(40, 55, 80))

    # 輕微漸層疊加
    for i in range(height):
        alpha_ratio = i / max(1, height)
        tint = int(26 * (1 - alpha_ratio))
        draw.line(
            (0, y + i, width, y + i),
            fill=(40 + tint, 55 + tint, 80 + tint),
            width=1,
        )

    # 頂部裝飾線
    draw.line([(0, y), (width, y)], fill=(100, 150, 220), width=3)

    # 底部裝飾線
    draw.line(
        [(0, y + height - 1), (width, y + height - 1)], fill=(60, 80, 110), width=2
    )

    # 繪製標題
    if title and font:
        draw.text(
            (28, y + 10),
            f"{icon} {title}" if icon else title,
            font=font,
            fill=(220, 230, 255),
        )


def draw_game_divider(
    draw: ImageDraw.ImageDraw,
    x1: int,
    x2: int,
    y: int,
    color: Tuple[int, int, int] = (80, 100, 140),
) -> None:
    """繪製遊戲風格分隔線"""
    # 主線
    draw.line([(x1, y), (x2, y)], fill=color, width=2)
    # 裝飾點
    mid = (x1 + x2) // 2
    draw.ellipse([(mid - 3, y - 3), (mid + 3, y + 3)], fill=color)


def draw_rarity_badge(
    draw: ImageDraw.ImageDraw, x: int, y: int, rarity: int, font
) -> None:
    """繪製稀有度徽章"""
    colors = {
        1: (180, 180, 180),  # 普通 - 灰
        2: (100, 200, 100),  # 優秀 - 綠
        3: (100, 150, 255),  # 稀有 - 藍
        4: (180, 100, 255),  # 史詩 - 紫
        5: (255, 180, 50),  # 傳說 - 橙
    }
    color = colors.get(rarity, (180, 180, 180))

    # 繪製星星
    stars = "★" * rarity
    draw.text((x, y), stars, font=font, fill=color)


# 遊戲風格配色方案
GAME_COLORS = {
    "bg_dark": (25, 35, 55),
    "bg_card": (35, 45, 65),
    "bg_light": (45, 55, 85),
    "border": (80, 120, 180),
    "border_highlight": (120, 170, 240),
    "text_primary": (230, 240, 255),
    "text_secondary": (180, 190, 210),
    "text_muted": (130, 140, 160),
    "accent_blue": (80, 150, 220),
    "accent_green": (80, 200, 120),
    "accent_red": (220, 100, 100),
    "accent_gold": (255, 200, 80),
    "success": (100, 200, 100),
    "warning": (255, 180, 80),
    "error": (220, 100, 100),
}


def get_rarity_color(rarity: int) -> Tuple[int, int, int]:
    """根據稀有度獲取顏色"""
    colors = {
        1: (180, 180, 180),
        2: (100, 200, 100),
        3: (100, 150, 255),
        4: (180, 100, 255),
        5: (255, 180, 50),
    }
    return colors.get(rarity, (180, 180, 180))
