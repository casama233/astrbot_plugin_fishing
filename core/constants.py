from enum import Enum


class ItemType(Enum):
    ROD = "rod"
    ACCESSORY = "accessory"
    BAIT = "bait"
    ITEM = "item"
    FISH = "fish"


class ItemSubType(Enum):
    MONEY_BAG = "money_bag"
    CONSUMABLE = "consumable"
    EQUIPMENT = "equipment"


class FishQuality(Enum):
    NORMAL = 0
    HIGH = 1


class MarketListingType(Enum):
    FISH = "fish"
    ROD = "rod"
    ACCESSORY = "accessory"
    ITEM = "item"
    COMMODITY = "commodity"


class ExchangeCommodity(Enum):
    DRIED_FISH = "dried_fish"
    FISH_ROE = "fish_roe"
    FISH_OIL = "fish_oil"
    FISH_BONE = "fish_bone"
    FISH_SCALE = "fish_scale"
    FISH_SAUCE = "fish_sauce"


DEFAULT_SELL_PRICES = {
    1: 100,
    2: 500,
    3: 2000,
    4: 5000,
    5: 10000,
}

REFINE_MULTIPLIER = {
    1: 1.0,
    2: 1.6,
    3: 3.0,
    4: 6.0,
    5: 12.0,
    6: 25.0,
    7: 55.0,
    8: 125.0,
    9: 280.0,
    10: 660.0,
}

DEFAULT_POND_UPGRADES = [
    {"from": 480, "to": 999, "cost": 50000},
    {"from": 999, "to": 9999, "cost": 500000},
    {"from": 9999, "to": 99999, "cost": 50000000},
    {"from": 99999, "to": 999999, "cost": 5000000000},
]

DEFAULT_AQUARIUM_UPGRADES = [
    {"from": 0, "to": 10, "cost": 50000},
    {"from": 10, "to": 30, "cost": 200000},
    {"from": 30, "to": 100, "cost": 1000000},
    {"from": 100, "to": 500, "cost": 5000000},
]

RARITY_DISPLAY_MAP = {
    1: "⭐",
    2: "⭐⭐",
    3: "⭐⭐⭐",
    4: "⭐⭐⭐⭐",
    5: "⭐⭐⭐⭐⭐",
    6: "⭐⭐⭐⭐⭐⭐",
    7: "⭐⭐⭐⭐⭐⭐⭐",
    8: "⭐⭐⭐⭐⭐⭐⭐⭐",
    9: "⭐⭐⭐⭐⭐⭐⭐⭐⭐",
    10: "⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐",
}

SUBCOMMAND_ALIAS_MAP = {
    "註冊": "register",
    "注册": "register",
    "簽到": "signin",
    "签到": "signin",
    "背包": "bag",
    "狀態": "status",
    "状态": "status",
    "魚塘": "pond",
    "鱼塘": "pond",
    "商店": "shop",
    "市場": "market",
    "市场": "market",
    "幫助": "help",
    "帮助": "help",
    "骰寶": "sicbo",
    "骰宝": "sicbo",
    "押點": "bet_pt",
    "押点": "bet_pt",
    "購買": "buy",
    "购买": "buy",
    "上架": "list",
    "我的": "my",
    "下架": "del",
    "同步": "sync",
    "補充": "replenish",
    "补充": "replenish",
    "金幣": "coins",
    "金币": "coins",
    "高級": "premium",
    "高级": "premium",
}
