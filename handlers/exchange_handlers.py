import os
from astrbot.api.event import AstrMessageEvent
from typing import Optional, Dict, Any, TYPE_CHECKING, List
from datetime import datetime, timedelta
from ..utils import build_tip_result

if TYPE_CHECKING:
    from ..main import FishingPlugin


class ExchangeHandlers:
    COMMODITY_NAME_MAP = {
        "魚乾": "鱼干",
        "魚卵": "鱼卵",
        "魚油": "鱼油",
        "魚骨": "鱼骨",
        "魚鱗": "鱼鳞",
        "魚露": "鱼露",
    }

    def __init__(self, plugin: "FishingPlugin"):
        self.plugin = plugin
        self.exchange_service = plugin.exchange_service
        self.user_repo = plugin.user_repo

    def _normalize_commodity_name(self, name: str) -> str:
        """将繁体商品名转换为简体，便于匹配数据库中的名称"""
        return self.COMMODITY_NAME_MAP.get(name, name)

    def _get_effective_user_id(self, event: AstrMessageEvent) -> str:
        return self.plugin._get_effective_user_id(event)

    def _extract_exchange_args(self, event: AstrMessageEvent) -> List[str]:
        """提取交易所参数，兼容 `/交易所 xxx` 与直接命令。"""
        parts = event.message_str.split()
        if not parts:
            return []
        head = parts[0].lstrip("/").lower()
        if head in ["交易所", "交易市場", "交易市场", "exchange"]:
            return parts[1:]
        return parts

    def _normalize_exchange_subcommand(self, command: str) -> str:
        cmd = (command or "").strip().lstrip("/").lower()
        alias_map = {
            "开户": "open",
            "開戶": "open",
            "开戶": "open",
            "account": "open",
            "開通": "open",
            "开通": "open",
            "status": "status",
            "状态": "status",
            "狀態": "status",
            "buy": "buy",
            "purchase": "buy",
            "买入": "buy",
            "買入": "buy",
            "購入": "buy",
            "sell": "sell",
            "卖出": "sell",
            "賣出": "sell",
            "出售": "sell",
            "help": "help",
            "帮助": "help",
            "幫助": "help",
            "說明": "help",
            "说明": "help",
            "history": "history",
            "历史": "history",
            "歷史": "history",
            "analysis": "analysis",
            "分析": "analysis",
            "stats": "stats",
            "统计": "stats",
            "統計": "stats",
            "持仓": "inventory",
            "持倉": "inventory",
            "库存": "inventory",
            "庫存": "inventory",
            "倉庫": "inventory",
            "clear": "clear",
            "清仓": "clear",
            "清倉": "clear",
            "平倉": "clear",
        }
        return alias_map.get(cmd, cmd)

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """获取市场情绪对应的表情符号"""
        sentiment_map = {
            "bullish": "🐂",
            "bearish": "🐻",
            "neutral": "😐",
            "optimistic": "😊",
            "pessimistic": "😟",
            "volatile": "🌪️",
        }
        return sentiment_map.get(sentiment.lower(), "❓")

    def _get_trend_emoji(self, trend: str) -> str:
        """获取价格趋势对应的表情符号"""
        trend_map = {
            "rising": "📈",
            "falling": "📉",
            "stable": "➖",
            "volatile": "🌊",
            "sideways": "↔️",
        }
        return trend_map.get(trend.lower(), "❓")

    def _get_formatted_update_schedule(self) -> str:
        """获取格式化的价格更新时间描述"""
        schedule = self.exchange_service.price_service.get_update_schedule()
        if not schedule:
            return "未配置"
        return "、".join(t.strftime("%H:%M") for t in schedule)

    def _get_price_history_help(self) -> str:
        """获取价格历史帮助信息"""
        return """【📈 价格历史帮助】
══════════════════════════════
📊 历史数据功能
• 交易所 历史: 查看7天价格历史
• 交易所 历史 [天数]: 查看指定天数历史
• 交易所 历史 [商品]: 查看指定商品历史

📈 图表信息
• 价格走势图: 显示价格变化趋势
• 涨跌幅统计: 计算期间涨跌情况
• 波动性分析: 评估价格波动程度
• 支撑阻力位: 识别关键价格点位

💡 使用技巧
• 观察价格趋势，判断买卖时机
• 关注成交量变化，分析市场活跃度
• 识别价格模式，预测未来走势
• 结合技术指标，提高分析准确性

══════════════════════════════
💬 示例: 【交易所 历史 3】查看3天价格历史
        """

    def _get_market_analysis_help(self) -> str:
        """获取市场分析帮助信息"""
        return """【📈 市场分析帮助】
══════════════════════════════
📊 分析指标
• 市场情绪: 反映投资者心理状态
• 价格趋势: 显示价格发展方向
• 供需状态: 分析市场供需平衡
• 波动性: 评估价格波动程度

📈 技术分析
• 移动平均线: 平滑价格波动
• 相对强弱指数: 判断超买超卖
• 布林带: 识别价格通道
• 成交量分析: 验证价格走势

💡 投资建议
• 趋势跟踪: 跟随主要趋势方向
• 反转策略: 在极端位置反向操作
• 分散投资: 降低单一商品风险
• 止损止盈: 控制风险和锁定利润

══════════════════════════════
💬 使用【交易所 分析】查看详细分析报告
        """

    def _get_trading_stats_help(self) -> str:
        """获取交易统计帮助信息"""
        return """【📈 交易统计帮助】
══════════════════════════════
📊 个人统计
• 总交易次数: 累计买卖操作次数
• 总交易金额: 累计交易金币数量
• 盈亏统计: 总体盈亏情况
• 胜率分析: 盈利交易占比

📈 持仓分析
• 当前持仓: 各商品持有数量
• 持仓价值: 按当前价格计算总价值
• 持仓成本: 购买时的总成本
• 浮动盈亏: 未实现盈亏情况

💡 风险控制
• 仓位管理: 控制单次交易规模
• 止损设置: 设定最大亏损限额
• 分散投资: 避免集中持仓
• 定期评估: 定期检查投资组合

══════════════════════════════
💬 使用【交易所 统计】查看个人交易统计
        """

    def _to_base36(self, n: int) -> str:
        """将数字转换为Base36字符串"""
        if n == 0:
            return "0"
        out = []
        while n > 0:
            n, remainder = divmod(n, 36)
            out.append("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[remainder])
        return "".join(reversed(out))

    def _get_commodity_display_code(self, instance_id: int) -> str:
        """生成大宗商品的显示ID"""
        return f"C{self._to_base36(instance_id)}"

    def _calculate_inventory_profit_loss(
        self, inventory: Dict[str, Any], current_prices: Dict[str, int]
    ) -> Dict[str, Any]:
        """计算库存盈亏分析 - 统一的数据流方法"""
        try:
            total_cost = 0
            total_current_value = 0

            for commodity_id, commodity_data in inventory.items():
                total_cost += commodity_data.get("total_cost", 0)
                current_price = current_prices.get(commodity_id, 0)

                # 检查每个商品实例是否腐败
                commodity_value = 0
                for item in commodity_data.get("items", []):
                    if not isinstance(item, dict):
                        continue

                    expires_at = item.get("expires_at")
                    quantity = item.get("quantity", 0)

                    if expires_at and isinstance(expires_at, datetime):
                        now = datetime.now()
                        is_expired = expires_at <= now

                        if is_expired:
                            # 腐败商品按0价值计算
                            commodity_value += 0
                        else:
                            # 未腐败商品按当前市场价格计算
                            commodity_value += current_price * quantity
                    else:
                        # 如果没有过期时间信息，按当前市场价格计算
                        commodity_value += current_price * quantity

                total_current_value += commodity_value

            profit_loss = total_current_value - total_cost
            profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0

            return {
                "total_cost": total_cost,
                "total_current_value": total_current_value,
                "profit_loss": profit_loss,
                "profit_rate": profit_rate,
                "is_profit": profit_loss > 0,
            }
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"计算库存盈亏分析失败: {e}")
            return {
                "total_cost": 0,
                "total_current_value": 0,
                "profit_loss": 0,
                "profit_rate": 0,
                "is_profit": False,
            }

    def _from_base36(self, s: str) -> int:
        """将base36字符串转换为数字"""
        return int(s, 36)

    def _parse_commodity_display_code(self, code: str) -> Optional[int]:
        """解析大宗商品的显示ID，返回instance_id"""
        code = code.strip().upper()
        if code.startswith("C") and len(code) > 1:
            try:
                return self._from_base36(code[1:])
            except ValueError:
                return None
        return None

    def _sparkline(self, values: List[int]) -> str:
        """将数值列表转换为简单的 Unicode sparkline。"""
        if not values:
            return ""
        ticks = "▁▂▃▄▅▆▇█"
        mn, mx = min(values), max(values)
        if mx == mn:
            return ticks[0] * len(values)

        def scale(v: int) -> int:
            idx = int((v - mn) / (mx - mn) * (len(ticks) - 1))
            return max(0, min(len(ticks) - 1, idx))

        return "".join(ticks[scale(v)] for v in values)

    async def _view_price_history(self, event: AstrMessageEvent):
        """查看价格历史曲线：
        - 交易所 历史 -> 默认7天，显示所有商品
        - 交易所 历史 [天数] -> 显示指定天数，所有商品
        - 交易所 历史 [商品] -> 默认7天，仅该商品
        - 交易所 历史 [商品] [天数] -> 指定商品与天数
        """
        args = self._extract_exchange_args(event)
        if args and self._normalize_exchange_subcommand(args[0]) == "history":
            args = args[1:]
        # 解析参数
        target_commodity_name: Optional[str] = None
        days = 7
        # 支持的商品名映射
        market_status = self.exchange_service.get_market_status()
        if not market_status.get("success"):
            yield event.plain_result(
                f"❌ 获取市场信息失败: {market_status.get('message', '未知错误')}"
            )
            return

        # 参数形态判断
        # 交易所 历史
        # 交易所 历史 X
        # 交易所 历史 商品
        # 交易所 历史 商品 X
        if len(args) >= 1:
            p = args[0]
            # 若是数字，解析为天数
            if p.isdigit():
                days = max(1, min(30, int(p)))
            else:
                # 解析商品名（支持繁简通用）
                p_normalized = self._normalize_commodity_name(p)
                found = False
                for cid, info in market_status.get("commodities", {}).items():
                    if self._normalize_commodity_name(info["name"]) == p_normalized:
                        target_commodity_name = info["name"]
                        found = True
                        break
                if not found:
                    yield event.plain_result(self._get_price_history_help())
                    return
                # 若还有第四个参数作为天数
                if len(args) >= 2 and args[1].isdigit():
                    days = max(1, min(30, int(args[1])))

        # 获取历史数据
        hist = self.exchange_service.get_price_history(days=days)
        if not hist.get("success"):
            yield event.plain_result(
                f"❌ 获取历史失败: {hist.get('message', '未知错误')}"
            )
            return

        history: Dict[str, List[int]] = hist.get("history", {})
        labels: List[str] = hist.get("labels", [])

        # 根据商品过滤
        if target_commodity_name:
            # 查找对应 commodity_id
            cid = None
            for c_id, info in market_status.get("commodities", {}).items():
                if info["name"] == target_commodity_name:
                    cid = c_id
                    break
            if not cid:
                yield event.plain_result(f"❌ 找不到商品: {target_commodity_name}")
                return
            history = {cid: history.get(cid, [])}

        # 没有任何数据
        if not history:
            yield event.plain_result("暂无历史数据。")
            return

        # 反查 id->name
        id_to_name = {
            cid: info["name"]
            for cid, info in market_status.get("commodities", {}).items()
        }
        # 优先图片渲染
        try:
            from ..draw.exchange import draw_exchange_history_image

            image = draw_exchange_history_image(labels, history, id_to_name, days)
            image_path = os.path.join(self.plugin.tmp_dir, "exchange_history.png")
            image.save(image_path)
            yield event.image_result(image_path)

            user_id = self._get_effective_user_id(event)
            tip = build_tip_result(
                event,
                "⌨️ 建議下一步\n```\n/交易所 分析\n```",
                plugin=self.plugin,
                user_id=user_id,
            )
            if tip:
                yield tip
            return
        except Exception:
            pass

        # 文字回退
        msg = "【📈 價格歷史】\n"
        msg += f"區間：近 {days} 天\n"
        msg += "═" * 30 + "\n"
        for cid, series in history.items():
            name = id_to_name.get(cid, cid)
            if not series:
                continue
            spark = self._sparkline(series)
            start = series[0]
            end = series[-1]
            change = end - start
            pct = (change / start * 100) if start > 0 else 0
            msg += f"{name}: {spark}\n"
            msg += f"  起始 {start:,} → 當前 {end:,} 變化 {change:+,} ({pct:+.1f}%)\n"
        yield event.plain_result(msg)

    async def _view_market_analysis(self, event: AstrMessageEvent):
        """市场分析：
        - 交易所 分析 -> 默认分析全部商品，7天窗口
        - 交易所 分析 [商品] -> 分析单商品，7天窗口
        - 交易所 分析 [商品] [天数] -> 分析单商品，指定窗口（1-30）
        - 交易所 分析 [天数] -> 分析全部商品，指定窗口
        """
        from math import sqrt

        args = self._extract_exchange_args(event)
        if args and self._normalize_exchange_subcommand(args[0]) == "analysis":
            args = args[1:]
        target_commodity_name: Optional[str] = None
        days = 7

        market_status = self.exchange_service.get_market_status()
        if not market_status.get("success"):
            yield event.plain_result(
                f"❌ 获取市场信息失败: {market_status.get('message', '未知错误')}"
            )
            return
        commodities = market_status.get("commodities", {})
        id_to_name = {cid: info["name"] for cid, info in commodities.items()}

        # 解析参数：可能是（分析）、（分析 X）、（分析 商品）、（分析 商品 X）
        if len(args) >= 1:
            p = args[0]
            if p.isdigit():
                days = max(1, min(30, int(p)))
            else:
                # 支持繁简通用
                p_normalized = self._normalize_commodity_name(p)
                found = False
                for cid, info in commodities.items():
                    if self._normalize_commodity_name(info["name"]) == p_normalized:
                        target_commodity_name = info["name"]
                        found = True
                        break
                if not found:
                    yield event.plain_result(self._get_market_analysis_help())
                    return
        if len(args) >= 2 and args[1].isdigit():
            days = max(1, min(30, int(args[1])))

        hist = self.exchange_service.get_price_history(days=days)
        if not hist.get("success"):
            yield event.plain_result(
                f"❌ 获取历史失败: {hist.get('message', '未知错误')}"
            )
            return
        history: Dict[str, List[int]] = hist.get("history", {})

        # 过滤商品
        if target_commodity_name:
            cid = None
            for c_id, info in commodities.items():
                if info["name"] == target_commodity_name:
                    cid = c_id
                    break
            if not cid:
                yield event.plain_result(f"❌ 找不到商品: {target_commodity_name}")
                return
            history = {cid: history.get(cid, [])}

        if not history:
            yield event.plain_result("暂无可分析的数据。")
            return

        def sma(series: List[int], n: int) -> float:
            if not series or n <= 0:
                return 0.0
            n = min(n, len(series))
            return sum(series[-n:]) / n

        def volatility(series: List[int]) -> float:
            if len(series) < 2:
                return 0.0
            # 简单标准差近似：与均值的偏差
            m = sum(series) / len(series)
            var = sum((x - m) ** 2 for x in series) / (len(series) - 1)
            epsilon = 1e-6
            denom = m if abs(m) >= epsilon else epsilon
            return sqrt(var) / denom * 100

        def simple_rsi(series: List[int]) -> float:
            # 简易RSI：最近N-1日涨幅与跌幅的比率
            if len(series) < 3:
                return 50.0
            window = min(15, len(series) - 1)
            if window < 1:
                return 50.0
            gains = 0.0
            losses = 0.0
            for a, b in zip(series[-(window + 1) : -1], series[-window:]):
                diff = b - a
                if diff > 0:
                    gains += diff
                elif diff < 0:
                    losses -= diff
            if gains + losses == 0:
                return 50.0
            rs = gains / max(1e-9, losses)
            rsi = 100 - (100 / (1 + rs))
            return max(0.0, min(100.0, rsi))

        def trend(series: List[int]) -> str:
            MIN_WINDOW = 5
            if len(series) < MIN_WINDOW:
                # For very short series, trend is unreliable
                return "stable"
            # Use at least MIN_WINDOW or len(series)//3, whichever is larger
            window = max(MIN_WINDOW, len(series) // 3)
            start_idx = max(0, len(series) - window)
            start = series[start_idx]
            end = series[-1]
            if end > start * 1.02:
                return "rising"
            return "falling" if end < start * 0.98 else "stable"

        def suggestion(trend_val: str, rsi_val: float, vol_val: float) -> str:
            if trend_val == "rising" and rsi_val < 70:
                return "趋势向上，可考虑顺势少量买入"
            if trend_val == "falling" and rsi_val > 30:
                return "趋势向下，谨慎观望或逢反弹减仓"
            if vol_val > 15:
                return "波动较大，建议降低仓位控制风险"
            return "以观望为主，等待更明确信号"

        rows = []
        for cid, series in history.items():
            if not series:
                continue
            name = id_to_name.get(cid, cid)
            last = series[-1]
            ma3 = sma(series, 3)
            ma5 = sma(series, 5)
            ma7 = sma(series, 7)
            vol = volatility(series)
            rsi = simple_rsi(series)
            tr = trend(series)
            sug = suggestion(tr, rsi, vol)
            rows.append(
                {
                    "name": name,
                    "last": last,
                    "ma3": ma3,
                    "ma5": ma5,
                    "ma7": ma7,
                    "vol": vol,
                    "rsi": rsi,
                    "trend": tr,
                    "suggestion": sug,
                    "series": series,
                }
            )

        try:
            from ..draw.exchange import draw_exchange_analysis_image

            image = draw_exchange_analysis_image(rows, days)
            image_path = os.path.join(self.plugin.tmp_dir, "exchange_analysis.png")
            image.save(image_path)
            yield event.image_result(image_path)

            user_id = self._get_effective_user_id(event)
            tip = build_tip_result(
                event,
                "⌨️ 建議下一步\n```\n/交易所 買入 商品 數量\n```\n```\n/交易所 歷史\n```",
                plugin=self.plugin,
                user_id=user_id,
            )
            if tip:
                yield tip
            return
        except Exception:
            pass

        msg = "【📊 市場分析】\n"
        msg += f"窗口: 近{days}天\n"
        msg += "═" * 30 + "\n"
        for row in rows:
            msg += f"{row['name']}\n"
            msg += f"  當前價: {int(row['last']):,}\n"
            msg += f"  均線: MA3={row['ma3']:.0f}  MA5={row['ma5']:.0f}  MA7={row['ma7']:.0f}\n"
            msg += f"  波動率: {row['vol']:.1f}%  RSI: {row['rsi']:.0f}\n"
            msg += f"  趨勢: {row['trend']}  建議: {row['suggestion']}\n"
            msg += "─" * 20 + "\n"
        yield event.plain_result(msg)

    async def _view_trading_stats(self, event: AstrMessageEvent):
        """查看交易統計：展示用戶持倉統計和盈虧情況"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)

        if not user or not user.exchange_account_status:
            yield event.plain_result(
                "您尚未開通交易所賬戶，請使用【交易所 開戶】命令開戶。"
            )
            return

        market_status = self.exchange_service.get_market_status()
        if not market_status.get("success"):
            yield event.plain_result(
                f"❌ 獲取市場信息失敗: {market_status.get('message', '未知錯誤')}"
            )
            return

        current_prices = market_status.get("prices", {})
        commodities = market_status.get("commodities", {})

        inventory_result = self.exchange_service.get_user_inventory(user_id)
        if not inventory_result.get("success"):
            yield event.plain_result(
                f"❌ 獲取庫存失敗: {inventory_result.get('message', '未知錯誤')}"
            )
            return

        inventory = inventory_result.get("inventory", {})
        analysis = self._calculate_inventory_profit_loss(inventory, current_prices)

        total_quantity = sum(
            data.get("total_quantity", 0) for data in inventory.values()
        )
        total_cost = analysis.get("total_cost", 0)
        total_value = analysis.get("total_current_value", 0)
        profit_loss = analysis.get("profit_loss", 0)
        profit_rate = analysis.get("profit_rate", 0)

        commodity_details = []
        for commodity_id, data in inventory.items():
            name = data.get("name", commodity_id)
            qty = data.get("total_quantity", 0)
            cost = data.get("total_cost", 0)
            price = current_prices.get(commodity_id, 0)
            value = qty * price
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0

            items = data.get("items", [])
            expired_count = 0
            expiring_soon = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                expires_at = item.get("expires_at")
                item_qty = item.get("quantity", 0)
                if expires_at and isinstance(expires_at, datetime):
                    time_left = expires_at - datetime.now()
                    if time_left.total_seconds() <= 0:
                        expired_count += item_qty
                    elif time_left.total_seconds() < 86400:
                        expiring_soon += item_qty

            commodity_details.append(
                {
                    "name": name,
                    "quantity": qty,
                    "cost": cost,
                    "value": value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "expired": expired_count,
                    "expiring_soon": expiring_soon,
                }
            )

        try:
            from ..draw.exchange import draw_exchange_stats_image

            image = draw_exchange_stats_image(
                total_quantity=total_quantity,
                total_cost=total_cost,
                total_value=total_value,
                profit_loss=profit_loss,
                profit_rate=profit_rate,
                commodity_details=commodity_details,
                commodities_info=commodities,
            )
            image_path = os.path.join(self.plugin.tmp_dir, "exchange_stats.png")
            image.save(image_path)
            yield event.image_result(image_path)

            tip = build_tip_result(
                event,
                "⌨️ 建議下一步\n```\n/持倉\n```\n```\n/交易所 分析\n```",
                plugin=self.plugin,
                user_id=user_id,
            )
            if tip:
                yield tip
            return
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"繪製統計圖片失敗: {e}")

        msg = "【📊 我的交易統計】\n"
        msg += "═" * 30 + "\n"
        msg += f"📦 總持倉數量: {total_quantity}\n"
        msg += f"💰 總成本: {total_cost:,} 金幣\n"
        msg += f"💎 當前價值: {total_value:,} 金幣\n"
        profit_icon = "📈" if profit_loss >= 0 else "📉"
        msg += f"{profit_icon} 盈虧: {profit_loss:+,} 金幣 ({profit_rate:+.1f}%)\n"
        msg += "─" * 30 + "\n"

        for detail in commodity_details:
            name = detail["name"]
            qty = detail["quantity"]
            cost = detail["cost"]
            pnl = detail["pnl"]
            pnl_pct = detail["pnl_pct"]
            expired = detail["expired"]
            expiring = detail["expiring_soon"]

            status = ""
            if expired > 0:
                status = f" 💀過期{expired}個"
            elif expiring > 0:
                status = f" ⚠️將過期{expiring}個"

            pnl_icon = "📈" if pnl >= 0 else "📉"
            msg += f"• {name}: {qty}個 | 成本{cost:,} | {pnl_icon}{pnl:+,} ({pnl_pct:+.1f}%){status}\n"

        msg += "═" * 30 + "\n"
        msg += "💡 使用【持倉】查看詳細庫存 | 【交易所 分析】查看市場分析"

        yield event.plain_result(msg)

    async def exchange_main(self, event: AstrMessageEvent):
        """交易所主命令，根据参数分发到不同功能"""
        args = self._extract_exchange_args(event)

        if len(args) == 0:
            # 无参数，显示交易所状态
            async for r in self.exchange_status(event):
                yield r
        elif len(args) >= 1:
            command = self._normalize_exchange_subcommand(args[0])
            if command == "open":
                async for r in self.open_exchange_account(event):
                    yield r
            elif command == "buy":
                async for r in self.buy_commodity(event):
                    yield r
            elif command == "sell":
                async for r in self.sell_commodity(event):
                    yield r
            elif command == "help":
                try:
                    from ..draw.exchange import draw_exchange_help_image

                    sections = [
                        (
                            "📊 市場資訊",
                            [
                                "/交易所",
                                "/交易所 歷史 [商品] [天數]",
                                "/交易所 分析 [商品] [天數]",
                                "/交易所 統計",
                            ],
                        ),
                        (
                            "💼 交易操作",
                            [
                                "/交易所 開戶",
                                "/交易所 買入 [商品] [數量]",
                                "/交易所 賣出 [商品] [數量]",
                                "/交易所 賣出 [庫存ID] [數量]",
                            ],
                        ),
                        (
                            "📦 庫存管理",
                            [
                                "/持倉",
                                "/清倉",
                                "/清倉 [商品]",
                                "/交易所 持倉",
                                "/交易所 清倉",
                            ],
                        ),
                    ]
                    schedule_display = self._get_formatted_update_schedule()
                    exchange_cfg = (
                        getattr(self.exchange_service.inventory_service, "config", {})
                        or {}
                    )
                    tax_rate = float(exchange_cfg.get("tax_rate", 0.05) or 0.05)
                    capacity = int(exchange_cfg.get("capacity", 1000) or 1000)
                    image = draw_exchange_help_image(
                        sections,
                        schedule_display,
                        f"{tax_rate * 100:.1f}%",
                        str(capacity),
                    )
                    image_path = os.path.join(self.plugin.tmp_dir, "exchange_help.png")
                    image.save(image_path)
                    yield event.image_result(image_path)
                except Exception:
                    yield event.plain_result(self._get_exchange_help())
            elif command == "history":
                async for r in self._view_price_history(event):
                    yield r
            elif command == "analysis":
                async for r in self._view_market_analysis(event):
                    yield r
            elif command == "stats":
                async for r in self._view_trading_stats(event):
                    yield r
            elif command == "status":
                async for r in self.exchange_status(event):
                    yield r
            elif command == "inventory":
                async for r in self.view_inventory(event):
                    yield r
            elif command == "clear":
                async for r in self.clear_inventory(event):
                    yield r
            else:
                yield event.plain_result(
                    "❌ 未知命令。使用【交易所 帮助/幫助/help】查看可用命令。"
                )

    def _get_exchange_help(self) -> str:
        """获取交易所帮助信息"""
        schedule_display = self._get_formatted_update_schedule()
        return f"""【📈 交易所完整指南】
══════════════════════════════
🎯 快速入門
1. /交易所 開戶 - 開通交易所帳戶
2. /交易所 - 查看當前市場行情
3. /交易所 買入 魚乾 10 - 購買10個魚乾
4. /持倉 - 查看我的庫存
5. /交易所 賣出 魚乾 5 - 賣出5個魚乾

══════════════════════════════
📊 市場資訊指令
• /交易所 - 查看當前市場行情和價格
• /交易所 歷史 [商品] [天數] - 查看價格歷史走勢圖
  範例：/交易所 歷史 魚乾 7（查看魚乾7天走勢）
• /交易所 分析 [商品] [天數] - 查看市場技術分析
  範例：/交易所 分析 魚油 5（查看魚油5天分析）
• /交易所 統計 - 查看個人交易統計數據

══════════════════════════════
💰 交易操作指令
【買入】
• /交易所 買入 [商品名稱] [數量]
  範例：/交易所 買入 魚乾 10
  說明：購買指定數量的大宗商品

【賣出】
• /交易所 賣出 [商品名稱] [數量]
  範例：/交易所 賣出 魚乾 5
  說明：賣出指定數量的商品（先進先出）

• /交易所 賣出 [庫存ID] [數量]
  範例：/交易所 賣出 C123 3
  說明：按庫存ID精準賣出（查看/持倉獲取ID）

• /交易所 賣出 [商品名稱] - 賣出該商品全部庫存
  範例：/交易所 賣出 魚油

══════════════════════════════
📦 庫存管理指令
• /持倉（/持倉）- 查看我的庫存詳情
  顯示：持有商品、數量、成本、當前價值、盈虧

• /清倉（/清倉）- 賣出所有庫存
  警告：會賣出所有商品，請謹慎使用

• /清倉 [商品名稱] - 賣出指定商品全部庫存
  範例：/清倉 魚乾

• /清倉 [庫存ID] - 賣出指定庫存
  範例：/清倉 C123

══════════════════════════════
⏰ 重要時間資訊
• 價格更新時間：每日 {schedule_display}
• 商品保質期：
  - 魚乾：3天
  - 魚卵：2天
  - 魚油：1-3天（隨機）
• 交易時間：24小時全天開放

══════════════════════════════
💡 交易技巧與建議
【新手建議】
• 先小額試水，熟悉市場規律
• 關注價格歷史，了解波動範圍
• 注意保質期，及時賣出避免腐敗
• 不要把所有金幣投入交易所

【進階策略】
• 低買高賣：在價格低點買入，高點賣出
• 分散投資：不要只買一種商品
• 趨勢跟隨：觀察市場情緒和價格趨勢
• 止損止盈：設定心理價位，控制風險

【風險提示】
⚠️ 商品會腐敗！過期商品價值歸零
⚠️ 價格波動大！可能虧損
⚠️ 盈利需繳稅！賣出盈利部分會扣稅
⚠️ 倉位有限！注意庫存容量

══════════════════════════════
📈 可交易商品
• 魚乾 - 保質期3天，價格相對穩定，低風險
• 魚卵 - 保質期2天，價格波動較大，高風險
• 魚油 - 保質期1-3天，高風險高收益，投機品
• 魚骨 - 保質期7天，價格最穩定，超低風險
• 魚鱗 - 保質期4天，價格波動適中，平衡之選
• 魚露 - 保質期1天，價格劇烈波動，僅供高手

══════════════════════════════
❓ 常見問題
Q: 如何查看庫存ID？
A: 使用 /持倉 指令，會顯示每個庫存的ID

Q: 為什麼賣出時扣的錢比預期少？
A: 盈利部分需要繳稅，虧損不退稅

Q: 商品腐敗了怎麼辦？
A: 腐敗商品價值歸零，無法賣出，注意保質期

Q: 可以取消交易嗎？
A: 交易一旦完成無法取消，請謹慎操作

══════════════════════════════
💬 需要幫助？使用 /交易所 幫助 查看本指南
    """

    async def exchange_status(self, event: AstrMessageEvent):
        """查看交易所当前状态"""
        try:
            user_id = self._get_effective_user_id(event)
            user = self.user_repo.get_by_id(user_id)

            if not user or not user.exchange_account_status:
                yield event.plain_result(
                    "您尚未开通交易所账户，请使用【交易所 开户】命令开户。"
                )
                return

            result = self.exchange_service.get_market_status()
            if not result["success"]:
                yield event.plain_result(
                    f"❌ 查询失败: {result.get('message', '未知错误')}"
                )
                return

            prices = result["prices"]
            commodities = result["commodities"]

            # 获取价格历史用于计算涨跌幅（使用“上一次价格”而非“昨天”）
            price_history = self.exchange_service.get_price_history(days=2)
            previous_prices = {}
            if price_history.get("success"):
                updates = price_history.get("updates", []) or []
                # 将更新按商品分组（updates 已按时间排序）
                updates_by_comm: Dict[str, list] = {}
                for u in updates:
                    cid = u.get("commodity_id")
                    if not cid:
                        continue
                    updates_by_comm.setdefault(cid, []).append(u)

                # 取每个商品的倒数第二条作为“上一次价格”
                for cid, ulist in updates_by_comm.items():
                    if len(ulist) >= 2:
                        previous_prices[cid] = ulist[-2].get("price")

            msg = "【📈 交易所行情】\n"
            msg += f"更新时间: {result.get('date', 'N/A')}\n"
            msg += "═" * 30 + "\n"

            # 显示市场情绪和趋势（移到商品价格上面）
            market_sentiment = result.get("market_sentiment", "neutral")
            price_trend = result.get("price_trend", "stable")
            supply_demand = result.get("supply_demand", "平衡")

            msg += f"📊 市场情绪: {self._get_sentiment_emoji(market_sentiment)} {market_sentiment}\n"
            msg += f"📈 价格趋势: {self._get_trend_emoji(price_trend)} {price_trend}\n"
            msg += f"⚖️ 供需状态: {supply_demand}\n"
            msg += "─" * 20 + "\n"

            # 显示每个商品的详细信息
            for comm_id, price in prices.items():
                commodity = commodities.get(comm_id)
                if commodity:
                    msg += f"商品: {commodity['name']}\n"
                    msg += f"价格: {price:,} 金币"

                    # 计算涨跌幅
                    if comm_id in previous_prices:
                        prev_price = previous_prices[comm_id]
                        change = price - prev_price
                        change_percent = (
                            (change / prev_price) * 100 if prev_price > 0 else 0
                        )

                        if change > 0:
                            msg += f" 📈 +{change:,} (+{change_percent:.1f}%)"
                        elif change < 0:
                            msg += f" 📉 {change:,} ({change_percent:.1f}%)"
                        else:
                            msg += f" ➖ 0 (0.0%)"
                    else:
                        msg += " 🆕 新价格"

                    msg += "\n"
                    msg += f"描述: {commodity['description']}\n"
                    msg += "─" * 20 + "\n"

            # 显示持仓容量和盈亏分析
            capacity = self.plugin.exchange_service.config.get("exchange", {}).get(
                "capacity", 1000
            )

            inventory_result = self.plugin.exchange_service.get_user_inventory(user_id)
            if inventory_result["success"]:
                inventory = inventory_result["inventory"]
                current_total_quantity = sum(
                    data.get("total_quantity", 0) for data in inventory.values()
                )
                capacity_percent = (
                    (current_total_quantity / capacity) * 100 if capacity > 0 else 0
                )

                msg += f"📦 当前持仓: {current_total_quantity} / {capacity} ({capacity_percent:.1f}%)\n"

                if inventory:
                    analysis = self._calculate_inventory_profit_loss(inventory, prices)
                    profit_status = (
                        "📈盈利"
                        if analysis["is_profit"]
                        else "📉亏损"
                        if analysis["profit_loss"] < 0
                        else "➖持平"
                    )
                    msg += f"💰 持仓盈亏: {analysis['profit_loss']:+,} 金币 ({analysis['profit_rate']:+.1f}%) {profit_status}\n"

                    # 显示各商品持仓详情
                    if len(inventory) > 0:
                        msg += "📋 持仓详情:\n"
                        for comm_id, data in inventory.items():
                            if data.get("total_quantity", 0) > 0:
                                commodity = commodities.get(comm_id, {})
                                current_price = prices.get(comm_id, 0)
                                total_value = (
                                    data.get("total_quantity", 0) * current_price
                                )
                                msg += f"  • {commodity.get('name', comm_id)}: {data.get('total_quantity', 0)}个 (价值 {total_value:,} 金币)\n"
                else:
                    msg += "📋 持仓详情: 暂无持仓\n"
            else:
                msg += f"📦 当前持仓: 无法获取 / {capacity}\n"

            # 显示下次更新时间
            schedule = self.exchange_service.price_service.get_update_schedule()
            now = datetime.now()
            next_update = None
            for scheduled_time in schedule:
                update_time = now.replace(
                    hour=scheduled_time.hour,
                    minute=scheduled_time.minute,
                    second=0,
                    microsecond=0,
                )
                if update_time > now:
                    next_update = update_time
                    break

            if not next_update and schedule:
                first_time = schedule[0]
                next_update = (now + timedelta(days=1)).replace(
                    hour=first_time.hour,
                    minute=first_time.minute,
                    second=0,
                    microsecond=0,
                )

            if next_update:
                time_diff = next_update - now
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                msg += f"⏰ 下次更新: {next_update.strftime('%H:%M')} (约{hours}小时{minutes}分钟后)\n"
            else:
                msg += "⏰ 下次更新: 未配置\n"

            msg += "═" * 30 + "\n"
            msg += "💡 使用【交易所 帮助】查看更多命令。"

            # 优先使用图片渲染（失败则回退文字）
            try:
                from ..draw.exchange import draw_exchange_status_image

                # 獲取最近的價格歷史用於走勢圖（最近7天）
                recent_history_result = self.exchange_service.get_price_history(days=7)
                recent_history = None
                if recent_history_result.get("success"):
                    recent_history = recent_history_result.get("history", {})

                image = draw_exchange_status_image(
                    result, previous_prices, recent_history
                )
                image_path = os.path.join(self.plugin.tmp_dir, "exchange_status.png")
                image.save(image_path)
                yield event.image_result(image_path)

                user_id = self._get_effective_user_id(event)
                tip = build_tip_result(
                    event,
                    "⌨️ 建議下一步\n```\n/交易所 分析\n```\n```\n/持倉\n```",
                    plugin=self.plugin,
                    user_id=user_id,
                )
                if tip:
                    yield tip
                return
            except Exception:
                pass

            yield event.plain_result(msg)
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"交易所状态查询失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")

    async def open_exchange_account(self, event: AstrMessageEvent):
        """开通交易所账户"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.open_exchange_account(user_id)
        if result.get("success"):
            self.plugin.tutorial_service.check_command_progress(user_id, "交易所 開戶")
        try:
            from ..draw.exchange import draw_exchange_result_image

            ok = bool(result.get("success"))
            title = "交易所開戶成功" if ok else "交易所開戶失敗"
            lines = [str(result.get("message", ""))]
            image = draw_exchange_result_image(title, lines, success=ok)
            image_path = os.path.join(self.plugin.tmp_dir, "exchange_open_result.png")
            image.save(image_path)
            yield event.image_result(image_path)
            return
        except Exception:
            pass
        yield event.plain_result(
            f"✅ {result['message']}"
            if result["success"]
            else f"❌ {result['message']}"
        )

    async def view_inventory(self, event: AstrMessageEvent):
        """查看大宗商品库存"""
        try:
            from astrbot.api import logger

            user_id = self._get_effective_user_id(event)

            result = self.exchange_service.get_user_inventory(user_id)
            if not result["success"]:
                yield event.plain_result(f"❌ {result.get('message', '查询失败')}")
                return

            inventory = result["inventory"]
            if not inventory:
                yield event.plain_result("您的交易所库存为空。")
                return

            market_status = self.exchange_service.get_market_status()
            current_prices = market_status.get("prices", {})

            analysis = self._calculate_inventory_profit_loss(inventory, current_prices)

            msg = "【📦 我的交易所库存】\n"
            msg += "═" * 30 + "\n"

            profit_status = (
                "📈盈利"
                if analysis["is_profit"]
                else "📉亏损"
                if analysis["profit_loss"] < 0
                else "➖持平"
            )
            msg += f"📊 总体盈亏：{analysis['profit_loss']:+} 金币 {profit_status}\n"
            msg += f"💰 总成本：{analysis['total_cost']:,} 金币\n"
            msg += f"💎 当前价值：{analysis['total_current_value']:,} 金币\n"
            msg += f"📈 盈利率：{analysis['profit_rate']:+.1f}%\n"
            msg += "─" * 30 + "\n"

            for commodity_id, commodity_data in inventory.items():
                try:
                    commodity_name = commodity_data.get("name", "未知商品")
                    total_quantity = commodity_data.get("total_quantity", 0)

                    current_price = current_prices.get(commodity_id, 0)

                    # 计算商品总价值，考虑腐败状态
                    commodity_value = 0
                    for item in commodity_data.get("items", []):
                        if not isinstance(item, dict):
                            continue

                        expires_at = item.get("expires_at")
                        quantity = item.get("quantity", 0)

                        if expires_at and isinstance(expires_at, datetime):
                            now = datetime.now()
                            is_expired = expires_at <= now

                            if is_expired:
                                # 腐败商品按0价值计算
                                commodity_value += 0
                            else:
                                # 未腐败商品按当前市场价格计算
                                commodity_value += current_price * quantity
                        else:
                            # 如果没有过期时间信息，按当前市场价格计算
                            commodity_value += current_price * quantity

                    profit_loss = commodity_value - commodity_data.get("total_cost", 0)
                    profit_status = (
                        "📈" if profit_loss > 0 else "📉" if profit_loss < 0 else "➖"
                    )
                    msg += f"{commodity_name} ({total_quantity}个) - 盈亏: {profit_loss:+}金币 {profit_status}\n"

                    for item in commodity_data.get("items", []):
                        if not isinstance(item, dict):
                            continue

                        expires_at = item.get("expires_at")
                        instance_id = item.get("instance_id")
                        quantity = item.get("quantity", 0)

                        if (
                            expires_at
                            and isinstance(expires_at, datetime)
                            and instance_id is not None
                        ):
                            time_left = expires_at - datetime.now()
                            display_id = self._get_commodity_display_code(instance_id)

                            if time_left.total_seconds() <= 0:
                                time_str = "💀 已腐败"
                            elif time_left.total_seconds() < 86400:
                                hours = int(time_left.total_seconds() // 3600)
                                time_str = f"⚠️剩{hours}小时"
                            else:
                                days = int(time_left.total_seconds() // 86400)
                                remaining_hours = int(
                                    (time_left.total_seconds() % 86400) // 3600
                                )
                                if remaining_hours > 0:
                                    time_str = f"✅剩{days}天{remaining_hours}小时"
                                else:
                                    time_str = f"✅剩{days}天"

                            msg += f"  └─ {display_id}: {quantity}个 ({time_str})\n"

                except Exception as e:
                    logger.error(f"处理库存项失败: {e}")
                    continue

            msg += "═" * 30 + "\n"

            capacity = self.exchange_service.config.get("exchange", {}).get(
                "capacity", 1000
            )
            current_total_quantity = sum(
                data.get("total_quantity", 0) for data in inventory.values()
            )
            msg += f"📦 当前持仓: {current_total_quantity} / {capacity}\n"

            # 优先使用图片渲染（失败则回退文字）
            try:
                from ..draw.exchange import draw_exchange_inventory_image

                image = draw_exchange_inventory_image(
                    inventory,
                    current_prices,
                    analysis,
                    capacity,
                    current_total_quantity,
                )
                image_path = os.path.join(self.plugin.tmp_dir, "exchange_inventory.png")
                image.save(image_path)
                yield event.image_result(image_path)

                user_id = self._get_effective_user_id(event)
                tip = build_tip_result(
                    event,
                    "⌨️ 建議下一步\n```\n/交易所 賣出 商品 數量\n```\n```\n/交易所 歷史\n```",
                    plugin=self.plugin,
                    user_id=user_id,
                )
                if tip:
                    yield tip
                return
            except Exception:
                pass

            yield event.plain_result(msg)

        except Exception as e:
            from astrbot.api import logger

            logger.error(f"持仓命令执行失败: {e}")
            yield event.plain_result(f"❌ 持仓命令执行失败: {e}")

    async def buy_commodity(self, event: AstrMessageEvent):
        """购买大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = self._extract_exchange_args(event)
        if args and self._normalize_exchange_subcommand(args[0]) == "buy":
            args = args[1:]

        if len(args) != 2:
            yield event.plain_result(
                "❌ 命令格式错误，请使用：交易所 买入 [商品名称] [数量]"
            )
            return

        commodity_name = self._normalize_commodity_name(args[0])
        try:
            quantity = int(args[1])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数")
                return
        except ValueError:
            yield event.plain_result("❌ 数量必须是有效的数字")
            return

        market_status = self.exchange_service.get_market_status()
        if not market_status["success"]:
            yield event.plain_result(
                f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
            )
            return

        commodity_id = None
        for cid, info in market_status["commodities"].items():
            if self._normalize_commodity_name(info["name"]) == commodity_name:
                commodity_id = cid
                break

        if not commodity_id:
            yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
            return

        current_price = market_status["prices"].get(commodity_id, 0)
        if current_price <= 0:
            yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
            return

        result = self.exchange_service.purchase_commodity(
            user_id, commodity_id, quantity, current_price
        )
        try:
            from ..draw.exchange import draw_exchange_result_image

            ok = bool(result.get("success"))
            title = "買入完成" if ok else "買入失敗"
            lines = [
                f"商品: {commodity_name}",
                f"數量: {quantity}",
                f"成交價: {current_price:,} 金幣",
                str(result.get("message", "")),
            ]
            image = draw_exchange_result_image(title, lines, success=ok)
            image_path = os.path.join(self.plugin.tmp_dir, "exchange_buy_result.png")
            image.save(image_path)
            yield event.image_result(image_path)
            return
        except Exception:
            pass
        yield event.plain_result(
            f"✅ {result['message']}"
            if result["success"]
            else f"❌ {result['message']}"
        )

    async def sell_commodity(self, event: AstrMessageEvent):
        """卖出大宗商品"""
        try:
            user_id = self._get_effective_user_id(event)
            args = self._extract_exchange_args(event)
            if args and self._normalize_exchange_subcommand(args[0]) == "sell":
                args = args[1:]

            market_status = self.exchange_service.get_market_status()
            if not market_status["success"]:
                yield event.plain_result(
                    f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
                )
                return

            first_arg = args[0] if args else ""

            if len(args) == 1:
                commodity_name = self._normalize_commodity_name(args[0])
                commodity_id = None
                for cid, info in market_status["commodities"].items():
                    if self._normalize_commodity_name(info["name"]) == commodity_name:
                        commodity_id = cid
                        break

                if not commodity_id:
                    yield event.plain_result(f"❌ 找不到商品: {args[0]}")
                    return

                current_price = market_status["prices"].get(commodity_id, 0)
                if current_price <= 0:
                    yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
                    return

                inventory = self.exchange_service.get_user_commodities(user_id)
                commodity_items = [
                    item for item in inventory if item.commodity_id == commodity_id
                ]
                if not commodity_items:
                    yield event.plain_result(f"❌ 您没有 {args[0]}")
                    return

                quantity = sum(item.quantity for item in commodity_items)
                result = self.exchange_service.sell_commodity(
                    user_id, commodity_id, quantity, current_price
                )
                instance_id = None

            elif len(args) == 2:
                first_arg = args[0]
                instance_id = self._parse_commodity_display_code(first_arg)

                try:
                    quantity = int(args[1])
                    if quantity <= 0:
                        yield event.plain_result("❌ 数量必须是正整数")
                        return
                except ValueError:
                    yield event.plain_result("❌ 数量必须是有效的数字")
                    return

                if instance_id is not None:
                    inventory = self.exchange_service.get_user_commodities(user_id)
                    commodity_item = next(
                        (item for item in inventory if item.instance_id == instance_id),
                        None,
                    )
                    if not commodity_item:
                        yield event.plain_result("❌ 找不到指定的库存项目")
                        return

                    current_price = market_status["prices"].get(
                        commodity_item.commodity_id, 0
                    )
                    if current_price <= 0:
                        yield event.plain_result("❌ 商品价格异常")
                        return

                    result = self.exchange_service.sell_commodity_by_instance(
                        user_id, instance_id, quantity, current_price
                    )
                    commodity_name = commodity_item.name
                else:
                    commodity_name = self._normalize_commodity_name(first_arg)
                    commodity_id = None
                    for cid, info in market_status["commodities"].items():
                        if (
                            self._normalize_commodity_name(info["name"])
                            == commodity_name
                        ):
                            commodity_id = cid
                            break

                    if not commodity_id:
                        yield event.plain_result(f"❌ 找不到商品: {first_arg}")
                        return

                    current_price = market_status["prices"].get(commodity_id, 0)
                    if current_price <= 0:
                        yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
                        return

                    inventory = self.exchange_service.get_user_commodities(user_id)
                    commodity_items = [
                        item for item in inventory if item.commodity_id == commodity_id
                    ]
                    if not commodity_items:
                        yield event.plain_result(f"❌ 您没有 {first_arg}")
                        return

                    total_quantity = sum(item.quantity for item in commodity_items)
                    if quantity > total_quantity:
                        yield event.plain_result(
                            f"❌ 数量不足！您只有 {total_quantity} 个 {first_arg}"
                        )
                        return

                    result = self.exchange_service.sell_commodity(
                        user_id, commodity_id, quantity, current_price
                    )
            else:
                yield event.plain_result("❌ 命令格式错误，请使用帮助查看。")
                return

            try:
                from ..draw.exchange import draw_exchange_result_image

                ok = bool(result.get("success"))
                title = "賣出完成" if ok else "賣出失敗"
                if instance_id is not None:
                    lines = [
                        f"庫存ID: {first_arg}",
                        f"數量: {quantity}",
                        f"成交價: {current_price:,} 金幣",
                        str(result.get("message", "")),
                    ]
                else:
                    lines = [
                        f"商品: {first_arg}",
                        f"數量: {quantity}",
                        f"成交價: {current_price:,} 金幣",
                        str(result.get("message", "")),
                    ]

                image = draw_exchange_result_image(title, lines, success=ok)
                image_path = os.path.join(
                    self.plugin.tmp_dir, "exchange_sell_result.png"
                )
                image.save(image_path)
                yield event.image_result(image_path)
                return
            except Exception:
                pass

            yield event.plain_result(
                f"✅ {result['message']}"
                if result["success"]
                else f"❌ {result['message']}"
            )
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"卖出大宗商品失败: {e}")
            yield event.plain_result(f"❌ 卖出失败: {str(e)}")

    async def clear_inventory(self, event: AstrMessageEvent):
        """清仓功能"""
        user_id = self._get_effective_user_id(event)
        args = self._extract_exchange_args(event)
        if args and self._normalize_exchange_subcommand(args[0]) == "clear":
            args = args[1:]

        if len(args) == 0 or (
            len(args) == 1 and args[0].lower() in ["all", "所有", "全部"]
        ):
            result = self.exchange_service.clear_all_inventory(user_id)
            try:
                from ..draw.exchange import draw_exchange_result_image

                ok = bool(result.get("success"))
                image = draw_exchange_result_image(
                    "一鍵清倉", [str(result.get("message", ""))], success=ok
                )
                image_path = os.path.join(
                    self.plugin.tmp_dir, "exchange_clear_result.png"
                )
                image.save(image_path)
                yield event.image_result(image_path)
                return
            except Exception:
                pass
            yield event.plain_result(
                f"✅ {result['message']}"
                if result["success"]
                else f"❌ {result['message']}"
            )
        elif len(args) == 1:
            commodity_name = self._normalize_commodity_name(args[0])

            market_status = self.exchange_service.get_market_status()
            if not market_status["success"]:
                yield event.plain_result(
                    f"❌ 获取价格失败: {market_status.get('message', '未知错误')}"
                )
                return

            commodity_id = None
            for cid, info in market_status["commodities"].items():
                if self._normalize_commodity_name(info["name"]) == commodity_name:
                    commodity_id = cid
                    break

            if not commodity_id:
                yield event.plain_result(f"❌ 找不到商品: {args[0]}")
                return

            result = self.exchange_service.clear_commodity_inventory(
                user_id, commodity_id
            )
            try:
                from ..draw.exchange import draw_exchange_result_image

                ok = bool(result.get("success"))
                image = draw_exchange_result_image(
                    "分商品清倉",
                    [f"商品: {commodity_name}", str(result.get("message", ""))],
                    success=ok,
                )
                image_path = os.path.join(
                    self.plugin.tmp_dir, "exchange_clear_result.png"
                )
                image.save(image_path)
                yield event.image_result(image_path)
                return
            except Exception:
                pass
            yield event.plain_result(
                f"✅ {result['message']}"
                if result["success"]
                else f"❌ {result['message']}"
            )
        else:
            yield event.plain_result(
                "❌ 命令格式错误，请使用：/清仓 或 /清仓 [商品名称]，或 交易所 清仓 [商品名称]"
            )
