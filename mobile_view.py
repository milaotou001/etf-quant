"""Pure configuration helpers for the private mobile Streamlit view."""
from __future__ import annotations

import base64
import binascii
import json
import math
import os
from datetime import datetime
from collections.abc import Iterable, Mapping
from pathlib import Path

from purchase_plan import CURRENT_PLAN_VERSION


FULL_PAGE_OPTIONS = [
    "状态与图表",
    "复盘日志",
    "半年买入计划",
    "组合复盘",
    "战略方向",
]
READ_ONLY_PAGE_OPTIONS = ["状态与图表", "半年买入计划"]
TRADE_SNAPSHOT_VERSION = 1
TRADE_TYPES = {"buy", "sell_profit", "sell_loss"}

MOBILE_DIR = Path(__file__).resolve().parent / "mobile"
PLAN_SNAPSHOT_FILE = "plan_snapshot.json"
TRADES_SNAPSHOT_FILE = "trades_snapshot.json"


class MobileViewConfigError(ValueError):
    """Raised when cloud read-only configuration is absent or unsafe."""


def is_mobile_read_only(env: Mapping[str, object]) -> bool:
    raw = env.get("MOBILE_READ_ONLY")
    if raw is None:
        return False
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise MobileViewConfigError("MOBILE_READ_ONLY 必须是 true 或 false")


def mobile_page_options(read_only: bool) -> list[str]:
    return list(READ_ONLY_PAGE_OPTIONS if read_only else FULL_PAGE_OPTIONS)


def primary_metric_order(read_only: bool) -> list[str]:
    return ["rsi", "price", "macd", "rvol"] if read_only else ["price", "rsi", "macd", "rvol"]


def plan_price_symbols(read_only: bool, symbols: Iterable[str]) -> tuple[str, ...]:
    return () if read_only else tuple(symbols)


def _validate_plan(plan: object) -> dict:
    if not isinstance(plan, dict) or not isinstance(plan.get("assets"), dict):
        raise MobileViewConfigError("计划快照缺少 assets")
    if plan.get("version") != CURRENT_PLAN_VERSION:
        raise MobileViewConfigError(
            f"计划快照版本不兼容：需要 {CURRENT_PLAN_VERSION}，实际 {plan.get('version')}"
        )
    return plan


def encode_plan_snapshot(plan: dict) -> str:
    validated = _validate_plan(plan)
    payload = json.dumps(validated, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


def load_mobile_plan(env: Mapping[str, object]) -> dict:
    encoded = env.get("PURCHASE_PLAN_B64")
    if not encoded:
        raise MobileViewConfigError("云端缺少 PURCHASE_PLAN_B64 计划快照")
    try:
        payload = base64.b64decode(str(encoded).encode("ascii"), validate=True)
        plan = json.loads(payload.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise MobileViewConfigError("PURCHASE_PLAN_B64 解码失败") from exc
    return _validate_plan(plan)


def _scalar_value(value: object) -> object:
    """Convert pandas/numpy scalar values to ordinary Python values."""
    return value.item() if hasattr(value, "item") else value


def _normalize_trade_date(value: object) -> str:
    value = _scalar_value(value)
    if hasattr(value, "strftime") and not isinstance(value, str):
        text = value.strftime("%Y-%m-%d")
    else:
        text = str(value)[:10]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise MobileViewConfigError("交易点 date 必须是 YYYY-MM-DD") from exc
    return text


def _normalize_trade_entry(entry: Mapping[str, object]) -> dict:
    if not isinstance(entry, Mapping):
        raise MobileViewConfigError("交易点记录格式无效")
    trade_type = str(entry.get("type", ""))
    if trade_type not in TRADE_TYPES:
        raise MobileViewConfigError(f"交易点 type 无效：{trade_type}")
    try:
        price = float(_scalar_value(entry["price"]))
        qty_value = float(_scalar_value(entry["qty"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise MobileViewConfigError("交易点 price/qty 无效") from exc
    if not math.isfinite(price) or not math.isfinite(qty_value) or price < 0 or qty_value <= 0:
        raise MobileViewConfigError("交易点 price/qty 必须是有效正数")
    qty = int(qty_value) if qty_value.is_integer() else qty_value
    return {
        "date": _normalize_trade_date(entry.get("date")),
        "type": trade_type,
        "price": price,
        "qty": qty,
    }


def _normalize_trade_snapshot(trades: Mapping[str, Iterable[Mapping[str, object]]]) -> dict:
    if not isinstance(trades, Mapping):
        raise MobileViewConfigError("交易点快照格式无效")
    symbols = {}
    for symbol, entries in sorted(trades.items(), key=lambda item: str(item[0])):
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Iterable):
            raise MobileViewConfigError("交易点列表格式无效")
        symbols[str(symbol)] = [_normalize_trade_entry(entry) for entry in entries]
    return {"version": TRADE_SNAPSHOT_VERSION, "symbols": symbols}


def encode_trade_snapshot(trades: Mapping[str, Iterable[Mapping[str, object]]]) -> str:
    payload = _normalize_trade_snapshot(trades)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def load_mobile_trades(env: Mapping[str, object]) -> dict[str, list[dict]]:
    """Load chart-only trade points; missing or invalid cloud data degrades safely."""
    encoded = env.get("TRADES_B64")
    if not encoded:
        return {}
    try:
        payload = base64.b64decode(str(encoded).encode("ascii"), validate=True)
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, Mapping) or decoded.get("version") != TRADE_SNAPSHOT_VERSION:
            raise MobileViewConfigError("交易点快照版本不兼容")
        normalized = _normalize_trade_snapshot(decoded.get("symbols", {}))
        return normalized["symbols"]
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError, TypeError, ValueError, MobileViewConfigError):
        return {}


def save_mobile_snapshots(plan: dict, trades: dict | None = None, base_dir: Path | None = None) -> tuple[Path, Path]:
    """Write plan and trade snapshots as plain JSON files.  Returns (plan_path, trades_path)."""
    target_dir = base_dir or MOBILE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    plan_path = target_dir / PLAN_SNAPSHOT_FILE
    trades_path = target_dir / TRADES_SNAPSHOT_FILE
    plan_payload = _validate_plan(plan)
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot = _normalize_trade_snapshot(trades or {}) if trades else {"version": TRADE_SNAPSHOT_VERSION, "symbols": {}}
    trades_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path, trades_path


def load_mobile_plan_from_snapshot(base_dir: Path | None = None) -> dict:
    plan_path = (base_dir or MOBILE_DIR) / PLAN_SNAPSHOT_FILE
    if not plan_path.is_file():
        raise MobileViewConfigError(f"计划快照文件不存在：{plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MobileViewConfigError("计划快照文件解析失败") from exc
    return _validate_plan(plan)


def load_mobile_trades_from_snapshot(base_dir: Path | None = None) -> dict[str, list[dict]]:
    trades_path = (base_dir or MOBILE_DIR) / TRADES_SNAPSHOT_FILE
    if not trades_path.is_file():
        return {}
    try:
        decoded = json.loads(trades_path.read_text(encoding="utf-8"))
        if not isinstance(decoded, Mapping) or decoded.get("version") != TRADE_SNAPSHOT_VERSION:
            return {}
        normalized = _normalize_trade_snapshot(decoded.get("symbols", {}))
        return normalized["symbols"]
    except (json.JSONDecodeError, TypeError, ValueError, MobileViewConfigError):
        return {}
