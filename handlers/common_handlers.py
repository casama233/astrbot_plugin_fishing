import os
import re
import ast
from astrbot.api import logger
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
        # 嘗試從 event 獲取頭像 URL
        for method_name in ["get_sender_avatar", "get_sender_avatar_url"]:
            if hasattr(event, method_name):
                import asyncio

                value = getattr(event, method_name)()
                if asyncio.iscoroutine(value):
                    value = await value
                if value:
                    avatar_url = str(value)
                    break

        if not avatar_url:
            msg_obj = getattr(event, "message_obj", None)
            if msg_obj is not None:
                # 某些平台（如 Discord）的 message_obj 可能包含 sender 物件
                sender = getattr(msg_obj, "sender", None)
                if sender:
                    for attr in ["avatar", "avatar_url", "profile_image_url"]:
                        if hasattr(sender, attr):
                            value = getattr(sender, attr)
                            if value:
                                avatar_url = str(value)
                                break

                # 直接從 message_obj 獲取
                if not avatar_url:
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
    except Exception as e:
        logger.error(f"獲取頭像 URL 出錯: {e}")
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

        tips = ["⌨️ 建議下一步"]
        if not has_bait:
            tips.append("```\n/商店\n```")
        else:
            tips.append("```\n/釣魚\n```")
        if coins < 200:
            tips.append("```\n/簽到\n```")
            tips.append("```\n/全部賣出\n```")
        if auto_fishing:
            tips.append("```\n/自動釣魚\n```")
        tips.append("```\n/魚竿\n```")
        tips.append("```\n/飾品\n```")
        tips.append("```\n/精煉 R短碼\n```")
        tips.append("```\n/市場\n```")
        tips.append("```\n/交易所\n```")
        tips.append("```\n/釣魚幫助 速查\n```")
        yield event.plain_result("\n".join(tips[:7]))
    except Exception:
        yield event.plain_result(
            "⌨️ 建議下一步\n"
            "```\n/釣魚\n```\n"
            "```\n/背包\n```\n"
            "```\n/商店\n```\n"
            "```\n/市場\n```\n"
            "```\n/釣魚幫助 速查\n```"
        )


async def fishing_log(self: "FishingPlugin", event: AstrMessageEvent):
    """查看釣魚記錄"""
    raw = event.message_str
    for src in [
        "/钓鱼记录",
        "/釣魚記錄",
        "/钓鱼日志",
        "/釣魚日誌",
        "/钓鱼历史",
        "/釣魚歷史",
        "/钓鱼纪录",
        "/釣魚紀錄",
    ]:
        if raw.strip().startswith(src):
            raw = raw.replace(src, "/釣魚記錄", 1)
            break
    event.message_str = raw
    user_id = self._get_effective_user_id(event)
    if result := self.fishing_service.get_user_fish_log(user_id):
        if result["success"]:
            records = result["records"]
            if not records:
                yield event.plain_result(
                    "📜 你目前還沒有釣魚記錄。\n\n建議先試試：\n  /釣魚\n  /釣魚區域 2"
                )
                return

            message = f"【📜 釣魚記錄】最近 {len(records)} 筆\n"
            message += "════════════════════════════\n"
            for idx, record in enumerate(records, start=1):
                fish_name = record.get("fish_name", "未知魚種")
                fish_rarity = int(record.get("fish_rarity", 1) or 1)
                fish_weight = record.get("fish_weight", 0)
                fish_value = record.get("fish_value", 0)
                accessory = record.get("accessory") or "未裝備"
                rod = record.get("rod") or "未裝備"
                bait = record.get("bait") or "未使用"
                ts = safe_datetime_handler(record.get("timestamp"))

                message += (
                    f"{idx}. 🐟 {fish_name} {'★' * fish_rarity}\n"
                    f"   ⚖️ 重量：{fish_weight}g   💰 價值：{fish_value} 金幣\n"
                    f"   🎣 魚竿：{rod}   💍 飾品：{accessory}\n"
                    f"   🪱 魚餌：{bait}\n"
                    f"   🕒 時間：{ts}\n"
                )
                if idx < len(records):
                    message += "────────────────────────────\n"

            message += "════════════════════════════\n"
            message += "⌨️ 建議下一步\n"
            message += "```\n/釣魚\n```\n"
            message += "```\n/背包\n```\n"
            message += "```\n/魚類圖鑑\n```"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 取得釣魚記錄失敗：{result['message']}")
    else:
        yield event.plain_result("❌ 系統忙碌中，請稍後再試。")


async def fishing_help(self: "FishingPlugin", event: AstrMessageEvent):
    """重構版幫助：分類清晰、含引導、數值即時查詢。"""

    def _fmt_pct(x: float) -> str:
        try:
            return f"{float(x) * 100:.1f}%"
        except Exception:
            return "0%"

    def _chunk_text(text: str, limit: int = 1600):
        lines = text.split("\n")
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > limit and current:
                chunks.append(current.rstrip())
                current = line + "\n"
            else:
                current += line + "\n"
        if current.strip():
            chunks.append(current.rstrip())
        return chunks

    def _extract_command_table():
        main_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "main.py")
        )
        commands = []
        try:
            with open(main_path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if not isinstance(node, ast.AsyncFunctionDef):
                    continue
                for dec in node.decorator_list:
                    if not (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "command"
                    ):
                        continue
                    if not dec.args or not isinstance(dec.args[0], ast.Constant):
                        continue
                    cmd = str(dec.args[0].value)
                    aliases = []
                    for kw in dec.keywords:
                        if kw.arg == "alias" and isinstance(
                            kw.value, (ast.List, ast.Tuple)
                        ):
                            for e in kw.value.elts:
                                if isinstance(e, ast.Constant):
                                    aliases.append(str(e.value))
                    # 去重并保持顺序
                    seen = set()
                    uniq_aliases = []
                    for a in aliases:
                        if a not in seen:
                            seen.add(a)
                            uniq_aliases.append(a)
                    commands.append(
                        {"line": node.lineno, "command": cmd, "aliases": uniq_aliases}
                    )
            commands.sort(key=lambda x: x["line"])
        except Exception as e:
            logger.error(f"解析指令清單失敗: {e}")
        return commands

    def _fmt_cmd(c):
        aliases = c.get("aliases", [])
        if aliases:
            show = "、".join(f"/{a}" for a in aliases[:4])
            extra = " …" if len(aliases) > 4 else ""
            return f"- /{c['command']}（別名：{show}{extra}）"
        return f"- /{c['command']}"

    commands = _extract_command_table()

    # 分类映射（主命令名）
    category_rules = {
        "core": {
            "title": "🌊 新手與核心",
            "cmds": {
                "注册",
                "钓鱼",
                "签到",
                "自动钓鱼",
                "钓鱼区域",
                "钓鱼记录",
                "钓鱼纪录",
                "状态",
                "背包",
                "钓鱼帮助",
            },
        },
        "inventory": {
            "title": "🎒 背包與養成",
            "cmds": {
                "鱼塘",
                "偷看鱼塘",
                "鱼塘容量",
                "升级鱼塘",
                "水族箱",
                "水族箱帮助",
                "放入水族箱",
                "移出水族箱",
                "升级水族箱",
                "鱼竿",
                "鱼饵",
                "饰品",
                "道具",
                "使用",
                "开启全部钱袋",
                "精炼",
                "出售",
                "锁定",
                "解锁",
                "金币",
                "高级货币",
                "转账",
                "更新昵称",
            },
        },
        "economy": {
            "title": "💰 經濟：商店與市場",
            "cmds": {
                "全部卖出",
                "保留卖出",
                "砸锅卖铁",
                "出售稀有度",
                "出售所有鱼竿",
                "出售所有饰品",
                "商店",
                "商店购买",
                "市场",
                "上架",
                "购买",
                "我的上架",
                "下架",
            },
        },
        "exchange": {
            "title": "📈 交易所",
            "cmds": {"交易所", "持仓", "清仓"},
        },
        "gacha": {
            "title": "🎰 抽卡與概率玩法",
            "cmds": {
                "抽卡",
                "十连",
                "查看卡池",
                "抽卡记录",
                "擦弹",
                "擦弹记录",
                "命运之轮",
                "继续",
                "放弃",
            },
        },
        "sicbo": {
            "title": "🎲 骰寶",
            "cmds": {
                "开庄",
                "骰宝状态",
                "我的下注",
                "骰宝帮助",
                "骰宝赔率",
                "大",
                "小",
                "单",
                "双",
                "豹子",
                "一点",
                "二点",
                "三点",
                "四点",
                "五点",
                "六点",
                "4点",
                "5点",
                "6点",
                "7点",
                "8点",
                "9点",
                "10点",
                "11点",
                "12点",
                "13点",
                "14点",
                "15点",
                "16点",
                "17点",
            },
        },
        "social": {
            "title": "👥 社交與互動",
            "cmds": {
                "排行榜",
                "偷鱼",
                "电鱼",
                "驱灵",
                "查看称号",
                "使用称号",
                "查看成就",
                "税收记录",
                "鱼类图鉴",
                "发红包",
                "领红包",
                "红包列表",
                "红包详情",
                "撤回红包",
            },
        },
        "admin": {
            "title": "🛠 管理員",
            "cmds": {
                "修改金币",
                "奖励金币",
                "扣除金币",
                "修改高级货币",
                "奖励高级货币",
                "扣除高级货币",
                "全体奖励金币",
                "全体奖励高级货币",
                "全体扣除金币",
                "全体扣除高级货币",
                "全体发放道具",
                "开启钓鱼后台管理",
                "关闭钓鱼后台管理",
                "代理上线",
                "代理下线",
                "同步初始设定",
                "授予称号",
                "移除称号",
                "创建称号",
                "补充鱼池",
                "骰宝结算",
                "骰宝倒计时",
                "骰宝模式",
                "清理红包",
            },
        },
    }

    categorized = {k: [] for k in category_rules.keys()}
    uncategorized = []
    for c in commands:
        placed = False
        for key, conf in category_rules.items():
            if c["command"] in conf["cmds"]:
                categorized[key].append(c)
                placed = True
                break
        if not placed:
            uncategorized.append(c)

    # 即时配置/数值
    fishes = self.item_template_repo.get_all_fish() or []
    baits = self.item_template_repo.get_all_baits() or []
    zones = self.inventory_repo.get_all_zones() or []

    fish_count = len(fishes)
    rarity_set = sorted(
        {
            int(getattr(f, "rarity", 0) or 0)
            for f in fishes
            if getattr(f, "rarity", None) is not None
        }
    )
    min_weight = min((int(getattr(f, "min_weight", 0) or 0) for f in fishes), default=0)
    max_weight = max((int(getattr(f, "max_weight", 0) or 0) for f in fishes), default=0)
    min_value = min((int(getattr(f, "base_value", 0) or 0) for f in fishes), default=0)
    max_value = max((int(getattr(f, "base_value", 0) or 0) for f in fishes), default=0)

    zone_count = len(zones)
    active_zone_count = len([z for z in zones if bool(getattr(z, "is_active", True))])
    rare_quota_total = sum(
        int(getattr(z, "daily_rare_fish_quota", 0) or 0) for z in zones
    )

    max_bait_success = max(
        (float(getattr(b, "success_rate_modifier", 0.0) or 0.0) for b in baits),
        default=0.0,
    )
    max_bait_rare = max(
        (float(getattr(b, "rare_fish_modifier", 0.0) or 0.0) for b in baits),
        default=0.0,
    )
    max_bait_qty = max(
        (float(getattr(b, "quantity_modifier", 1.0) or 1.0) for b in baits), default=1.0
    )
    max_bait_weight = max(
        (float(getattr(b, "weight_modifier", 1.0) or 1.0) for b in baits), default=1.0
    )

    fishing_cfg = self.game_config.get("fishing", {})
    sign_cfg = self.game_config.get("signin", {})
    market_cfg = self.game_config.get("market", {})
    tax_cfg = self.game_config.get("tax", {})
    exchange_cfg = self.game_config.get("exchange", {})
    exchange_inv_cfg = (
        getattr(self.exchange_service.inventory_service, "config", {}) or {}
    )

    fish_cost = int(fishing_cfg.get("cost", 10) or 10)
    fish_cd = int(fishing_cfg.get("cooldown_seconds", 180) or 180)
    quality_cap = float(self.game_config.get("quality_bonus_max_chance", 0.35) or 0.35)
    sign_min = int(sign_cfg.get("min_reward", 100) or 100)
    sign_max = int(sign_cfg.get("max_reward", 300) or 300)

    market_tax = float(market_cfg.get("listing_tax_rate", 0.02) or 0.02)
    transfer_tax = float(tax_cfg.get("transfer_tax_rate", 0.05) or 0.05)
    exchange_tax = float(
        exchange_inv_cfg.get("tax_rate", exchange_cfg.get("tax_rate", 0.05)) or 0.05
    )
    exchange_capacity = int(
        exchange_inv_cfg.get("capacity", exchange_cfg.get("capacity", 1000)) or 1000
    )

    wof_cfg = getattr(self.game_mechanics_service, "WHEEL_OF_FATE_CONFIG", {}) or {}
    wof_min = int(wof_cfg.get("min_entry_fee", 500) or 500)
    wof_max = int(wof_cfg.get("max_entry_fee", 50000) or 50000)

    def _commands_block(key: str) -> str:
        lst = categorized.get(key, [])
        if not lst:
            return "- （此分類暫無命令）"
        return "\n".join(_fmt_cmd(x) for x in lst)

    all_cmd_lines = []
    for key in [
        "core",
        "inventory",
        "economy",
        "exchange",
        "gacha",
        "sicbo",
        "social",
        "admin",
    ]:
        title = category_rules[key]["title"]
        all_cmd_lines.append(f"【{title}】")
        all_cmd_lines.extend(_fmt_cmd(c) for c in categorized.get(key, []))
        all_cmd_lines.append("")
    if uncategorized:
        all_cmd_lines.append("【🧩 其他未分類】")
        all_cmd_lines.extend(_fmt_cmd(c) for c in uncategorized)

    pages = {
        "index": (
            "【🎣 釣魚幫助：從入門到入土】\n"
            "歡迎來到這個充滿鹹魚與夢想的世界！簡單來說，你的目標是：\n"
            "1️⃣ 搬磚：簽到、釣魚，累積第一桶金\n"
            "2️⃣ 敗家：買裝備、精煉、擴建魚塘\n"
            "3️⃣ 炒股：低買高賣，成為市場大鱷\n"
            "4️⃣ 互害：偷魚、電魚，友誼的小船說翻就翻\n\n"
            "【功能導航】\n"
            "- 1 核心：註冊、簽到、釣魚（打工人的日常）\n"
            "- 2 背包：魚塘/水族箱/裝備（你的全部家當）\n"
            "- 3 經濟：商店/市場（剁手與回血的地方）\n"
            "- 4 交易所：大宗商品（天台還是別墅？）\n"
            "- 5 機率：抽卡、擦彈（單車變摩托）\n"
            "- 6 骰寶：多人對局（贏了會所嫩模）\n"
            "- 7 社交：互偷互電（相愛相殺）\n"
            "- 8 管理：GM的權杖\n\n"
            "【當前伺服器情報】\n"
            f"- 已發現魚種：{fish_count} 種；稀有度覆蓋：{(f'{min(rarity_set)}~{max(rarity_set)} 星' if rarity_set else '暫無')}\n"
            f"- 魚獲重量：{min_weight}g ~ {max_weight}g（吃太飽了？）\n"
            f"- 市場行情：{min_value} ~ {max_value} 金幣（看臉）\n"
            f"- 開放區域：{active_zone_count}/{zone_count}；全區稀有餘額 {rare_quota_total}\n"
            f"- 釣魚成本：{fish_cost} 金幣/次；冷卻時間：{fish_cd} 秒\n"
            f"- 極品爆率上限：{_fmt_pct(quality_cap)}（玄不救非，氪能改命）\n\n"
            "【90秒光速入門】\n"
            "- /註冊 → /簽到 → /釣魚（重複N次）→ /全部賣出\n"
            "- 有錢了？買魚餌！再有錢？買股票！\n\n"
            "👇 查詢具體指令：\n"
            "用法：/釣魚幫助 <分類> 或 /釣魚幫助 <頁碼>\n"
            "範例：/釣魚幫助 社交 或 /釣魚幫助 7"
        ),
        "core": (
            "【1/10 🌊 核心玩法：打工人的自我修養】\n"
            f"情報：釣魚成本 {fish_cost} 金幣/次，CD {fish_cd} 秒，簽到低保 {sign_min}~{sign_max} 金幣\n\n"
            "【生存法則】\n"
            "- 釣魚是要錢的！別釣到破產了\n"
            "- 魚有重量和價值，越重越值錢\n"
            "- 高品質魚（✨）價格翻倍，那是歐皇的證明\n"
            "- 不同的區域有不同的魚，多出去走走\n\n"
            "【常用指令】\n"
            f"{_commands_block('core')}\n\n"
            "【老船長建議】\n"
            "- /釣魚區域 3（換個風水寶地）\n"
            "- /釣魚（開始搬磚）\n"
            "- /狀態（看看自己有多強）"
        ),
        "inventory": (
            "【2/10 🎒 背包與養成：倉鼠症患者的福音】\n"
            f"加成上限：成功率 +{max_bait_success * 100:.1f}%，稀有率 +{max_bait_rare * 100:.1f}%，數量 x{max_bait_qty:.2f}，重量 x{max_bait_weight:.2f}\n\n"
            "【你的寶庫】\n"
            "- 魚塘：暫時存放你的漁獲\n"
            "- 水族箱：保險櫃，這裡的魚不會被偷！\n"
            "- 裝備：工欲善其事，必先利其器\n"
            "- 精煉：搏一搏，單車變摩托（也可能變廢鐵）\n\n"
            "【常用指令】\n"
            f"{_commands_block('inventory')}\n\n"
            "【老船長建議】\n"
            "- /背包（看看有什麼寶貝）\n"
            "- /使用 Rxxxx（裝備魚竿）\n"
            "- /精煉 Axxxx（強化飾品）\n"
            "- /放入水族箱 Fxxxx（保護你的大魚）"
        ),
        "economy": (
            "【3/10 💰 經濟系統：商海浮沉】\n"
            f"稅務局提醒：市場交易稅 {_fmt_pct(market_tax)}（賣家承擔）\n\n"
            "【生財有道】\n"
            "- 商店：官方黑店（劃掉），補給站\n"
            "- 市場：玩家自由交易，撿漏的好地方\n"
            "- 匿名：穿上馬甲，沒人知道你是誰\n\n"
            "【常用指令】\n"
            f"{_commands_block('economy')}\n\n"
            "【老船長建議】\n"
            "- /商店（進貨）\n"
            "- /上架 F3 100 5 匿名（蒙面擺攤）\n"
            "- /購買 C5（買別人的傳家寶）"
        ),
        "exchange": (
            "【4/10 📈 交易所：釣魚界的華爾街】\n"
            f"帳戶資訊：倉位限制 {exchange_capacity}；盈利稅 {_fmt_pct(exchange_tax)}（虧了不補貼哦）\n\n"
            "【投資（賭博）指南】\n"
            "- 買入大宗商品（魚油、魚乾等）\n"
            "- 觀察價格波動，低吸高拋\n"
            "- 這是強者的遊戲，心臟不好的慎入\n\n"
            "【常用指令】\n"
            f"{_commands_block('exchange')}\n"
            "- /交易所 幫助\n"
            "- /交易所 歷史 [商品] [天數]\n"
            "- /交易所 分析 [商品] [天數]\n"
            "- /交易所 統計\n\n"
            "【老船長建議】\n"
            "- /交易所 開戶（先領個證）\n"
            "- /交易所 買入 魚油 10（試試水）\n"
            "- /持倉（看看虧了沒）"
        ),
        "gacha": (
            "【5/10 🎰 機率玩法：搏一搏，單車變摩托】\n"
            f"入場費：命運之輪 {wof_min}~{wof_max} 金幣\n\n"
            "【驗證血統的時刻】\n"
            "- 抽卡：是歐皇還是非酋，一抽便知\n"
            "- 擦彈：在危險邊緣瘋狂試探，活下來就是賺到\n"
            "- 命運之輪：是男人就下100層（雖然通常在第3層就掛了）\n\n"
            "【常用指令】\n"
            f"{_commands_block('gacha')}\n\n"
            "【老船長建議】\n"
            "- /十連 1 3（大力出奇蹟）\n"
            "- /擦彈 1000（小賭怡情）"
        ),
        "sicbo": (
            "【6/10 🎲 骰寶：贏了會所嫩模，輸了下海幹活】\n"
            "規則：莊家開盤，閒家下注。買定離手，願賭服輸！\n\n"
            "【常用指令】\n"
            f"{_commands_block('sicbo')}\n\n"
            "【老船長建議】\n"
            "- /開莊（坐莊收錢）\n"
            "- /大 1000（無腦壓大）\n"
            "- /豹子 100（夢想還是要有的）"
        ),
        "social": (
            "【7/10 👥 社交互害：友誼的小船說翻就翻】\n"
            f"手續費：轉帳扣 {_fmt_pct(transfer_tax)}（防止洗錢）\n\n"
            "【社交（互害）指南】\n"
            "- 排行榜：看看誰是肝帝，誰是歐皇\n"
            "- 偷魚/電魚：讀書人的事，能算偷嗎？\n"
            "- 發紅包：老闆大氣！老闆身體健康！\n\n"
            "【常用指令】\n"
            f"{_commands_block('social')}\n\n"
            "【老船長建議】\n"
            "- /排行榜 重量（看看誰釣到了巨物）\n"
            "- /偷魚 @倒霉蛋\n"
            "- /發紅包 10000 5 普通（散財童子）"
        ),
        "admin": (
            "【8/10 🛠 管理員：GM的權杖】\n"
            "這裡是你無法觸及的領域（除非你是管理員）。\n\n"
            "【常用指令】\n"
            f"{_commands_block('admin')}\n\n"
            "【老船長建議】\n"
            "- /重置 @玩家（重置玩家數據）\n"
            "- /凍結 @玩家（禁止玩家操作）\n"
            "- /解凍 @玩家（恢復玩家操作）"
        ),
        "science": (
            "【9/10 🧪 數值解密：一般人我不告訴他】\n"
            f"- 魚種圖鑑：{fish_count} 種；稀有度：{(f'{min(rarity_set)}~{max(rarity_set)} 星' if rarity_set else '暫無')}\n"
            f"- 魚有多重：{min_weight}g ~ {max_weight}g（取決於你餵了什麼）\n"
            f"- 魚有多貴：{min_value} ~ {max_value} 金幣（市場價波動）\n"
            f"- 開放區域：{active_zone_count}/{zone_count}；全區每日稀有配額 {rare_quota_total}\n"
            f"- 搬磚效率：{fish_cost}金幣/次，{fish_cd}秒/次\n"
            f"- 極品機率：{_fmt_pct(quality_cap)}（理論上限，實際看臉）\n"
            f"- 稅務局：交易稅 {_fmt_pct(market_tax)}，轉帳稅 {_fmt_pct(transfer_tax)}，盈利稅 {_fmt_pct(exchange_tax)}\n\n"
            "【玄學小貼士】\n"
            "- 魚餌很關鍵，選對魚餌事半功倍。\n"
            "- 高品質魚（✨）可遇不可求，釣到就是賺到。\n"
            "- 每個區域的特產都不一樣，多去探索吧！"
        ),
        "quick": (
            "【10/10 ⚡ 90秒光速入門（從入門到入土）】\n"
            "1) /註冊（簽賣身契）\n"
            "2) /簽到（領低保）\n"
            "3) /釣魚（開始搬磚）\n"
            "4) /背包（數數收穫）\n"
            "5) /全部賣出（換成小錢錢）\n"
            "6) /商店（消費升級）\n\n"
            "【進階路線】\n"
            "- 原始積累：簽到 + 釣魚 + 賣魚\n"
            "- 裝備競賽：精煉飾品 + 升級魚竿\n"
            "- 資本運作：市場撿漏 + 交易所炒股\n"
            "- 稱霸全服：衝榜 + 偷魚 + 骰寶"
        ),
        "all": "【📚 全指令索引（含別名）】\n\n" + "\n".join(all_cmd_lines),
    }

    selector_map = {
        "1": "core",
        "核心": "core",
        "基礎": "core",
        "2": "inventory",
        "背包": "inventory",
        "養成": "inventory",
        "3": "economy",
        "經濟": "economy",
        "商店": "economy",
        "市場": "economy",
        "市场": "economy",
        "4": "exchange",
        "交易所": "exchange",
        "5": "gacha",
        "機率": "gacha",
        "概率": "gacha",
        "抽卡": "gacha",
        "6": "sicbo",
        "骰寶": "sicbo",
        "骰宝": "sicbo",
        "7": "social",
        "社交": "social",
        "互動": "social",
        "互动": "social",
        "8": "admin",
        "管理": "admin",
        "管理員": "admin",
        "管理员": "admin",
        "9": "science",
        "科普": "science",
        "數值": "science",
        "数值": "science",
        "機制": "science",
        "机制": "science",
        "10": "quick",
        "速查": "quick",
        "快捷": "quick",
        "新手": "quick",
        "全部": "all",
        "全指令": "all",
        "索引": "all",
        "all": "all",
    }

    args = event.message_str.strip().split(maxsplit=1)
    if len(args) == 1:
        for chunk in _chunk_text(pages["index"]):
            yield event.plain_result(chunk)
        return

    selector = args[1].strip()
    key = selector_map.get(selector)
    if key:
        for chunk in _chunk_text(pages[key]):
            yield event.plain_result(chunk)
        return

    # 如果不是分类，尝试做命令搜索
    kw = selector.lower()
    matched = []
    for c in commands:
        cmd = c["command"].lower()
        alias_hit = any(kw in a.lower() for a in c.get("aliases", []))
        if kw in cmd or alias_hit:
            matched.append(c)

    if matched:
        msg = "【🔎 幫助搜尋結果】\n"
        msg += f"關鍵字：{selector}\n\n"
        msg += "\n".join(_fmt_cmd(c) for c in matched[:40])
        if len(matched) > 40:
            msg += f"\n\n… 另有 {len(matched) - 40} 條，請縮小關鍵字"
        for chunk in _chunk_text(msg):
            yield event.plain_result(chunk)
        return

    yield event.plain_result(
        "❌ 找不到該分類或關鍵字\n\n"
        "可用：/釣魚幫助 核心/背包/經濟/交易所/機率/骰寶/社交/管理/科普/全部\n"
        "也可直接搜尋：/釣魚幫助 轉賬 或 /釣魚幫助 水族箱"
    )


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
        yield event.plain_result("❌ 無法解析目標用戶\n\n請使用：\n  @用戶 或 用戶 ID")
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
