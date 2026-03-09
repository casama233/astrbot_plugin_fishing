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
