"""
文本处理工具函数
优化文本测量、换行和渲染性能
"""

import os
import platform
import unicodedata
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict


def get_text_size_cached(
    text: str,
    font: ImageFont.FreeTypeFont,
    cache: Optional[Dict[str, Tuple[int, int]]] = None,
) -> Tuple[int, int]:
    """
    带缓存的文本尺寸测量，避免重复计算

    Args:
        text: 要测量的文本
        font: 字体对象
        cache: 可选的缓存字典

    Returns:
        (width, height): 文本尺寸
    """
    if cache is None:
        # 如果没有提供缓存，直接测量
        return _measure_text_size(text, font)

    # 使用缓存
    cache_key = f"{text}_{font.size}"
    if cache_key not in cache:
        cache[cache_key] = _measure_text_size(text, font)

    return cache[cache_key]


def _measure_text_size(text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """
    测量文本尺寸的内部函数
    """
    # 创建临时图像进行测量
    temp_img = Image.new("RGB", (1, 1), (255, 255, 255))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def wrap_text_by_width_optimized(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    cache: Optional[Dict[str, Tuple[int, int]]] = None,
) -> List[str]:
    """
    优化的文本按宽度换行函数

    Args:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度
        cache: 可选的缓存字典

    Returns:
        List[str]: 换行后的文本行列表
    """
    if not text:
        return []

    # 如果文本很短，直接返回
    text_width, _ = get_text_size_cached(text, font, cache)
    if text_width <= max_width:
        return [text]

    lines = []
    current_line = ""

    # 按字符分割，但优化测量频率
    for char in text:
        test_line = current_line + char
        test_width, _ = get_text_size_cached(test_line, font, cache)

        if test_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char

    if current_line:
        lines.append(current_line)

    return lines


def wrap_text_by_width_with_hyphenation(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    cache: Optional[Dict[str, Tuple[int, int]]] = None,
) -> List[str]:
    """
    带连字符的文本换行，适用于英文文本

    Args:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度
        cache: 可选的缓存字典

    Returns:
        List[str]: 换行后的文本行列表
    """
    if not text:
        return []

    # 先尝试简单换行
    lines = wrap_text_by_width_optimized(text, font, max_width, cache)

    # 如果只有一行，直接返回
    if len(lines) <= 1:
        return lines

    # 对每行进行连字符优化
    optimized_lines = []
    for line in lines:
        if len(line) > 10 and " " in line:  # 只对较长的行进行连字符处理
            words = line.split(" ")
            if len(words) > 1:
                # 尝试在单词边界换行
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_width, _ = get_text_size_cached(test_line, font, cache)

                    if test_width <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            optimized_lines.append(current_line)
                        current_line = word

                if current_line:
                    optimized_lines.append(current_line)
            else:
                optimized_lines.append(line)
        else:
            optimized_lines.append(line)

    return optimized_lines


def normalize_display_text(text: Optional[str]) -> str:
    if not text:
        return ""
    t = str(text)
    t = t.replace("｜", "，").replace("|", "，")
    t = t.replace(" / ", "、").replace(" /", "、").replace("/ ", "、")
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()


def create_text_cache() -> dict:
    """
    创建文本测量缓存

    Returns:
        dict: 空的缓存字典
    """
    return {}


def clear_text_cache(cache: dict) -> None:
    """
    清空文本测量缓存

    Args:
        cache: 要清空的缓存字典
    """
    cache.clear()


def get_text_metrics_batch(
    texts: List[str],
    font: ImageFont.FreeTypeFont,
    cache: Optional[Dict[str, Tuple[int, int]]] = None,
) -> List[Tuple[int, int]]:
    """
    批量测量文本尺寸，提高效率

    Args:
        texts: 文本列表
        font: 字体对象
        cache: 可选的缓存字典

    Returns:
        List[Tuple[int, int]]: 每个文本的尺寸列表
    """
    if cache is None:
        return [_measure_text_size(text, font) for text in texts]

    results = []
    for text in texts:
        results.append(get_text_size_cached(text, font, cache))

    return results


def _find_cjk_font(exclude_path: Optional[str] = None) -> Optional[str]:
    """
    查找CJK字体路径（支持繁体中文字符）

    Returns:
        字体文件路径，如果找不到则返回None
    """
    resource_dir = os.path.join(os.path.dirname(__file__), "resource")

    # 使用项目资源目录中的字体（按优先级排序）
    cjk_fonts = [
        "zpix.ttf",  # Zpix（优先，覆盖中日韩与符号）
        "RenOuFangSong-16.ttf",  # 仁欧仿宋（优先，繁简通用）
        "NotoSansTC-Bold.ttf",  # Noto Sans 繁体中文（首选后备）
        "NotoSansJP-Bold.ttf",  # Noto Sans 日文（后备）
        "FashionBitmap16_0.091.ttf",  # Fashion Bitmap（后备）
        "DouyinSansBold.otf",  # 兜底字体
    ]

    exclude_abs = os.path.abspath(exclude_path) if exclude_path else None

    for font_name in cjk_fonts:
        font_path = os.path.join(resource_dir, font_name)
        if not os.path.exists(font_path):
            continue
        if exclude_abs and os.path.abspath(font_path) == exclude_abs:
            continue
        if os.path.exists(font_path):
            return font_path

    return None


def get_primary_font_path() -> str:
    """获取主字体路径（优先保证繁体中文可渲染）。"""
    resource_dir = os.path.join(os.path.dirname(__file__), "resource")

    candidates = [
        os.path.join(resource_dir, "zpix.ttf"),
        os.path.join(resource_dir, "RenOuFangSong-16.ttf"),
        os.path.join(resource_dir, "NotoSansTC-Bold.ttf"),
        os.path.join(resource_dir, "NotoSansJP-Bold.ttf"),
        os.path.join(resource_dir, "FashionBitmap16_0.091.ttf"),
        os.path.join(resource_dir, "DouyinSansBold.otf"),
    ]

    for p in candidates:
        if os.path.exists(p):
            return p

    # 最后兜底（保持原行为）
    return os.path.join(resource_dir, "DouyinSansBold.otf")


class FontWithFallback:
    """
    带自动回退的字体包装类
    当主字体不支持某个字符时，自动使用系统CJK字体
    """

    def __init__(
        self,
        primary_font: ImageFont.FreeTypeFont,
        fallback_font: Optional[ImageFont.FreeTypeFont] = None,
    ):
        self.primary_font = primary_font
        self.fallback_font = fallback_font
        self._char_cache = {}  # 缓存字符到字体的映射

    def _is_zero_width_modifier(self, char: str) -> bool:
        """判断零宽修饰符（如 VS16、ZWJ、组合符号）。"""
        if not char:
            return False
        code = ord(char)
        if code == 0x200D or code == 0x20E3 or 0xFE00 <= code <= 0xFE0F:
            return True
        cat = unicodedata.category(char)
        return cat in {"Mn", "Me", "Cf"}

    def _is_cjk_char(self, char: str) -> bool:
        """判断是否为CJK字符（中文、日文、韩文）"""
        if not char:
            return False
        code = ord(char)
        # CJK统一汉字、CJK扩展A/B/C/D/E、CJK兼容汉字、日文平假名/片假名、韩文等
        return (
            0x4E00 <= code <= 0x9FFF  # CJK统一汉字
            or 0x3400 <= code <= 0x4DBF  # CJK扩展A
            or 0x20000 <= code <= 0x2A6DF  # CJK扩展B
            or 0x2A700 <= code <= 0x2B73F  # CJK扩展C
            or 0x2B740 <= code <= 0x2B81F  # CJK扩展D
            or 0x2B820 <= code <= 0x2CEAF  # CJK扩展E
            or 0x2CEB0 <= code <= 0x2EBEF  # CJK扩展F
            or 0x30000 <= code <= 0x3134F  # CJK扩展G
            or 0x31350 <= code <= 0x323AF  # CJK扩展H
            or 0x2EBF0 <= code <= 0x2EE5F  # CJK扩展I
            or 0xF900 <= code <= 0xFAFF  # CJK兼容汉字
            or 0x2F800 <= code <= 0x2FA1F  # CJK兼容扩展补充
            or 0x3040 <= code <= 0x309F  # 日文平假名
            or 0x30A0 <= code <= 0x30FF  # 日文片假名
            or 0xAC00 <= code <= 0xD7AF  # 韩文音节
        )

    def _is_cjk_punctuation(self, char: str) -> bool:
        """判断是否为CJK标点符号（应优先使用回退字体）"""
        if not char:
            return False
        code = ord(char)
        return (
            0x3000 <= code <= 0x303F  # CJK Symbols and Punctuation
            or 0xFF00 <= code <= 0xFFEF  # Halfwidth and Fullwidth Forms
        )

    def _is_emoji_char(self, char: str) -> bool:
        """判断是否为常见 emoji 字符范围。"""
        if not char:
            return False
        code = ord(char)
        return (
            0x1F300 <= code <= 0x1F5FF  # Misc Symbols and Pictographs
            or 0x1F600 <= code <= 0x1F64F  # Emoticons
            or 0x1F680 <= code <= 0x1F6FF  # Transport and Map
            or 0x2300 <= code <= 0x23FF  # Misc Technical (含⌨)
            or 0x1F700 <= code <= 0x1F77F  # Alchemical Symbols
            or 0x1F780 <= code <= 0x1F7FF  # Geometric Shapes Extended
            or 0x1F800 <= code <= 0x1F8FF  # Supplemental Arrows-C
            or 0x1F900 <= code <= 0x1F9FF  # Supplemental Symbols and Pictographs
            or 0x1FA00 <= code <= 0x1FAFF  # Symbols and Pictographs Extended-A
            or 0x2600 <= code <= 0x26FF  # Misc Symbols
            or 0x2700 <= code <= 0x27BF  # Dingbats
            or 0xFE00 <= code <= 0xFE0F  # Variation Selectors (emoji style)
        )

    def _get_font_for_char(self, char: str) -> ImageFont.FreeTypeFont:
        """
        选择字符的渲染字体

        策略：
        1. mask 为空 → 回退字体
        2. CJK 字符且 bbox 无效 → 回退字体
        3. 其他 → 主字体
        """
        if char in self._char_cache:
            return self._char_cache[char]

        if self._is_zero_width_modifier(char):
            self._char_cache[char] = self.primary_font
            return self.primary_font

        def _font_can_render(
            target_font: ImageFont.FreeTypeFont, target_char: str
        ) -> bool:
            try:
                mask = target_font.getmask(target_char)
                if mask.size[0] == 0 or mask.size[1] == 0:
                    return False
                bbox = mask.getbbox()
                if not (bbox is not None and bbox[2] > bbox[0] and bbox[3] > bbox[1]):
                    return False

                # 通用缺字判断：和常见 notdef 占位字形一致时视为不可渲染
                for probe in ("□", "�", "?"):
                    try:
                        probe_mask = target_font.getmask(probe)
                        if (
                            probe_mask.size == mask.size
                            and probe_mask.tobytes() == mask.tobytes()
                        ):
                            return False
                    except Exception:
                        continue

                return True
            except Exception:
                return False

        try:
            fallback_font = self.fallback_font
            primary_ok = _font_can_render(self.primary_font, char)
            fallback_ok = (
                _font_can_render(fallback_font, char) if fallback_font else False
            )

            if primary_ok and not fallback_ok:
                self._char_cache[char] = self.primary_font
                return self.primary_font
            if fallback_ok and not primary_ok:
                if fallback_font:
                    self._char_cache[char] = fallback_font
                    return fallback_font

            if primary_ok and fallback_ok:
                # 通用策略：
                # - CJK（含标点）优先回退字体（字形覆盖更完整）
                # - 其他字符优先主字体（保持英文/数字/emoji 风格一致）
                if self._is_cjk_char(char) or self._is_cjk_punctuation(char):
                    if fallback_font:
                        self._char_cache[char] = fallback_font
                        return fallback_font
                if self._is_emoji_char(char):
                    self._char_cache[char] = self.primary_font
                    return self.primary_font
                self._char_cache[char] = self.primary_font
                return self.primary_font

            self._char_cache[char] = self.primary_font
            return self.primary_font

        except Exception:
            # 异常时使用回退字体
            font = self.fallback_font if self.fallback_font else self.primary_font
            self._char_cache[char] = font
            return font

    def getmask(self, text, mode="", *args, **kwargs):
        """获取文本的mask，自动处理回退"""
        if not self.fallback_font:
            return self.primary_font.getmask(text, mode, *args, **kwargs)

        if not text:
            return self.primary_font.getmask(text, mode, *args, **kwargs)

        # 单字符时按字符级策略选择字体
        if len(text) == 1:
            selected = self._get_font_for_char(text)
            return selected.getmask(text, mode, *args, **kwargs)

        def _coverage_score(target_font, target_text: str) -> int:
            score = 0
            for ch in target_text:
                if self._is_zero_width_modifier(ch):
                    continue
                try:
                    mask = target_font.getmask(ch)
                    if (
                        mask.size[0] > 0
                        and mask.size[1] > 0
                        and mask.getbbox() is not None
                    ):
                        score += 1
                except Exception:
                    continue
            return score

        p_score = _coverage_score(self.primary_font, text)
        f_score = _coverage_score(self.fallback_font, text)
        if f_score > p_score:
            return self.fallback_font.getmask(text, mode, *args, **kwargs)
        if p_score > f_score:
            return self.primary_font.getmask(text, mode, *args, **kwargs)

        # 若任一字符更适合回退字体，则整体使用回退字体渲染
        for ch in text:
            if self._get_font_for_char(ch) is self.fallback_font:
                return self.fallback_font.getmask(text, mode, *args, **kwargs)

        return self.primary_font.getmask(text, mode, *args, **kwargs)

    def getbbox(self, text, *args, **kwargs):
        """获取文本边界框"""
        if self.fallback_font and text:
            if any(self._get_font_for_char(ch) is self.fallback_font for ch in text):
                return self.fallback_font.getbbox(text, *args, **kwargs)
        return self.primary_font.getbbox(text, *args, **kwargs)

    def getlength(self, text, *args, **kwargs):
        """获取文本长度，保证 CJK 文本测量与实际渲染字体一致"""
        if self.fallback_font and text:
            if any(self._get_font_for_char(ch) is self.fallback_font for ch in text):
                return self.fallback_font.getlength(text, *args, **kwargs)
        return self.primary_font.getlength(text, *args, **kwargs)

    def __getattr__(self, name):
        """代理其他属性到主字体"""
        return getattr(self.primary_font, name)


def load_font_with_cjk_fallback(font_path: str, size: int) -> FontWithFallback:
    """
    加载字体，自动添加CJK回退支持

    Args:
        font_path: 主字体文件路径
        size: 字体大小

    Returns:
        FontWithFallback: 带回退的字体对象
    """
    # 加载主字体：优先调用方指定，其次使用项目主字体
    primary_path = (
        font_path
        if (font_path and os.path.exists(font_path))
        else get_primary_font_path()
    )
    try:
        primary_font = ImageFont.truetype(primary_path, size)
    except Exception:
        primary_font = ImageFont.load_default()  # type: ignore

    # 用户指定 zpix 作为统一字体时，不启用回退，确保全局都使用同一款字体
    if os.path.basename(primary_path).lower() == "zpix.ttf":
        return FontWithFallback(primary_font, None)  # type: ignore

    # 加载 CJK 字体作为回退（仅使用项目资源中的字体，不查询系统）
    fallback_font = None
    cjk_font_path = _find_cjk_font(exclude_path=primary_path)
    if cjk_font_path:
        try:
            fallback_font = ImageFont.truetype(cjk_font_path, size)
        except Exception as e:
            # 如果加载失败，记录错误但不抛出异常
            pass

    return FontWithFallback(primary_font, fallback_font)  # type: ignore


def draw_text_smart(
    draw: ImageDraw.ImageDraw,
    position: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    """
    智能文本绘制函数，自动处理字体回退

    如果传入的font是FontWithFallback类型，会自动使用回退字体处理缺失字符
    否则直接使用普通绘制

    Args:
        draw: ImageDraw对象
        position: 文本位置 (x, y)
        text: 要绘制的文本
        font: 字体对象（可以是FontWithFallback或普通字体）
        fill: 文本颜色
    """
    # 如果是FontWithFallback类型，需要特殊处理
    if isinstance(font, FontWithFallback):
        if not font.fallback_font:
            # 没有回退字体，直接绘制
            draw.text(position, text, font=font.primary_font, fill=fill)
            return

        # 检查是否所有字符都能用主字体渲染
        need_fallback = False
        for char in text:
            char_font = font._get_font_for_char(char)
            if char_font != font.primary_font:
                need_fallback = True
                break

        # 如果所有字符都能用主字体，直接一次性绘制（保持原始间距）
        if not need_fallback:
            draw.text(position, text, font=font.primary_font, fill=fill)
            return

        # 需要回退字体，逐个字符检查并绘制
        x, y = position
        current_x = x

        # 创建临时图像用于测量（复用以提高效率）
        temp_img = Image.new("RGB", (200, 100), (255, 255, 255))
        temp_draw = ImageDraw.Draw(temp_img)

        # 计算中线对齐：使用主字体的标准字符的垂直中心作为参考
        # 这确保无论使用哪个字体渲染，字符都在同一水平视觉中心线上
        # 使用"A"作为参考字符（标准拉丁字母大写，所有字体都支持）
        reference_bbox = temp_draw.textbbox((0, 0), "A", font=font.primary_font)
        reference_center_y = (reference_bbox[1] + reference_bbox[3]) / 2  # 垂直中心

        for i, char in enumerate(text):
            code = ord(char)

            # 跳过零宽修饰符，避免把 emoji 组合拆开后产生额外占位宽度
            # FE0E/FE0F: 变体选择符；200D: ZWJ；20E3: 键帽组合符
            if code == 0x200D or code == 0x20E3 or 0xFE00 <= code <= 0xFE0F:
                continue

            # 获取适合该字符的字体
            char_font = font._get_font_for_char(char)

            # 获取当前字符的bbox
            char_bbox = temp_draw.textbbox((0, 0), char, font=char_font)
            char_center_y = (char_bbox[1] + char_bbox[3]) / 2  # 当前字符的垂直中心

            # 计算y坐标：让所有字符的垂直中心对齐到参考中心
            # 基本思路：字符中心 = y + reference_center_y
            # 所以：char_y = y + (reference_center_y - char_center_y)
            char_y = y + (reference_center_y - char_center_y)

            # 测量字符宽度：直接使用渲染该字符的字体测量
            try:
                if hasattr(char_font, "getlength"):
                    char_width = int(char_font.getlength(char))
                else:
                    bbox = temp_draw.textbbox((0, 0), char, font=char_font)
                    char_width = bbox[2] - bbox[0]

                # 如果测量宽度依然为0，使用字体大小估算（保底）
                if char_width <= 0:
                    char_width = (
                        font.primary_font.size // 2
                        if ord(char) < 128
                        else font.primary_font.size
                    )
            except Exception:
                char_width = (
                    font.primary_font.size // 2
                    if ord(char) < 128
                    else font.primary_font.size
                )

            # 绘制字符（使用调整后的y坐标，确保基线对齐）
            draw.text((current_x, char_y), char, font=char_font, fill=fill)
            current_x += char_width
    else:
        # 普通字体，直接绘制
        draw.text(position, text, font=font, fill=fill)
