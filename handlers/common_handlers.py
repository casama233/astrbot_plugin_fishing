import os
import re
from astrbot.api.event import filter, AstrMessageEvent
from ..draw.state import draw_state_image, get_user_state_data
from ..core.utils import get_now
from ..utils import safe_datetime_handler, parse_target_user_id, parse_amount
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def register_user(self: "FishingPlugin", event: AstrMessageEvent):
    """註冊用戶命令"""
    user_id = self._get_effective_user_id(event)
    nickname = (
        event.get_sender_name() if event.get_sender_name() is not None else user_id
    )
    if result := self.user_service.register(user_id, nickname):
        yield event.plain_result(result["message"])
        if result.get("success", False):
            yield event.plain_result(
                "🌊 【新手引導：你在海邊醒來】\n\n"
                "歡迎來到釣魚世界！從這裡開始你的冒險：\n\n"
                "📌 生存與起步\n"
                "  /簽到、/釣魚、/狀態\n\n"
                "🎒 資源管理\n"
                "  /背包、/魚塘、/出售 F 短碼\n\n"
                "⚔️ 裝備成長\n"
                "  /魚竿、/飾品、/精煉 R/A 短碼\n\n"
                "💰 經濟路線\n"
                "  /商店、/市場、/交易所\n\n"
                "🏆 社交對抗\n"
                "  /排行榜、/偷魚 @用戶、/電魚 @用戶\n\n"
                "📘 完整導航：/釣魚幫助\n"
                "💡 建議流程：簽到 → 釣魚 → 賣魚 → 買基礎魚餌"
            )
    else:
        yield event.plain_result("❌ 出錯啦！請稍後再試。")


async def sign_in(self: "FishingPlugin", event: AstrMessageEvent):
    """签到"""
    user_id = self._get_effective_user_id(event)
    result = self.user_service.daily_sign_in(user_id)
    if result["success"]:
        yield event.plain_result(result["message"])


async def state(self: "FishingPlugin", event: AstrMessageEvent):
    """查看用户状态"""
    user_id = self._get_effective_user_id(event)

    # 调用新的数据获取函数
    user_data = get_user_state_data(
        self.user_repo,
        self.inventory_repo,
        self.item_template_repo,
        self.log_repo,
        self.buff_repo,
        self.game_config,
        user_id,
    )

    if not user_data:
        yield event.plain_result("❌ 用戶不存在\n\n請先註冊開始遊戲：\n  /註冊")
        return
    # 尝试提取平台头像URL（优先用于Discord等非QQ平台）
    avatar_url = None
    try:
        for method_name in ["get_sender_avatar", "get_sender_avatar_url"]:
            if hasattr(event, method_name):
                value = getattr(event, method_name)()
                if value:
                    avatar_url = str(value)
                    break

        if not avatar_url:
            msg_obj = getattr(event, "message_obj", None)
            if msg_obj is not None:
                for attr in [
                    "avatar",
                    "avatar_url",
                    "sender_avatar",
                    "sender_avatar_url",
                ]:
                    if hasattr(msg_obj, attr):
                        value = getattr(msg_obj, attr)
                        if value:
                            avatar_url = str(value)
                            break

        if not avatar_url:
            msg_obj = getattr(event, "message_obj", None)
            sender = getattr(msg_obj, "sender", None) if msg_obj is not None else None
            if sender is not None:
                for attr in [
                    "avatar",
                    "avatar_url",
                    "user_avatar",
                    "profile_image_url",
                ]:
                    if hasattr(sender, attr):
                        value = getattr(sender, attr)
                        if value:
                            avatar_url = str(value)
                            break
    except Exception:
        avatar_url = None

    # 生成状态图像
    image = await draw_state_image(user_data, self.data_dir, avatar_url=avatar_url)
    # 保存图像到临时文件
    image_path = os.path.join(self.tmp_dir, "user_status.png")
    image.save(image_path)
    yield event.image_result(image_path)
    try:
        user = self.user_repo.get_by_id(user_id)
        coins = user.coins if user else 0
        bait_info = self.inventory_service.get_user_bait_inventory(user_id) or {}
        baits = bait_info.get("baits", []) or []
        has_bait = any(int(b.get("quantity", 0) or 0) > 0 for b in baits)
        state_info = self.user_service.get_user_state(user_id) or {}
        auto_fishing = bool(state_info.get("user", {}).get("is_auto_fishing", False))

        tips = ["⌨️ 状态页智能提示"]
        if not has_bait:
            tips.append("- 你当前没有鱼饵：/商店（优先补基础饵）")
        else:
            tips.append("- 可以继续刷资源：/钓鱼")
        if coins < 200:
            tips.append("- 金币偏少：/签到 或 /全部卖出")
        if auto_fishing:
            tips.append("- 自动钓鱼已开启：/自动钓鱼（可关闭）")
        tips.append("- 装备养成：/鱼竿、/饰品、/精炼 R/A短码")
        tips.append("- 交易流转：/市场、/交易所")
        tips.append("💡 快捷总览：/钓鱼帮助 速查")
        yield event.plain_result("\n".join(tips[:7]))
    except Exception:
        yield event.plain_result(
            "⌨️ 快捷操作\n"
            "- /钓鱼：继续捕鱼\n"
            "- /背包：查看全部物品\n"
            "- /商店、/市场：补给与交易\n"
            "💡 快捷总览：/钓鱼帮助 速查"
        )


async def fishing_log(self: "FishingPlugin", event: AstrMessageEvent):
    """查看钓鱼记录"""
    user_id = self._get_effective_user_id(event)
    if result := self.fishing_service.get_user_fish_log(user_id):
        if result["success"]:
            records = result["records"]
            if not records:
                yield event.plain_result("❌ 您还没有钓鱼记录。")
                return
            message = "【📜 钓鱼记录】：\n"
            for record in records:
                message += (
                    f" - {record['fish_name']} ({'★' * record['fish_rarity']})\n"
                    f" - ⚖️重量: {record['fish_weight']} 克 - 💰价值: {record['fish_value']} 金币\n"
                    f" - 🔧装备： {record['accessory']} & {record['rod']} | 🎣鱼饵: {record['bait']}\n"
                    f" - 钓鱼时间: {safe_datetime_handler(record['timestamp'])}\n"
                )
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 获取钓鱼记录失败：{result['message']}")
    else:
        yield event.plain_result("❌ 出错啦！请稍后再试。")


async def fishing_help(self: "FishingPlugin", event: AstrMessageEvent):
    """显示钓鱼插件帮助信息"""
    pages = {
        1: """【🎣 钓鱼帮助 1/10：新手与核心】
提示：命令中的 [参数] 为必填，<参数> 为可选。

- /注册
- /钓鱼
- /签到
- /自动钓鱼
- /钓鱼区域 [ID]（别名：/区域 [ID]）
- /钓鱼记录（别名：/钓鱼日志、/钓鱼历史）
- /钓鱼纪录（别名写法）
- /状态（别名：/我的状态）
- /背包（别名：/查看背包、/我的背包）
- /钓鱼帮助（别名：/钓鱼菜单、/菜单）

标准子命令写法（AstrBot）
- /fish register
- /fish signin
- /fish bag
- /fish status
- /fish pond
- /fish shop
- /fish market
- /fish help
- /fish sicbo
- /fish bet_pt

示例：
- /注册
- /签到
- /钓鱼
- /钓鱼区域 2

👉 翻页：/钓鱼帮助 2 或 /钓鱼帮助 背包""",
        2: """【🎣 钓鱼帮助 2/10：背包与养成】
- /鱼塘
- /偷看鱼塘 [@用户/用户ID]（别名：/查看鱼塘、/偷看）
- /鱼塘容量
- /升级鱼塘（别名：/鱼塘升级）
- /水族箱（支持：/水族箱 帮助）
- /水族箱帮助（别名：/水族箱幫助）
- /放入水族箱 [FID] [数量]（别名：/移入水族箱）
- /移出水族箱 [FID] [数量]（别名：/移回鱼塘）
- /升级水族箱（别名：/水族箱升级）
- /鱼竿 /鱼饵 /饰品 /道具
- /使用 [短码]（别名：/装备）
- /开启全部钱袋（别名：/打开全部钱袋、/打开所有钱袋）
- /精炼 [短码]（别名：/强化）
- /出售 [短码]（别名：/卖出）
- /锁定 [短码]（别名：/上锁）
- /解锁 [短码]（别名：/开锁）
- /金币 /高级货币（别名：/钻石、/星石）
- /转账 [@用户/用户ID] [金额]
- /更新昵称 [新昵称]

示例：
- /使用 R2N9C
- /精炼 A7K3Q
- /出售 D1 5
- /转账 @用户 1000

🐠 水族箱专用示例：
- /水族箱
- /水族箱 帮助
- /放入水族箱 F3 5
- /放入水族箱 F3H 2（高品质）
- /移出水族箱 F3 2
- /升级水族箱

👉 翻页：/钓鱼帮助 3 或 /钓鱼帮助 商店""",
        3: """【🎣 钓鱼帮助 3/10：商店与市场】
- /全部卖出（别名：/全部出售、/卖出全部、/出售全部、/清空鱼）
- /保留卖出（别名：/保留出售、/卖出保留、/出售保留）
- /砸锅卖铁（别名：/破产、/清空）
- /出售稀有度 [1-5]（别名：/稀有度出售、/出售星级）
- /出售所有鱼竿（别名：/出售全部鱼竿、/卖出所有鱼竿）
- /出售所有饰品（别名：/出售全部饰品、/卖出所有饰品）
- /商店
- /商店购买 [商店ID] [商品ID] [数量]
- /市场
- /上架 [短码] [价格] [数量] [匿名]
- /购买 [ID]
- /我的上架（别名：/上架列表、/我的商品、/我的挂单）
- /下架 [ID]

税务与手续费（市场）
- 上架时会收取上架手续费（默认 2%，按单价计算）
- 下架商品不返还上架手续费（防止反复上下架规避税负）
- 可用 /税收记录 查看历史税费流水

示例：
- /商店购买 2 5 3
- /上架 F3 100 5 匿名
- /购买 C5

👉 翻页：/钓鱼帮助 4 或 /钓鱼帮助 交易所""",
        4: """【🎣 钓鱼帮助 4/10：交易所】
💼 交易所
- /交易所
- /交易所 开户
- /交易所 状态（支持：/交易所 status、/交易所 狀態）
- /交易所 买入 [商品名称] [数量]（支持：买入/買入/buy）
- /交易所 卖出 [商品名称] 或 [CID] [数量]（支持：卖出/賣出/sell）
- /交易所 历史 [商品] [天数]（支持：历史/歷史/history）
- /交易所 分析 [商品] [天数]（支持：分析/analysis）
- /交易所 统计（支持：统计/統計/stats）
- /交易所 持仓（支持：持仓/持倉/库存/庫存）
- /交易所 清仓（支持：清仓/清倉/clear）
- /持仓（别名：/持倉）
- /清仓（别名：/清倉；支持：/清仓 [商品名称]、/清仓 all）

税务与手续费（交易所）
- 交易所卖出按盈利部分收税（默认税率 5%，以配置为准）
- 市场上架大宗商品仍需支付市场上架手续费
- 可用 /税收记录 查看历史税费流水

示例：
- /交易所 开户
- /交易所 买入 鱼油 10
- /交易所 卖出 C1A 3
- /交易所 歷史 鱼油 7
- /交易所 持倉
- /交易所 清倉 all
- /清仓 所有

👉 翻页：/钓鱼帮助 5 或 /钓鱼帮助 抽卡""",
        5: """【🎣 钓鱼帮助 5/10：抽卡与概率玩法】
- /抽卡 /十连 /查看卡池 /抽卡记录
- /擦弹 /擦弹记录
- /命运之轮 /继续 /放弃

示例：
- /抽卡 5
- /十连 1 3
- /擦弹 allin
- /命运之轮 5000

👉 翻页：/钓鱼帮助 6 或 /钓鱼帮助 骰宝""",
        6: """【🎣 钓鱼帮助 6/10：骰宝】
- /开庄
- /大 [金额]、/小 [金额]、/单 [金额]、/双 [金额]
- /豹子 [金额]
- /一点 [金额]、/二点 [金额]、/三点 [金额]、/四点 [金额]、/五点 [金额]、/六点 [金额]
- /4点 [金额]、/5点 [金额]、/6点 [金额]、/7点 [金额]、/8点 [金额]、/9点 [金额]
- /10点 [金额]、/11点 [金额]、/12点 [金额]、/13点 [金额]、/14点 [金额]、/15点 [金额]、/16点 [金额]、/17点 [金额]
- /骰宝状态（别名：/游戏状态）
- /我的下注（别名：/下注情况）
- /骰宝帮助（别名：/骰宝说明）
- /骰宝赔率（别名：/骰宝赔率表、/赔率）

示例：
- /开庄
- /大 1000
- /12点 500
- /我的下注

👉 翻页：/钓鱼帮助 7 或 /钓鱼帮助 社交""",
        7: """【🎣 钓鱼帮助 7/10：社交与互动】
👥 社交
- /排行榜（别名：/phb）
- /偷鱼 [@用户/用户ID]
- /电鱼 [@用户/用户ID]
- /电鱼功能说明：\n  • 成功会按比例获得目标鱼塘鱼类\n  • 失败会触发天罚并进入冷却\n  • 建议先用 /偷看鱼塘 评估目标库存
- /驱灵 [@用户/用户ID]
- /驱灵说明：\n  • 需要持有【驱灵香】道具\n  • 可移除目标当前的海灵守护效果\n  • 适合在对方有守护时使用
- /查看称号 /使用称号
- /查看成就 /税收记录 /鱼类图鉴（别名：/图鉴）
- /发红包 /领红包 /红包列表 /红包详情 /撤回红包

转账与税费
- /转账 [@用户/用户ID] [金额]
- 转账手续费默认 5%（转出方支付，到账方收到输入金额本体）
- 示例：/转账 @用户 1000（你需支付 1000 + 手续费）

示例：
- /偷看鱼塘 @用户
- /电鱼 123456789
- /驱灵 @用户
- /发红包 10000 5 普通
- /鱼类图鉴
- /图鉴

👉 翻页：/钓鱼帮助 8 或 /钓鱼帮助 管理""",
        8: """【🎣 钓鱼帮助 8/10：管理员】
⚙️ 管理员
- /修改金币、/奖励金币、/扣除金币
- /修改高级货币、/奖励高级货币、/扣除高级货币
- /全体奖励金币、/全体奖励高级货币
- /全体扣除金币、/全体扣除高级货币、/全体发放道具
- /开启钓鱼后台管理、/关闭钓鱼后台管理
- /代理上线、/代理下线
- /同步初始设定（别名：/同步设定、/同步数据、/同步）
- /授予称号、/移除称号、/创建称号、/补充鱼池
- /骰宝结算、/骰宝倒计时、/骰宝模式、/清理红包

标准管理子命令写法（AstrBot）
- /fish_admin sync
- /fish_admin replenish
- /fish_admin coins [用户ID] [数量]
- /fish_admin premium [用户ID] [数量]

示例：
- /同步初始设定
- /修改金币 123456789 50000
- /骰宝模式 text

💡 说明：已支持简体/繁体关键词与 Discord @ 目标用户解析。""",
        9: """【⚡ 钓鱼速查页】
🎯 新手起步（先做这5步）
- /注册
- /签到
- /钓鱼
- /状态
- /商店

🎒 常用背包操作
- /背包
- /水族箱
- /鱼类图鉴（/图鉴）
- /鱼竿 /饰品 /鱼饵 /道具
- /使用 R短码（装备鱼竿）
- /使用 A短码（装备饰品）
- /使用 B短码（使用鱼饵）
- /使用 D短码（使用道具）
- /精炼 R短码 或 /精炼 A短码
- /出售 D1 5

💰 交易与变现
- /全部卖出
- /商店购买 2 2 5
- /市场
- /上架 F3 100 5 匿名
- /购买 C5

🧭 进阶玩法
- /交易所 开户
- /交易所 买入 鱼油 10
- /开庄
- /大 1000
- /电鱼 @用户

📌 提示：完整说明见 /钓鱼帮助 1~10""",
        11: """【🗺️ 钓鱼帮助：区域限定鱼说明】
区域限定鱼系统
- 每个区域有独立鱼池（zone_fish_mapping），只会从该区域的限定鱼里抽。
- 若当前区域某星级没有鱼，会自动重分配概率到该区域实际存在的星级（避免“抽到不存在星级”）。
- 6+ 星为独立桶：只在该区域存在 6 星及以上鱼时才会参与。

你可以这样理解
- 区域决定“可钓到哪些鱼”。
- 装备/鱼饵主要影响“在这些鱼里更容易钓到什么品质/价值”。
- 不会出现“在春潮港钓出不属于春潮港的限定鱼”这类穿池情况。

常用排查步骤（玩家向）
- /钓鱼区域 [ID] 确认自己所在区域
- /鱼类图鉴 或 /图鉴 查看已解锁鱼
- /钓鱼记录 对照近期掉落是否符合区域主题

管理向建议
- 新增/调整区域鱼后，务必保证该区域分布对应星级至少有一条鱼
- 若只想后期出神话鱼，请不要把该鱼映射到前中期区域

相关命令
- /钓鱼区域
- /钓鱼记录
- /鱼类图鉴（/图鉴）""",
        10: """【💸 税务与手续费专页】
本页汇总和金币流转相关的税费规则，便于快速核算。

一、玩家市场（上架/下架）
- 上架时收取上架手续费（默认 2%，按单价计算，具体以配置为准）
- 下架商品不返还上架手续费
- 命令示例：
  • /上架 F3 100 5 匿名
  • /下架 C5

二、交易所（大宗商品）
- 交易所卖出按盈利部分收税（默认 5%，具体以配置为准）
- 若把大宗商品挂到玩家市场，仍需支付市场上架手续费
- 命令示例：
  • /交易所 卖出 鱼油
  • /交易所 卖出 C1A 3

三、转账手续费
- /转账 [@用户/用户ID] [金额]
- 转账手续费默认 5%（转出方承担）
- 对方到账金额 = 你输入的金额本体
- 你实际扣款 = 转账金额 + 手续费
- 示例：/转账 @用户 1000

四、税费流水查询
- /税收记录：查看个人税费历史（市场税、转账手续费、交易税等）

💡 建议
- 高频交易前先看 /税收记录 评估真实净收益
- 大额转账前先预留手续费余额""",
    }

    alias_to_page = {
        "1": 1,
        "基础": 1,
        "核心": 1,
        "2": 2,
        "背包": 2,
        "养成": 2,
        "3": 3,
        "商店": 3,
        "市场": 3,
        "4": 4,
        "交易所": 4,
        "5": 5,
        "抽卡": 5,
        "概率": 5,
        "6": 6,
        "骰宝": 6,
        "骰寶": 6,
        "娱乐": 6,
        "7": 7,
        "社交": 7,
        "互动": 7,
        "8": 8,
        "管理": 8,
        "管理员": 8,
        "管理員": 8,
        "速查": 9,
        "快捷": 9,
        "新手": 9,
        "9": 9,
        "税务": 10,
        "稅務": 10,
        "税费": 10,
        "稅費": 10,
        "手续费": 10,
        "手續費": 10,
        "转账": 10,
        "轉賬": 10,
        "10": 10,
        "区域限定": 11,
        "區域限定": 11,
        "限定鱼": 11,
        "限定魚": 11,
        "区域鱼池": 11,
        "區域魚池": 11,
        "鱼池": 11,
        "魚池": 11,
        "zone": 11,
        "11": 11,
    }

    args = event.message_str.strip().split(maxsplit=1)
    if len(args) == 1:
        yield event.plain_result(
            "🎣 【釣魚幫助目錄】\n\n"
            "你剛在海邊甦醒，先學會：簽到、釣魚、賣魚、買裝備，\n"
            "再挑戰市場與交易所。\n\n"
            "─────────────────\n\n"
            "  1. 基礎\n"
            "  2. 背包與養成\n"
            "  3. 商店與市場\n"
            "  4. 交易所\n"
            "  5. 抽卡與機率玩法\n"
            "  6. 骰寶\n"
            "  7. 社交與互動\n"
            "  8. 管理員\n\n"
            "─────────────────\n\n"
            "⚡ 速查頁：/釣魚幫助 速查\n"
            "💸 稅務頁：/釣魚幫助 稅務\n"
            "🗺️ 區域限定：/釣魚幫助 區域限定\n\n"
            "用法：/釣魚幫助 <頁碼或分類>\n"
            "示例：/釣魚幫助 1  或  /釣魚幫助 商店\n\n"
            "🚀 新手推薦：/註冊 → /簽到 → /釣魚 → /狀態 → /商店"
        )
        return

    selector = args[1].strip()
    page = alias_to_page.get(selector)
    if not page:
        yield event.plain_result(
            "❌ 未識別的幫助分類\n\n"
            "請使用：/釣魚幫助 1~11\n\n"
            "或：/釣魚幫助 基礎/背包/商店/交易所/抽卡/骰寶/社交/管理/速查/稅務/區域限定"
        )
        return

    yield event.plain_result(pages[page])


async def transfer_coins(self: "FishingPlugin", event: AstrMessageEvent):
    """转账金币"""
    # 兼容简繁中文转账前缀
    raw = event.message_str
    for alt in ["/转账", "/轉賬", "/轉帳", "/轉账", "/转帐"]:
        if raw.strip().startswith(alt):
            raw = raw.replace(alt, "/转账", 1)
            break
    event.message_str = raw
    args = event.message_str.split()

    # 解析目标用户ID（支持@和用户ID两种方式）
    target_user_id, error_msg = parse_target_user_id(event, args, 1)
    if error_msg:
        yield event.plain_result(error_msg)
        return
    if not target_user_id:
        yield event.plain_result("❌ 无法解析目标用户，请使用 @用户 或 用户ID")
        return
    target_user_id = str(target_user_id)

    # 解析金额参数：兼容多空格、粘连@（如 10000<@xxx>）等输入
    amount_str = ""
    for token in args[2:]:
        cleaned = re.sub(r"<@!?\d+>", "", str(token)).strip()
        if cleaned:
            amount_str = cleaned
            break

    if not amount_str:
        yield event.plain_result(
            "❌ 請指定轉帳金額\n\n"
            "示例：\n"
            "  /轉帳 @用戶 1000\n"
            "  /轉帳 @用戶 1 萬\n"
            "  /轉帳 @用戶 一千"
        )
        return

    try:
        amount = parse_amount(amount_str)
    except Exception as e:
        yield event.plain_result(
            f"❌ 無法解析轉帳金額：{str(e)}\n\n"
            "示例：\n"
            "  /轉帳 @用戶 1000\n"
            "  /轉帳 @用戶 1 萬\n"
            "  /轉帳 @用戶 一千"
        )
        return

    from_user_id = self._get_effective_user_id(event)

    # 调用转账服务
    result = self.user_service.transfer_coins(from_user_id, target_user_id, amount)
    yield event.plain_result(result["message"])


async def update_nickname(self: "FishingPlugin", event: AstrMessageEvent):
    """更新用户昵称"""
    args = event.message_str.split(" ")

    # 检查是否提供了新昵称
    if len(args) < 2:
        yield event.plain_result(
            "❌ 请提供新昵称，例如：/更新昵称 新的昵称\n"
            "💡 昵称要求：\n"
            "  - 不能为空\n"
            "  - 长度不超过32个字符\n"
            "  - 支持中文、英文、数字和常用符号"
        )
        return

    # 提取新昵称（支持包含空格的昵称）
    new_nickname = " ".join(args[1:])

    user_id = self._get_effective_user_id(event)

    # 调用用户服务更新昵称
    result = self.user_service.update_nickname(user_id, new_nickname)
    yield event.plain_result(result["message"])
