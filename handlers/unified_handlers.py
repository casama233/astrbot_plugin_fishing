from astrbot.api.event import AstrMessageEvent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def unified_sell(plugin: "FishingPlugin", event: AstrMessageEvent):
    """統一賣出入口 - 整合多個賣出指令"""
    user_id = plugin._get_effective_user_id(event)

    if not plugin.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    sub_cmd = args[1].lower() if len(args) > 1 else ""

    from . import market_handlers, inventory_handlers

    if sub_cmd in ["全部", "all", "所有"]:
        async for r in market_handlers.sell_all(plugin, event):
            yield r
    elif sub_cmd in ["保留", "keep"]:
        async for r in market_handlers.sell_keep(plugin, event):
            yield r
    elif sub_cmd in ["砸鍋賣鐵", "全部清空", "清空"]:
        async for r in market_handlers.sell_everything(plugin, event):
            yield r
    elif sub_cmd in ["稀有度", "rarity"]:
        async for r in market_handlers.sell_by_rarity(plugin, event):
            yield r
    elif sub_cmd in ["魚竿", "rod", "魚竿全部"]:
        async for r in market_handlers.sell_all_rods(plugin, event):
            yield r
    elif sub_cmd in ["飾品", "accessory", "飾品全部"]:
        async for r in market_handlers.sell_all_accessories(plugin, event):
            yield r
    elif sub_cmd:
        event.message_str = f"/出售 {sub_cmd}"
        async for r in inventory_handlers.sell_item(plugin, event):
            yield r
    else:
        help_text = """💼 【賣出指令幫助】

可用子命令：
• /賣出 全部 - 賣出魚塘所有魚
• /賣出 保留 - 賣出所有魚但每種保留一條
• /賣出 砸鍋賣鐵 - 出售所有未鎖定的魚竿、飾品和魚
• /賣出 稀有度 3 4 5 - 按稀有度賣出魚
• /賣出 魚竿 - 賣出所有未裝備的魚竿
• /賣出 飾品 - 賣出所有未裝備的飾品
• /賣出 F短碼 - 賣出指定物品

💡 快捷指令：
• /全部賣出 = /賣出 全部
• /砸鍋賣鐵 = /賣出 砸鍋賣鐵"""
        yield event.plain_result(help_text)


async def unified_fish_pond(plugin: "FishingPlugin", event: AstrMessageEvent):
    """統一魚塘入口 - 整合魚塘相關指令"""
    user_id = plugin._get_effective_user_id(event)

    if not plugin.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    sub_cmd = args[1].lower() if len(args) > 1 else ""

    from . import aquarium_handlers, inventory_handlers

    if sub_cmd in ["容量", "容量查詢", "大小"]:
        async for r in inventory_handlers.pond_capacity(plugin, event):
            yield r
    elif sub_cmd in ["升級", "upgrade", "擴容"]:
        async for r in inventory_handlers.upgrade_pond(plugin, event):
            yield r
    elif sub_cmd in ["偷看", "peek"]:
        event.message_str = f"/偷看魚塘 {' '.join(args[2:]) if len(args) > 2 else ''}"
        async for r in inventory_handlers.peek_pond(plugin, event):
            yield r
    elif sub_cmd in ["水族箱", "aquarium"]:
        async for r in aquarium_handlers.view_aquarium(plugin, event):
            yield r
    elif sub_cmd in ["放入", "add"]:
        if len(args) >= 3:
            event.message_str = f"/放入水族箱 {args[2]}"
            async for r in aquarium_handlers.add_to_aquarium(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/魚塘 放入 F短碼")
    elif sub_cmd in ["移出", "remove"]:
        if len(args) >= 3:
            event.message_str = f"/移出水族箱 {args[2]}"
            async for r in aquarium_handlers.remove_from_aquarium(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/魚塘 移出 F短碼")
    else:
        async for r in inventory_handlers.pond(plugin, event):
            yield r


async def unified_equipment(plugin: "FishingPlugin", event: AstrMessageEvent):
    """統一裝備入口 - 整合魚竿和飾品指令"""
    user_id = plugin._get_effective_user_id(event)

    if not plugin.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    sub_cmd = args[1].lower() if len(args) > 1 else ""

    from . import inventory_handlers

    if sub_cmd in ["魚竿", "rod"]:
        async for r in inventory_handlers.view_rods(plugin, event):
            yield r
    elif sub_cmd in ["飾品", "accessory"]:
        async for r in inventory_handlers.view_accessories(plugin, event):
            yield r
    elif sub_cmd in ["道具", "item", "物品"]:
        async for r in inventory_handlers.view_items(plugin, event):
            yield r
    elif sub_cmd in ["魚餌", "bait"]:
        async for r in inventory_handlers.view_baits(plugin, event):
            yield r
    elif sub_cmd in ["精煉", "refine"]:
        if len(args) >= 3:
            event.message_str = f"/精煉 {args[2]}"
            async for r in inventory_handlers.refine_equipment(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/裝備 精煉 R短碼 或 A短碼")
    elif sub_cmd in ["鎖定", "lock"]:
        if len(args) >= 3:
            event.message_str = f"/鎖定 {args[2]}"
            async for r in inventory_handlers.lock_equipment(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/裝備 鎖定 R短碼 或 A短碼")
    elif sub_cmd in ["解鎖", "unlock"]:
        if len(args) >= 3:
            event.message_str = f"/解鎖 {args[2]}"
            async for r in inventory_handlers.unlock_equipment(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/裝備 解鎖 R短碼 或 A短碼")
    else:
        help_text = """⚔️ 【裝備指令幫助】

可用子命令：
• /裝備 魚竿 - 查看所有魚竿
• /裝備 飾品 - 查看所有飾品
• /裝備 道具 - 查看所有道具
• /裝備 魚餌 - 查看所有魚餌
• /裝備 精煉 短碼 - 精煉裝備
• /裝備 鎖定 短碼 - 鎖定裝備（防止誤賣）
• /裝備 解鎖 短碼 - 解鎖裝備

💡 快捷指令：
• /魚竿 = /裝備 魚竿
• /飾品 = /裝備 飾品
• /精煉 Rxxx = /裝備 精煉 Rxxx"""
        yield event.plain_result(help_text)


async def unified_bag(plugin: "FishingPlugin", event: AstrMessageEvent):
    """統一背包入口 - 整合背包相關指令"""
    user_id = plugin._get_effective_user_id(event)

    if not plugin.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    sub_cmd = args[1].lower() if len(args) > 1 else ""

    from . import inventory_handlers

    if sub_cmd in ["使用", "use", "裝備"]:
        if len(args) >= 3:
            event.message_str = f"/使用 {args[2]}"
            async for r in inventory_handlers.use_item(plugin, event):
                yield r
        else:
            yield event.plain_result("❌ 用法：/背包 使用 短碼")
    elif sub_cmd in ["開啟", "open"]:
        event.message_str = "/開啟全部錢袋"
        async for r in inventory_handlers.open_all_pouches(plugin, event):
            yield r
    else:
        async for r in inventory_handlers.view_inventory(plugin, event):
            yield r


async def quick_action(plugin: "FishingPlugin", event: AstrMessageEvent):
    """快捷操作入口 - 常用操作的一鍵入口"""
    user_id = plugin._get_effective_user_id(event)

    if not plugin.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    action = args[1].lower() if len(args) > 1 else ""

    from . import common_handlers, fishing_handlers, market_handlers

    if action in ["簽到", "簽到領取"]:
        event.message_str = "/簽到"
        async for r in common_handlers.sign_in(plugin, event):
            yield r
    elif action in ["釣魚", "釣"]:
        event.message_str = "/釣魚"
        async for r in fishing_handlers.fish(plugin, event):
            yield r
    elif action in ["賣魚", "賣出"]:
        event.message_str = "/全部賣出"
        async for r in market_handlers.sell_all(plugin, event):
            yield r
    elif action in ["狀態", "查看"]:
        event.message_str = "/狀態"
        async for r in common_handlers.state(plugin, event):
            yield r
    elif action in ["商店", "買"]:
        event.message_str = "/商店"
        async for r in market_handlers.view_shop(plugin, event):
            yield r
    else:
        help_text = """⚡ 【快捷操作】

常用一鍵指令：
• /快 簽到 - 快速簽到
• /快 釣魚 - 快速釣魚
• /快 賣魚 - 快速賣出所有魚
• /快 狀態 - 快速查看狀態
• /快 商店 - 快速打開商店

💡 新手建議：
1. 先用 /教程 查看新手任務
2. 每天簽到領取金幣
3. 釣魚 → 賣魚 → 買魚餌 循環"""
        yield event.plain_result(help_text)
