import json
from pathlib import Path
from typing import Any, Dict, Optional


def _plugin_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / ".kiro"
        / "settings"
        / "astrbot_plugin_fishing_config.json"
    )


def _load_plugin_config() -> Dict[str, Any]:
    cfg_path = _plugin_config_path()
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _coerce_scalar(value: str) -> Any:
    text = (value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except Exception:
        return text


def parse_effect_code(raw: Optional[str]) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    result: Dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        if not key:
            continue
        result[key] = _coerce_scalar(value)
    return result


def get_accessory_effect_code(accessory_id: Optional[int]) -> str:
    if not accessory_id:
        return ""
    cfg = _load_plugin_config()
    notes = (cfg.get("item_effect_notes") or {}).get("accessories") or {}
    return str(notes.get(str(accessory_id), "") or "")


def get_accessory_effects(accessory_id: Optional[int]) -> Dict[str, Any]:
    return parse_effect_code(get_accessory_effect_code(accessory_id))


def get_bait_effect_code(bait_id: Optional[int]) -> str:
    if not bait_id:
        return ""
    cfg = _load_plugin_config()
    notes = (cfg.get("item_effect_notes") or {}).get("baits") or {}
    return str(notes.get(str(bait_id), "") or "")


def get_bait_effects(bait_id: Optional[int]) -> Dict[str, Any]:
    return parse_effect_code(get_bait_effect_code(bait_id))


def get_effect_number(effects: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(effects.get(key, default))
    except Exception:
        return float(default)


def get_effect_multiplier(
    effects: Dict[str, Any], key: str, default: float = 1.0
) -> float:
    value = get_effect_number(effects, key, default)
    return value if value > 0 else default


BAIT_EFFECT_KEYS = {
    "fishing_success_bonus": "釣魚成功率加成，0.05=+5%",
    "fishing_rare_bonus": "稀有魚出現率加成，0.03=+3%",
    "fishing_coin_bonus": "釣魚金幣收益加成，0.10=+10%",
    "fishing_quality_multiplier": "高品質魚概率倍率，1.2=+20%",
    "fishing_quantity_multiplier": "釣魚數量倍率，1.1=+10%",
    "fishing_weight_multiplier": "釣魚重量倍率，1.5=+50%",
    "garbage_reduction": "垃圾魚減少率，0.5=減少50%",
    "cooldown_multiplier": "釣魚冷卻時間倍率，0.8=減少20%",
    "duration_multiplier": "魚餌持續時間倍率，2.0=雙倍時間",
}

ACCESSORY_EFFECT_KEYS = {
    "fishing_cooldown_multiplier": "釣魚冷卻時間倍率，0.5=減半",
    "fishing_success_bonus": "釣魚成功率加成，0.05=+5%",
    "fishing_rare_bonus": "稀有魚出現率加成，0.03=+3%",
    "fishing_coin_bonus": "釣魚金幣收益加成，0.10=+10%",
    "fishing_quality_multiplier": "高品質魚概率倍率，1.2=+20%",
    "fishing_quantity_multiplier": "釣魚數量倍率，1.1=+10%",
    "steal_cooldown_multiplier": "偷魚冷卻時間倍率，0.7=減少30%",
    "electric_cooldown_multiplier": "電魚冷卻時間倍率，0.8=減少20%",
    "auto_fishing_interval_multiplier": "自動釣魚間隔倍率，0.75=縮短25%",
    "daily_tax_multiplier": "每日稅率倍率，0.5=稅收減半",
    "transfer_tax_multiplier": "轉賬稅率倍率，0.6=稅收減少40%",
    "market_tax_multiplier": "市場交易稅率倍率，0.8=稅收減少20%",
}
