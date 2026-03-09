import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .text_utils import (
    normalize_display_text,
    draw_text_smart,
    load_font_with_cjk_fallback,
    get_text_size_cached,
)
from .styles import (
    COLOR_TITLE,
    COLOR_CMD,
    COLOR_LINE,
    COLOR_SHADOW,
    FONT_PATH_BOLD,
    FONT_PATH_REGULAR,
)


def draw_help_image():
    # 画布宽度（高度将自适应计算）
    width = 800

    # 导入优化的渐变生成函数
    from .gradient_utils import create_vertical_gradient

    bg_top = (240, 248, 255)  # 浅蓝
    bg_bot = (255, 255, 255)  # 白

    # 2. 加载字体
    title_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 32)
    subtitle_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 28)
    section_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 24)
    cmd_font = load_font_with_cjk_fallback(FONT_PATH_BOLD, 18)
    desc_font = load_font_with_cjk_fallback(FONT_PATH_REGULAR, 16)

    # 3. 颜色定义
    title_color = COLOR_TITLE
    cmd_color = COLOR_CMD
    card_bg = (255, 255, 255)
    line_color = COLOR_LINE
    shadow_color = COLOR_SHADOW

    # 4. 获取文本尺寸的辅助函数（测量版）
    _measure_img = Image.new("RGB", (10, 10), bg_bot)
    _measure_draw = ImageDraw.Draw(_measure_img)

    def measure_text_size(text, font):
        bbox = _measure_draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 5. 处理logo背景色的函数
    def replace_white_background(img, new_bg_color=bg_top, threshold=240):
        """将图片的白色背景替换为指定颜色"""
        img = img.convert("RGBA")
        data = img.getdata()
        new_data = []

        for item in data:
            r, g, b = item[:3]
            alpha = item[3] if len(item) > 3 else 255

            # 如果像素接近白色，就替换为新背景色
            if r >= threshold and g >= threshold and b >= threshold:
                new_data.append((*new_bg_color, alpha))
            else:
                new_data.append(item)

        img.putdata(new_data)
        return img

    # 6. Logo/标题布局（先定义数值，稍后绘制）
    logo_size = 160
    logo_x = 30
    logo_y = 25
    title_y = logo_y + logo_size // 2

    # 7. 圆角矩形＋阴影 helper
    def draw_card(x0, y0, x1, y1, radius=12):
        # 简化阴影效果
        shadow_offset = 3
        # 绘制阴影
        draw.rounded_rectangle(
            [
                x0 + shadow_offset,
                y0 + shadow_offset,
                x1 + shadow_offset,
                y1 + shadow_offset,
            ],
            radius,
            fill=(220, 220, 220),
        )
        # 白色卡片
        draw.rounded_rectangle(
            [x0, y0, x1, y1], radius, fill=card_bg, outline=line_color, width=1
        )

    # 8. 绘制章节和命令
    def draw_section(title, cmds, y_start, cols=3):
        # 章节标题左对齊
        title_x = 50
        draw_text_smart(
            draw, (title_x, y_start - 12), title, font=section_font, fill=title_color
        )
        w, h = get_text_size_cached(title, section_font)

        # 标题下劃線
        underline_y = y_start + h // 2 + 2
        draw.line(
            [(title_x, underline_y), (title_x + w, underline_y)],
            fill=title_color,
            width=3,
        )

        y = y_start + h // 2 + 25

        card_w = (width - 60) // cols
        card_h = 85
        pad = 15

        for idx, (cmd, desc) in enumerate(cmds):
            col = idx % cols
            row = idx // cols
            x0 = 30 + col * card_w
            y0 = y + row * (card_h + pad)
            x1 = x0 + card_w - 10
            y1 = y0 + card_h

            draw_card(x0, y0, x1, y1)

            # 文本居中顯示
            cx = (x0 + x1) // 2
            # 命令文本
            cmd_w, _ = get_text_size_cached(cmd, cmd_font)
            draw_text_smart(
                draw, (cx - cmd_w // 2, y0 + 12), cmd, font=cmd_font, fill=cmd_color
            )

            # 描述文本 - 支持多行
            desc_lines = desc.split("\n") if "\n" in desc else [desc]
            for i, line in enumerate(desc_lines):
                line_w, _ = get_text_size_cached(line, desc_font)
                draw_text_smart(
                    draw,
                    (cx - line_w // 2, y0 + 40 + i * 18),
                    line,
                    font=desc_font,
                    fill=(100, 100, 100),
                )

        rows = math.ceil(len(cmds) / cols)
        return y + rows * (card_h + pad) + 35

    # 9. 各段命令数据
    basic = [
        ("註冊/注册", "萌新報到！\n開啟釣魚生涯"),
        ("釣魚/钓鱼", "甩一竿！\n看看運氣如何"),
        ("簽到/签到", "每日打卡\n領取低保工資"),
        ("自動釣魚/自动钓鱼", "解放雙手\n掛機摸魚神器"),
        ("釣魚區域 [ID]", "世界這麼大\n我想去別處釣釣"),
        ("釣魚記錄/钓鱼记录", "回顧你的\n光輝（或空軍）歷史"),
        ("更新暱稱 [新暱稱]", "換個馬甲\n重新做人"),
        ("釣魚幫助/帮助", "遇事不決\n就問問神奇海螺"),
    ]

    inventory = [
        ("狀態/状态", "照照鏡子\n看看現在有多強"),
        ("背包", "翻翻兜裡\n都有什麼寶貝"),
        ("魚塘/鱼塘", "巡視你的\n私人水族館"),
        ("魚塘容量", "看看魚塘\n還能塞多少魚"),
        ("升級魚塘", "擴建魚塘\n給魚兒換個大別墅"),
        ("水族箱", "保險櫃裡的\n珍藏觀賞魚"),
        ("水族箱 帮助", "水族箱\n使用說明書"),
        ("放入水族箱 [FID] [数量]", "把愛魚\n鎖進保險櫃"),
        ("移出水族箱 [FID] [数量]", "把魚拿出來\n準備賣錢"),
        ("升級水族箱", "給保險櫃\n擴個容"),
        ("魚竿/鱼竿", "工欲善其事\n必先利其器"),
        ("鱼饵", "捨不得孩子\n套不著狼"),
        ("飾品/饰品", "花裡胡哨\n但有用的護身符"),
        ("道具", "各種奇奇怪怪\n的功能道具"),
        ("使用 [ID]", "使用道具\n或裝備新傢伙"),
        ("开启全部钱袋", "一鍵暴富\n享受數錢的快感"),
        ("精煉/精炼 [ID]", "搏一搏\n單車變摩托"),
        ("出售 [ID]", "斷捨離\n把不用的換成錢"),
        ("鎖定/锁定 [ID]", "給寶貝上鎖\n手滑黨必備"),
        ("解鎖/解锁 [ID]", "解除鎖定\n準備交易或丟棄"),
        ("金幣/金币", "看看錢包\n還有多少餘額"),
        ("高級貨幣", "查看你的\n小金庫（點券）"),
    ]

    market = [
        ("全部賣出", "清空魚塘\n統統換成小錢錢"),
        ("保留賣出", "每種留一條\n剩下的全賣了"),
        ("砸鍋賣鐵", "警告！除了褲衩\n什麼都賣（慎用）"),
        ("出售稀有度 [1-5]", "精準清倉\n只賣指定檔次的魚"),
        ("出售所有魚竿", "清空倉庫\n舊魚竿大甩賣"),
        ("出售所有飾品", "清空首飾盒\n舊飾品大處理"),
        ("商店", "官方商城\n童叟無欺"),
        ("商店 购买 [商品ID] [数量]", "買買買！\n不買不是釣魚人"),
        ("市场", "跳蚤市場\n淘淘玩家的好貨"),
        ("市场 上架 [ID] [价格] [数量]", "擺攤賣貨\n支持蒙面交易"),
        ("市场 购买 [ID]", "看中就買\n手慢無"),
        ("市场 我的上架", "看看攤位上\n還有什麼沒賣掉"),
        ("市场 下架 [ID]", "收攤不賣了\n或者改個價"),
    ]

    gacha = [
        ("抽卡 [卡池ID]", "單抽奇蹟\n檢測血統的時刻"),
        ("十连 [卡池ID]", "十連保底\n大力出奇蹟"),
        ("查看卡池 [ID]", "看看池子裡\n都有什麼好東西"),
        ("抽卡记录", "查查流水\n看看虧了多少"),
        ("擦弹 [金额]", "玩的就是心跳\n贏了會所嫩模"),
        ("擦弹记录", "看看你的\n心跳回憶"),
        ("命运之轮 [金额]", "是男人就\n下100層"),
        ("繼續/继续", "繼續挑戰\n下一層獎勵翻倍"),
        ("放棄/放弃", "見好就收\n落袋為安"),
    ]

    sicbo = [
        ("骰宝 开庄", "坐莊開局\n倒數60秒等人來送"),
        ("骰宝 状态", "看看現在\n戰況如何"),
        ("骰宝 我的下注", "看看自己\n押了什麼"),
        ("骰宝 帮助", "規則說明\n賭神必讀"),
        ("骰宝 赔率", "完整賠率表\n數學家請進"),
        ("骰宝下注 大 [金额]", "押大(11-17點)\n賠率1:1"),
        ("骰宝下注 小 [金额]", "押小(4-10點)\n賠率1:1"),
        ("骰宝下注 单 [金额]", "押單數\n賠率1:1"),
        ("骰宝下注 双 [金额]", "押雙數\n賠率1:1"),
        ("骰宝下注 豹子 [金额]", "押三同號\n賠率1:24"),
        ("骰宝下注 一点 [金额]", "押出現1點\n動態賠率"),
        ("骰宝下注 4点 [金额]", "精準押4點\n賠率1:50"),
        ("骰宝下注 17点 [金额]", "精準押17點\n賠率1:50"),
        ("钓鱼管理 骰宝结算", "管理員專用\n強制收盤"),
        ("钓鱼管理 骰宝倒计时 [秒数]", "管理員專用\n控制開盤時間"),
        ("钓鱼管理 骰宝模式 [模式]", "管理員專用\n切換圖片/文字"),
    ]

    social = [
        ("排行榜 [类型]", "看看誰是\n釣魚界扛把子"),
        ("偷鱼 [@用户]", "讀書人的事\n能算偷嗎？"),
        ("电鱼 [@用户]", "正義執行（？）\n給群友戒網癮"),
        ("驱灵 [@用户]", "破除防護\n讓對手裸奔"),
        ("偷看鱼塘 [@用户]", "視姦群友\n看看有沒有大貨"),
        ("转账 [@用户] [金额]", "發紅包\n或是交保護費"),
        ("红包 发红包 [金额] [数量]", "撒幣時間\n全場由趙公子買單"),
        ("红包 领红包 [ID] [口令]", "搶紅包啦\n手慢無"),
        ("红包 红包列表", "看看還有\n哪些紅包沒領"),
        ("红包 红包详情 [ID]", "看看誰是\n運氣王"),
        ("红包 撤回红包 [ID]", "發錯了？\n趕緊撤回來"),
        ("钓鱼管理 清理红包 [所有]", "管理員專用\n打掃戰場"),
        ("查看称号", "看看頭頂\n掛著什麼頭銜"),
        ("使用称号 [ID]", "換個頭銜\n換種心情"),
        ("查看成就", "細數你的\n豐功偉績"),
        ("税收记录", "看看為國家\n貢獻了多少"),
        ("鱼类图鉴", "點亮圖鑑\n強迫症福音"),
    ]

    exchange = [
        ("交易所", "期貨大廳\n觀察市場走勢"),
        ("交易所 开户", "成為股民\n的第一步"),
        ("交易所 持仓", "看看手裡\n被套牢了多少"),
        ("交易所 买入 [商品] [数量]", "抄底建倉\n坐等升值"),
        ("交易所 卖出 [商品] [数量]", "高位套現\n落袋為安"),
        ("交易所 历史 [商品] [天数]", "回看走勢\n研究波動"),
        ("交易所 分析 [商品] [天数]", "看看盤面\n做點判斷"),
        ("交易所 帮助", "股市有風險\n入市需謹慎"),
        ("交易所 清仓", "割肉離場\n或者止盈出局"),
    ]

    admin = [
        ("钓鱼管理 同步", "同步資料\n讓配置就位"),
        ("钓鱼管理 修改金币 [用户ID] [数量]", "上帝之手\n修改餘額"),
        ("钓鱼管理 奖励金币 [用户ID] [数量]", "系統發錢\n支持中文數字"),
        ("钓鱼管理 扣除金币 [用户ID] [数量]", "系統罰款\n沒收非法所得"),
        ("钓鱼管理 修改高级货币 [用户ID] [数量]", "修改點券\n氪金玩家待遇"),
        ("钓鱼管理 全体发放道具 [道具ID] [数量]", "全服補償\n或者節日禮物"),
        ("钓鱼管理 授予称号 [用户] [名称]", "欽定頭銜\n你就是釣魚王"),
        ("钓鱼管理 移除称号 [用户] [名称]", "剝奪頭銜\n貶為庶民"),
        ("钓鱼管理 创建称号 [名称] ...", "創造新頭銜\n定義榮耀"),
        ("钓鱼管理 补充鱼池", "管理員專用\n重置稀有魚"),
        ("钓鱼管理 开启钓鱼后台管理", "打開後門\nWeb管理端"),
        ("钓鱼管理 关闭钓鱼后台管理", "關閉後門\n安全第一"),
        ("钓鱼管理 代理上线 [用户ID]", "靈魂附體\n代打模式"),
        ("钓鱼管理 代理下线", "靈魂出竅\n回歸自我"),
    ]

    # 10. 先计算自适应高度
    def section_delta(item_count: int, cols: int) -> int:
        rows = math.ceil(item_count / cols) if item_count > 0 else 0
        # 与 draw_section 中的垂直占位保持一致：h//2+25 起始 + rows*(card_h+pad) + 35
        _, h = measure_text_size("标题", section_font)
        card_h = 85
        pad = 15
        return (h // 2 + 25) + rows * (card_h + pad) + 35

    y0_est = logo_y + logo_size + 30
    y0_est += section_delta(len(basic), 3)
    y0_est += section_delta(len(inventory), 3)
    y0_est += section_delta(len(market), 3)
    y0_est += section_delta(len(gacha), 3)
    y0_est += section_delta(len(sicbo), 3)
    y0_est += section_delta(len(social), 2)
    y0_est += section_delta(len(exchange), 2)
    y0_est += section_delta(len(admin), 2)
    footer_y_est = y0_est + 20
    final_height = footer_y_est + 30

    # 用最终高度创建画布，然后进行真正绘制
    image = create_vertical_gradient(width, final_height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)

    # 绘制 Logo 和 标题
    try:
        logo = Image.open(
            os.path.join(os.path.dirname(__file__), "resource", "astrbot_logo.jpg")
        )
        logo = replace_white_background(logo, bg_top)
        logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", logo.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, logo.size[0], logo.size[1]], 20, fill=255)
        output = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        output.paste(logo, (0, 0))
        output.putalpha(mask)
        image.paste(output, (logo_x, logo_y), output)
    except Exception as e:
        # 如果没有logo文件，绘制一个圆角占位符
        draw.rounded_rectangle(
            (logo_x, logo_y, logo_x + logo_size, logo_y + logo_size),
            20,
            fill=bg_top,
            outline=(180, 180, 180),
            width=2,
        )
        draw.text(
            (logo_x + logo_size // 2, logo_y + logo_size // 2),
            "LOGO",
            fill=(120, 120, 120),
            font=subtitle_font,
            anchor="mm",
        )

    title_text = "釣魚遊戲幫助"
    title_w, _ = get_text_size_cached(title_text, title_font)
    draw_text_smart(
        draw,
        (width // 2 - title_w // 2, title_y - 20),
        title_text,
        font=title_font,
        fill=title_color,
    )

    # 重新基于真实 draw 定义尺寸函数
    def get_text_size(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 10+. 按顺序绘制各个部分
    y0 = logo_y + logo_size + 30
    y0 = draw_section("🎣 基礎與核心玩法", basic, y0, cols=3)
    y0 = draw_section("🎒 背包與資產管理", inventory, y0, cols=3)
    y0 = draw_section("🛒 商店與市場", market, y0, cols=3)
    y0 = draw_section("🎰 抽卡與概率玩法", gacha, y0, cols=3)
    y0 = draw_section("🎲 骰寶遊戲", sicbo, y0, cols=3)
    y0 = draw_section("👥 社交功能", social, y0, cols=2)
    y0 = draw_section("📈 大宗商品交易所", exchange, y0, cols=2)
    y0 = draw_section("⚙️ 管理後台（管理員）", admin, y0, cols=2)

    # 添加底部信息
    footer_y = y0 + 20
    footer_text = "💡 提示：命令中的 [ID] 表示必填參數，<> 表示可選參數"
    footer_w, _ = get_text_size_cached(footer_text, desc_font)
    draw_text_smart(
        draw,
        (width // 2 - footer_w // 2, footer_y),
        footer_text,
        font=desc_font,
        fill=(120, 120, 120),
    )

    # 11. 保存（高度已自适应，无需再次裁剪）
    final_height = footer_y + 48
    image = image.crop((0, 0, width, final_height))

    return image


def draw_help_images_split() -> list[Image.Image]:
    """将帮助图拆分为两张，降低平台压缩导致的可读性问题。"""
    img = draw_help_image()
    w, h = img.size
    if h <= 1200:
        return [img]

    # 中线附近带少量重叠，避免切到标题行
    overlap = 48
    mid = h // 2
    top_end = min(h, mid + overlap)
    bottom_start = max(0, mid - overlap)

    top = img.crop((0, 0, w, top_end))
    bottom = img.crop((0, bottom_start, w, h))
    return [top, bottom]
