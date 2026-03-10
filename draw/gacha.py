from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw

from .game_ui import (
    GAME_COLORS,
    create_game_gradient,
    draw_game_card,
    draw_game_title_bar,
    draw_game_divider,
    get_rarity_color,
)
from .styles import load_font

# Safety margin to prevent content truncation
SAFETY_MARGIN = 50


def _safe_get(obj: Union[Dict, Any], key: str, default: Any = None) -> Any:
    """安全获取属性或字典值"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def draw_gacha_pool_list_image(pools: List[Any]) -> Image.Image:
    """卡池列表圖片 - 統一遊戲風格版"""
    width = 940
    card_height = 90
    title_bar_height = 60
    footer_height = 80
    spacing = 12
    padding = 24

    title_font = load_font(32)
    body_font = load_font(20)
    small_font = load_font(16)

    # 計算高度並添加安全邊距
    num_pools = max(1, len(pools))
    calculated_height = (
        title_bar_height
        + padding
        + (card_height + spacing) * num_pools
        + footer_height
        + padding
    )
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    y = padding
    draw_game_title_bar(
        draw, width, y, title_bar_height, "抽卡池列表", title_font, "🎰"
    )
    y += title_bar_height + padding

    # 繪製卡池列表
    for idx, pool in enumerate(pools, start=1):
        pid = _safe_get(pool, "gacha_pool_id", "?")
        name = str(_safe_get(pool, "name", "未知卡池"))
        desc = str(_safe_get(pool, "description") or "")
        if _safe_get(pool, "cost_premium_currency"):
            cost_text = f"💎 {_safe_get(pool, 'cost_premium_currency')} 高級貨幣 / 次"
        else:
            cost_text = f"💰 {_safe_get(pool, 'cost_coins', 0)} 金幣 / 次"

        # 使用統一卡片樣式
        draw_game_card(draw, (padding, y, width - padding, y + card_height))

        # 卡池信息
        draw.text(
            (padding + 20, y + 12),
            f"{idx}. ID {pid}｜{name[:20]}",
            font=body_font,
            fill=GAME_COLORS["text_primary"],
        )
        draw.text(
            (padding + 20, y + 42),
            cost_text,
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        if desc:
            draw.text(
                (padding + 20, y + 64),
                desc[:50],
                font=small_font,
                fill=GAME_COLORS["text_tertiary"],
            )

        y += card_height + spacing

    # 繪製底部提示
    y = height - footer_height - padding - SAFETY_MARGIN
    draw_game_divider(draw, padding, width - padding, y)
    y += 16
    draw.text(
        (padding + 20, y),
        "💡 查看詳情：/查看卡池 ID",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    y += 28
    draw.text(
        (padding + 20, y),
        "💡 單抽 / 十連：/抽卡 ID /十連 ID [次數]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_gacha_pool_detail_image(
    pool: Union[Dict[str, Any], Any], probabilities: List[Union[Dict[str, Any], Any]]
) -> Image.Image:
    """卡池詳情圖片 - 統一遊戲風格版"""
    width = 980
    item_height = 56
    title_bar_height = 70
    info_section_height = 90
    footer_height = 70
    spacing = 8
    padding = 24

    title_font = load_font(32)
    body_font = load_font(22)
    small_font = load_font(18)
    tiny_font = load_font(14)

    # 計算高度 - 雙列佈局，行數 = ceil(總數/2)
    num_items = max(1, len(probabilities))
    num_rows = (num_items + 1) // 2  # 雙列，所以除以2
    calculated_height = (
        title_bar_height
        + info_section_height
        + padding
        + (item_height + spacing) * num_rows
        + footer_height
        + padding
    )
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    pool_name = _safe_get(pool, "name", "卡池詳情")
    y = padding
    draw_game_title_bar(
        draw, width, y, title_bar_height, f"{pool_name[:30]}", title_font, "🎰"
    )
    y += title_bar_height + 12

    # 卡池信息區域
    pool_id = _safe_get(pool, "gacha_pool_id", "?")
    draw.text(
        (padding + 20, y),
        f"ID：{pool_id}",
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )

    cost_premium = _safe_get(pool, "cost_premium_currency")
    if cost_premium:
        cost_text = f"💎 消耗：{cost_premium} 高級貨幣 / 次"
    else:
        cost_coins = _safe_get(pool, "cost_coins", 0)
        cost_text = f"💰 消耗：{cost_coins} 金幣 / 次"

    draw.text(
        (padding + 240, y),
        cost_text,
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    y += 32

    # 描述
    desc = str(_safe_get(pool, "description") or "")
    if desc:
        draw.text(
            (padding + 20, y),
            f"📖 {desc[:60]}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        y += 28

    y += 12
    draw_game_divider(draw, padding, width - padding, y)
    y += spacing + 8

    # 概率列表表頭
    draw.text(
        (padding + 20, y),
        "物品名稱",
        font=small_font,
        fill=GAME_COLORS["text_tertiary"],
    )
    draw.text(
        (width - padding - 100, y),
        "機率",
        font=small_font,
        fill=GAME_COLORS["text_tertiary"],
    )
    y += 24

    # 概率列表 - 雙列佈局
    col_count = 2
    col_width = (width - padding * 2 - 20) // col_count
    items_per_col = (len(probabilities) + col_count - 1) // col_count

    for col in range(col_count):
        col_y = y
        start_idx = col * items_per_col
        end_idx = min(start_idx + items_per_col, len(probabilities))

        for idx in range(start_idx, end_idx):
            item = probabilities[idx]
            rarity = int(_safe_get(item, "item_rarity", 1) or 1)
            rarity = max(1, min(rarity, 10))
            stars = "⭐" * rarity
            name = _safe_get(item, "item_name", "未知物品")
            prob = _safe_get(item, "probability", 0)
            try:
                ptext = f"{float(prob) * 100:.2f}%"
            except Exception:
                ptext = str(prob)

            col_x = padding + col * (col_width + 10)

            # 使用統一卡片樣式
            draw_game_card(draw, (col_x, col_y, col_x + col_width, col_y + item_height))

            # 使用統一稀有度顏色
            rarity_color = get_rarity_color(rarity)

            # 左側：名字 + 小進度條
            draw.text(
                (col_x + 12, col_y + 8),
                f"{stars} {name[:22]}",
                font=small_font,
                fill=rarity_color,
            )

            # 短進度條
            try:
                bar_x = col_x + 12
                bar_y = col_y + item_height - 10
                bar_width = col_width - 80
                fill_width = int(bar_width * float(prob))
                draw.rectangle(
                    [bar_x, bar_y, bar_x + bar_width, bar_y + 4],
                    fill=GAME_COLORS.get("bg_secondary", "#2a2a3e"),
                )
                if fill_width > 0:
                    draw.rectangle(
                        [bar_x, bar_y, bar_x + max(2, fill_width), bar_y + 4],
                        fill=rarity_color,
                    )
            except:
                pass

            # 右側：機率
            draw.text(
                (col_x + col_width - 90, col_y + 8),
                ptext,
                font=small_font,
                fill=GAME_COLORS["text_primary"],
            )

            col_y += item_height + spacing

    # 底部提示
    y = height - footer_height - padding
    draw_game_divider(draw, padding, width - padding, y)
    y += 20
    draw.text(
        (padding + 20, y),
        f"💡 抽卡：/抽卡 {pool_id} 十連：/十連 {pool_id}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_gacha_result_image(
    pool_id: int,
    pool_name: str,
    items: List[Dict[str, Any]],
    is_ten_draw: bool = False,
    multi_draw_times: int = 1,
) -> Image.Image:
    """抽卡結果圖片 - 統一遊戲風格版

    Args:
        pool_id: 卡池 ID
        pool_name: 卡池名稱
        items: 抽卡結果列表
        is_ten_draw: 是否為十連抽
        multi_draw_times: 多次十連次數（僅當 is_ten_draw=True 且 times>1 時有效）
    """
    width = 900
    item_height = 52
    title_bar_height = 80
    stats_height = 70
    footer_height = 60
    spacing = 8
    padding = 24

    title_font = load_font(28)
    body_font = load_font(18)
    small_font = load_font(16)

    # 統計稀有度
    rarity_counts = {}
    for item in items:
        rarity = item.get("rarity", 1)
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

    # 計算高度 - 根據實際物品數量動態計算（最多顯示20個）
    num_items = max(1, len(items))
    display_count = min(num_items, 20)
    calculated_height = (
        title_bar_height
        + stats_height
        + padding
        + (item_height + spacing) * display_count
        + footer_height
        + padding
    )
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    if is_ten_draw:
        if multi_draw_times > 1:
            title = f"{multi_draw_times}次十連抽卡結果"
        else:
            title = "十連抽卡結果"
    else:
        title = "單抽結果"

    y = padding
    draw_game_title_bar(draw, width, y, title_bar_height, title, title_font, "🎰")
    y += title_bar_height + 12

    # 卡池信息 - 使用更好看的格式
    draw.text(
        (padding + 20, y),
        f"卡池：{pool_name[:25]} (ID: {pool_id})",
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    y += 32

    # 統計信息 - 居中顯示
    rarity_parts = []
    for r in sorted(rarity_counts.keys(), reverse=True):
        stars = "⭐" * r
        rarity_parts.append(f"{stars}×{rarity_counts[r]}")
    stats_text = " | ".join(rarity_parts[:5])
    if len(rarity_parts) > 5:
        stats_text += " ..."
    draw.text(
        (padding + 20, y),
        f"📊 {stats_text}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )
    y += 36

    draw_game_divider(draw, padding, width - padding, y)
    y += spacing + 12

    # 物品列表（最多顯示20個）
    display_items = items[:20] if len(items) > 20 else items
    for item in display_items:
        rarity = item.get("rarity", 1)
        name = item.get("name", "未知物品")
        item_type = item.get("type", "")

        # 使用統一卡片樣式
        draw_game_card(draw, (padding, y, width - padding, y + item_height))

        # 使用統一稀有度顏色
        rarity_color = get_rarity_color(rarity)

        if item_type == "coins":
            # 金幣類型 - 優化顯示
            quantity = item.get("quantity", 0)
            draw.text(
                (padding + 20, y + 16),
                f"💰 {quantity:,}",
                font=body_font,
                fill=GAME_COLORS["accent_gold"],
            )
        else:
            # 普通物品 - 增加星星和名字的分隔感
            stars = "⭐" * rarity
            draw.text(
                (padding + 20, y + 16),
                f"{stars} {name[:35]}",
                font=body_font,
                fill=rarity_color,
            )

        y += item_height + spacing

    # 如果有更多物品
    if len(items) > 20:
        draw.text(
            (padding + 20, y),
            f"... 還有 {len(items) - 20} 件物品",
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )

    # 底部提示
    y = height - footer_height - padding
    draw_game_divider(draw, padding, width - padding, y)
    y += 20
    draw.text(
        (padding + 20, y),
        f"💡 抽卡：/抽卡 {pool_id} 十連：/十連 {pool_id}",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image


def draw_multi_ten_gacha_summary_image(
    pool_id: int,
    pool_name: str,
    times: int,
    total_items: int,
    total_cost: int,
    cost_type: str,
    rarity_counts: Dict[int, int],
    item_counts: Dict[str, int],
    coin_total: int,
) -> Image.Image:
    """多次十連抽卡統計圖片 - 統一遊戲風格版

    Args:
        pool_id: 卡池ID
        pool_name: 卡池名稱
        times: 十連次數
        total_items: 總物品數
        total_cost: 總消耗
        cost_type: 消耗類型（"金幣" 或 "高級貨幣"）
        rarity_counts: 稀有度統計
        item_counts: 物品統計
        coin_total: 金幣總計
    """
    width = 900
    title_bar_height = 80
    stats_section_height = 120
    item_section_height = max(40 * len(item_counts), 200)  # 物品詳情區域
    footer_height = 60
    spacing = 8
    padding = 24

    title_font = load_font(28)
    body_font = load_font(18)
    small_font = load_font(16)

    # 計算高度
    calculated_height = (
        title_bar_height
        + stats_section_height
        + item_section_height
        + footer_height
        + padding * 3
    )
    height = calculated_height + SAFETY_MARGIN

    # 使用統一遊戲風格背景
    image = create_game_gradient(width, int(height))
    draw = ImageDraw.Draw(image)

    # 繪製標題欄
    y = padding
    draw_game_title_bar(
        draw, width, y, title_bar_height, f"{times}次十連抽卡統計", title_font, "🎰"
    )
    y += title_bar_height + 12

    # 卡池信息
    draw.text(
        (padding + 20, y),
        f"卡池：{pool_name[:25]} (ID: {pool_id})",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )
    y += 28

    # 消耗統計
    draw.text(
        (padding + 20, y),
        f"消耗{cost_type}：{total_cost:,}",
        font=body_font,
        fill=GAME_COLORS["accent_gold"],
    )
    y += 28

    draw.text(
        (padding + 20, y),
        f"獲得物品：{total_items} 件",
        font=body_font,
        fill=GAME_COLORS["text_secondary"],
    )
    y += 32

    draw_game_divider(draw, padding, width - padding, y)
    y += spacing + 8

    # 稀有度統計
    draw.text(
        (padding + 20, y),
        "【📊 稀有度統計】",
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    y += 28

    for rarity in [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]:
        count = rarity_counts.get(rarity, 0)
        if count > 0:
            stars = "⭐" * rarity
            rarity_color = get_rarity_color(rarity)
            draw.text(
                (padding + 24, y),
                f"{stars} {count} 件",
                font=small_font,
                fill=rarity_color,
            )
            y += 24

    y += 8

    # 金幣統計
    if coin_total > 0:
        draw.text(
            (padding + 20, y),
            f"💰 金幣總計：{coin_total:,}",
            font=body_font,
            fill=GAME_COLORS["accent_gold"],
        )
        y += 32

    draw_game_divider(draw, padding, width - padding, y)
    y += spacing + 8

    # 物品詳情
    draw.text(
        (padding + 20, y),
        "【🎁 物品詳情】",
        font=body_font,
        fill=GAME_COLORS["text_primary"],
    )
    y += 28

    # 按名稱排序
    sorted_items = sorted(item_counts.items())
    for item_name, count in sorted_items[:15]:  # 最多顯示15種物品
        draw.text(
            (padding + 24, y),
            f"{item_name[:25]} × {count}",
            font=small_font,
            fill=GAME_COLORS["text_secondary"],
        )
        y += 22

    if len(sorted_items) > 15:
        draw.text(
            (padding + 24, y),
            f"... 還有 {len(sorted_items) - 15} 種物品",
            font=small_font,
            fill=GAME_COLORS["text_muted"],
        )

    # 底部提示
    y = height - footer_height - padding - SAFETY_MARGIN
    draw_game_divider(draw, padding, width - padding, y)
    y += 20
    draw.text(
        (padding + 20, y),
        f"💡 繼續抽卡：/十連 {pool_id} [次數]",
        font=small_font,
        fill=GAME_COLORS["text_secondary"],
    )

    return image
