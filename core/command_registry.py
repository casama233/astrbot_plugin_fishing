"""
指令註冊模組 - 將 main.py 中的指令註冊邏輯模組化

這個模組提供了統一的指令註冊接口，讓 main.py 更簡潔。
"""

from astrbot.api.event import filter, AstrMessageEvent
from typing import TYPE_CHECKING, Callable, Any, List, Dict

if TYPE_CHECKING:
    from ..main import FishingPlugin


def register_commands(plugin_class: type) -> type:
    """
    裝飾器：為插件類註冊所有指令

    使用方式：
        @register_commands
        class FishingPlugin(Star):
            pass
    """
    return plugin_class


def create_command_decorator(
    command: str, alias: List[str] = None, permission: str = None
) -> Callable:
    """
    創建指令裝飾器的工廠函數

    Args:
        command: 主指令名
        alias: 別名列表
        permission: 權限要求
    """

    def decorator(func: Callable) -> Callable:
        if alias:
            func = filter.command(command, alias=alias)(func)
        else:
            func = filter.command(command)(func)
        return func

    return decorator


COMMAND_GROUPS = {
    "core": {
        "name": "核心玩法",
        "icon": "🌊",
        "commands": ["註冊", "簽到", "釣魚", "狀態", "背包", "釣魚幫助"],
    },
    "inventory": {
        "name": "背包與養成",
        "icon": "🎒",
        "commands": ["魚塘", "水族箱", "魚竿", "飾品", "道具", "使用", "精煉", "出售"],
    },
    "economy": {
        "name": "經濟系統",
        "icon": "💰",
        "commands": ["商店", "市場", "交易所", "全部賣出"],
    },
    "gacha": {
        "name": "抽卡與概率",
        "icon": "🎰",
        "commands": ["抽卡", "十連", "擦彈", "命運之輪"],
    },
    "sicbo": {
        "name": "骰寶",
        "icon": "🎲",
        "commands": ["骰寶", "骰寶下注"],
    },
    "social": {
        "name": "社交互動",
        "icon": "👥",
        "commands": ["排行榜", "偷魚", "電魚", "紅包"],
    },
    "tutorial": {
        "name": "新手引導",
        "icon": "📖",
        "commands": ["教程"],
    },
    "unified": {
        "name": "統一入口",
        "icon": "⚡",
        "commands": ["賣出", "裝備"],
    },
}


def get_command_help_text() -> str:
    """生成指令幫助文本"""
    lines = ["📖 指令分類導航", "═" * 30]

    for group_key, group_info in COMMAND_GROUPS.items():
        icon = group_info["icon"]
        name = group_info["name"]
        cmds = group_info["commands"]
        cmd_list = "、".join(f"/{c}" for c in cmds[:5])
        if len(cmds) > 5:
            cmd_list += f" 等{len(cmds)}個"
        lines.append(f"{icon} {name}：{cmd_list}")

    lines.append("")
    lines.append("💡 輸入 /釣魚幫助 查看完整指令列表")

    return "\n".join(lines)


def get_category_for_command(command: str) -> str:
    """根據指令名獲取所屬分類"""
    for group_key, group_info in COMMAND_GROUPS.items():
        if command in group_info["commands"]:
            return group_key
    return "other"
