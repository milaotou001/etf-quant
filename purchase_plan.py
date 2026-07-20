"""半年买入计划的领域模型、持久化与观察计算。"""
from __future__ import annotations

import copy
import json
import math
import os
from datetime import date, timedelta


PRIVATE_DATA_DIR = os.path.join(os.path.dirname(__file__), "private_data")
PURCHASE_PLAN_PATH = os.path.join(PRIVATE_DATA_DIR, "purchase_plan.json")

PLAN_BASE_AMOUNT = 285_000.0
CURRENT_PLAN_VERSION = 6
STATUS_PLANNED = "planned"
STATUS_PENDING = "pending_reconciliation"
STATUS_RECONCILED = "reconciled"
EXECUTION_ON_PLAN = "on_plan"
EXECUTION_DEVIATION = "deviation"

TARGETS = {
    "563360": {"name": "A500", "target": 42_000.0, "color": "#2f855a", "soft_color": "#dcefe5"},
    "510300": {"name": "沪深300", "target": 42_000.0, "color": "#2563eb", "soft_color": "#dbeafe"},
    "518880": {"name": "黄金", "target": 57_000.0, "color": "#d69e2e", "soft_color": "#f9edc7"},
    "561380": {"name": "电网设备", "target": 10_000.0, "color": "#0891b2", "soft_color": "#cffafe"},
    "516150": {"name": "稀土", "target": 8_000.0, "color": "#c2410c", "soft_color": "#ffedd5"},
    "159570": {"name": "港股创新药", "target": 8_000.0, "color": "#db2777", "soft_color": "#fce7f3"},
    "560860": {"name": "工业有色", "target": 6_000.0, "color": "#b45309", "soft_color": "#fef3c7"},
    "513180": {"name": "恒生科技", "target": 8_000.0, "color": "#0d9488", "soft_color": "#ccfbf1"},
    "588000": {"name": "科创50（暂停）", "target": 28_500.0, "color": "#7c3aed", "soft_color": "#ede9fe"},
}

WIDE_ETF_ALLOCATION = {"first": 0.5, "second": 0.25, "third": 0.25}
WIDE_ETF_ROUND_AMOUNT = 11_250.0
WIDE_SYMBOLS = ("563360", "510300")
WIDE_CURRENT_AMOUNTS = (3_750.0, 3_750.0, 3_750.0)
WIDE_PLAN_NOTE = "第三笔等待右侧确认"
STRATEGIC_SATELLITE_ALLOCATION = {"first": 0.2, "second": 0.3, "third": 0.5}
STRATEGIC_PLAN_NOTE = "第1笔等初步止跌；第2笔等回踩确认；第3笔等右侧修复"
STRATEGIC_PLANS = {
    "561380": {
        "rounds": [
            (1_200.0, 1_800.0, 3_000.0),
            (800.0, 1_200.0, 2_000.0),
        ],
        "reserved_amount": 10_000.0,
        "plan_note": "第1轮：等止跌/回踩/右侧 · 第2轮：等半年报验证利润来源",
    },
    "516150": {
        "rounds": [
            (1_500.0, 2_500.0, 4_000.0),
        ],
        "reserved_amount": 8_000.0,
        "plan_note": STRATEGIC_PLAN_NOTE,
    },
    "159570": {
        "rounds": [
            (1_500.0, 2_500.0, 4_000.0),
        ],
        "reserved_amount": 8_000.0,
        "plan_note": STRATEGIC_PLAN_NOTE,
    },
    "560860": {
        "rounds": [
            (720.0, 1_080.0, 1_800.0),
            (480.0, 720.0, 1_200.0),
        ],
        "reserved_amount": 6_000.0,
        "plan_note": "第1轮：等止跌/回踩/右侧 · 第2轮：等Q3铜价趋势确认",
    },
    "513180": {
        "rounds": [
            (1_000.0, 1_500.0, 2_500.0),
            (600.0, 900.0, 1_500.0),
        ],
        "reserved_amount": 8_000.0,
        "plan_note": "第1轮：等RSI 30-35/回踩/右侧 · 第2轮：留弹药应对港股闪崩",
    },
}


def _wide_etf_amounts() -> list[float]:
    """Return two three-entry rounds using the approved 50/25/25 split."""
    round_amounts = [
        WIDE_ETF_ROUND_AMOUNT * WIDE_ETF_ALLOCATION[key]
        for key in ("first", "second", "third")
    ]
    return round_amounts + round_amounts


def _new_item(symbol: str, number: int, amount: float, planned_date: str | None = None) -> dict:
    return {
        "id": f"{symbol}-{number:02d}",
        "number": number,
        "planned_amount": float(amount),
        "planned_date": planned_date,
        "status": STATUS_PLANNED,
        "confirmed_date": None,
        "confirmed_dates": [],
        "actual": None,
        "needs_confirmation": False,
        "execution_type": None,
        "deviation_reason": None,
    }


def _strategic_asset(symbol: str, existing: dict | None = None) -> dict:
    plan = STRATEGIC_PLANS[symbol]
    existing_items = {
        int(item.get("number") or 0): item
        for item in (existing or {}).get("items", [])
    }
    items = []
    number = 1
    for round_amounts in plan["rounds"]:
        for amount in round_amounts:
            old_item = existing_items.get(number)
            if old_item and old_item.get("status") != STATUS_PLANNED:
                item = copy.deepcopy(old_item)
            else:
                item = _new_item(symbol, number, amount)
            items.append(item)
            number += 1
    return {
        **copy.deepcopy(TARGETS[symbol]),
        "reserved_amount": plan["reserved_amount"],
        "plan_note": plan["plan_note"],
        "items": items,
    }


def default_purchase_plan() -> dict:
    """Return a fresh copy of the confirmed 2026 second-half purchase plan."""
    assets = {}
    for symbol in WIDE_SYMBOLS:
        assets[symbol] = {
            **copy.deepcopy(TARGETS[symbol]),
            "plan_note": WIDE_PLAN_NOTE,
            "items": [
                _new_item(symbol, number, amount)
                for number, amount in enumerate(WIDE_CURRENT_AMOUNTS, start=1)
            ],
        }

    assets["588000"] = {
        **copy.deepcopy(TARGETS["588000"]),
        "plan_note": "暂停：半导体权重过高（50%+），与科技簇（集成电路/AI）同步暂停；待科技簇解冻后统一评估。",
        "items": [_new_item("588000", number, 2_552.5) for number in range(1, 7)],
    }

    start = date(2026, 7, 10)
    gold_items = [
        _new_item("518880", number, 2_500.0, (start + timedelta(days=7 * (number - 1))).isoformat())
        for number in range(1, 13)
    ]
    gold_items[0]["status"] = STATUS_PENDING
    gold_items[0]["confirmed_date"] = "2026-07-10"
    assets["518880"] = {**copy.deepcopy(TARGETS["518880"]), "items": gold_items}
    for symbol in STRATEGIC_PLANS:
        assets[symbol] = _strategic_asset(symbol)

    ordered_assets = {symbol: assets[symbol] for symbol in TARGETS}
    return {
        "version": CURRENT_PLAN_VERSION,
        "base_amount": PLAN_BASE_AMOUNT,
        "cash_target": 75_500.0,
        "allocation_scheme": {
            "strategic_satellite": copy.deepcopy(STRATEGIC_SATELLITE_ALLOCATION)
        },
        "assets": ordered_assets,
    }


def save_purchase_plan(plan: dict, path: str = PURCHASE_PLAN_PATH) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def load_purchase_plan(path: str = PURCHASE_PLAN_PATH) -> dict:
    if not path or not os.path.exists(path):
        return default_purchase_plan()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_purchase_plan()
    if not isinstance(payload, dict) or "assets" not in payload:
        return default_purchase_plan()
    return _migrate_plan(payload)


def _migrate_plan(plan: dict) -> dict:
    """Upgrade the saved plan without changing statuses or actual trade records."""
    version = int(plan.get("version", 1) or 1)
    if version >= CURRENT_PLAN_VERSION:
        return plan

    updated = copy.deepcopy(plan)
    if version < 2:
        wide_etf_amounts = _wide_etf_amounts()
        for symbol in WIDE_SYMBOLS:
            items = updated.get("assets", {}).get(symbol, {}).get("items", [])
            if len(items) != len(wide_etf_amounts):
                continue
            if any(item.get("status") != STATUS_PLANNED for item in items[:3]):
                # The first round may already be in progress under the former equal split.
                amounts = [3_750.0, 3_750.0, 3_750.0, *wide_etf_amounts[3:]]
            else:
                amounts = wide_etf_amounts
            for item, amount in zip(items, amounts):
                item["planned_amount"] = amount
        updated["allocation_scheme"] = {"wide_etf": copy.deepcopy(WIDE_ETF_ALLOCATION)}

    if version < 4:
        assets = updated.setdefault("assets", {})
        for symbol in WIDE_SYMBOLS:
            asset = assets.get(symbol)
            if not asset:
                continue
            asset.update(copy.deepcopy(TARGETS[symbol]))
            asset["items"] = [
                item
                for item in asset.get("items", [])
                if int(item.get("number") or 0) <= 2
                or item.get("status") != STATUS_PLANNED
            ]

        for symbol in ("518880", "588000"):
            if symbol in assets:
                items = assets[symbol].get("items", [])
                assets[symbol].update(copy.deepcopy(TARGETS[symbol]))
                assets[symbol]["items"] = items

        for symbol in STRATEGIC_PLANS:
            assets[symbol] = _strategic_asset(symbol, assets.get(symbol))

        ordered_assets = {
            symbol: assets[symbol]
            for symbol in TARGETS
            if symbol in assets
        }
        ordered_assets.update(
            (symbol, asset)
            for symbol, asset in assets.items()
            if symbol not in ordered_assets
        )
        updated["assets"] = ordered_assets
        updated["allocation_scheme"] = {
            "strategic_satellite": copy.deepcopy(STRATEGIC_SATELLITE_ALLOCATION)
        }

    if version < 5:
        assets = updated.setdefault("assets", {})
        for symbol in WIDE_SYMBOLS:
            asset = assets.get(symbol)
            if not asset:
                continue
            asset["plan_note"] = WIDE_PLAN_NOTE
            items = asset.setdefault("items", [])
            existing_numbers = {int(item.get("number") or 0) for item in items}
            if 3 not in existing_numbers:
                items.append(_new_item(symbol, 3, WIDE_CURRENT_AMOUNTS[2]))
            items.sort(key=lambda item: int(item.get("number") or 0))

    if version < 6:
        assets = updated.setdefault("assets", {})
        for symbol in STRATEGIC_PLANS:
            assets[symbol] = _strategic_asset(symbol, assets.get(symbol))
        updated["allocation_scheme"] = {
            "strategic_satellite": copy.deepcopy(STRATEGIC_SATELLITE_ALLOCATION)
        }

    updated["version"] = CURRENT_PLAN_VERSION
    return updated


def plan_item_heading(symbol: str, item: dict) -> str:
    """Return the concise heading used by a purchase-plan cell."""
    planned_date = item.get("planned_date")
    if planned_date:
        return f"第{item['number']}笔 · {planned_date[5:]}"
    if symbol in WIDE_SYMBOLS:
        return f"第{item['number']}笔"
    round_number = (int(item["number"]) - 1) // 3 + 1
    round_item = (int(item["number"]) - 1) % 3 + 1
    return f"第{round_number}轮 · {round_item}"


def _find_item(plan: dict, item_id: str) -> dict:
    for asset in plan.get("assets", {}).values():
        for item in asset.get("items", []):
            if item.get("id") == item_id:
                return item
    raise ValueError(f"未找到计划项：{item_id}")


def mark_item_bought(
    plan: dict,
    item_id: str,
    confirmed_date: str,
    split_dates: list[str] | None = None,
    execution_type: str = EXECUTION_ON_PLAN,
    deviation_reason: str | None = None,
) -> dict:
    updated = copy.deepcopy(plan)
    item = _find_item(updated, item_id)
    if item.get("status") == STATUS_RECONCILED:
        raise ValueError("已对账的计划项不能重复标记")
    dates = [str(value) for value in (split_dates or [confirmed_date]) if value]
    if not dates:
        raise ValueError("至少需要一个买入日期")
    if execution_type not in {EXECUTION_ON_PLAN, EXECUTION_DEVIATION}:
        raise ValueError("执行类型必须是按计划或偏离计划")
    item["status"] = STATUS_PENDING
    item["confirmed_date"] = dates[0]
    item["confirmed_dates"] = dates
    item["actual"] = None
    item["needs_confirmation"] = False
    item["execution_type"] = execution_type
    item["deviation_reason"] = deviation_reason if execution_type == EXECUTION_DEVIATION else None
    return updated


def undo_item_mark(plan: dict, item_id: str) -> dict:
    updated = copy.deepcopy(plan)
    item = _find_item(updated, item_id)
    if item.get("status") == STATUS_RECONCILED:
        raise ValueError("已对账的计划项不能撤销为计划中")
    item["status"] = STATUS_PLANNED
    item["confirmed_date"] = None
    item["confirmed_dates"] = []
    item["actual"] = None
    item["needs_confirmation"] = False
    item["execution_type"] = None
    item["deviation_reason"] = None
    return updated


def _date_text(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _trade_key(symbol: str, entry: dict, index: int) -> str:
    return "|".join(
        (
            symbol,
            _date_text(entry.get("date")) or "",
            str(entry.get("qty", "")),
            str(entry.get("price", "")),
            str(index),
        )
    )


def _confirmed_dates(item: dict) -> list[str]:
    dates = item.get("confirmed_dates")
    if isinstance(dates, list) and dates:
        return [_date_text(value) for value in dates if _date_text(value)]
    confirmed_date = _date_text(item.get("confirmed_date"))
    return [confirmed_date] if confirmed_date else []


def _actual_trade_keys(actual: dict | None) -> set[str]:
    if not actual:
        return set()
    keys = actual.get("trade_keys")
    if isinstance(keys, list):
        return {str(key) for key in keys if key}
    key = actual.get("trade_key")
    return {str(key)} if key else set()


def reconcile_purchase_plan(plan: dict, trades: dict) -> dict:
    """Conservatively link a pending cell only when date and trade are unique."""
    updated = copy.deepcopy(plan)
    used_keys = {
        key
        for asset in updated.get("assets", {}).values()
        for item in asset.get("items", [])
        for key in _actual_trade_keys(item.get("actual"))
    }

    for symbol, asset in updated.get("assets", {}).items():
        for item in asset.get("items", []):
            if item.get("status") != STATUS_PENDING:
                continue
            item["needs_confirmation"] = False

        buys_by_date: dict[str, list[tuple[str, dict]]] = {}
        for index, entry in enumerate((trades or {}).get(symbol, [])):
            if entry.get("type") != "buy":
                continue
            key = _trade_key(symbol, entry, index)
            if key in used_keys:
                continue
            trade_date = _date_text(entry.get("date"))
            if trade_date:
                buys_by_date.setdefault(trade_date, []).append((key, entry))

        for item in asset.get("items", []):
            if item.get("status") != STATUS_PENDING:
                continue
            dates = _confirmed_dates(item)
            if not dates:
                continue

            candidates: list[tuple[str, dict]] = []
            unresolved = False
            ambiguous = False
            for confirmed_date in dates:
                day_candidates = [
                    candidate
                    for candidate in buys_by_date.get(confirmed_date, [])
                    if candidate[0] not in used_keys
                ]
                if len(day_candidates) == 1:
                    candidates.append(day_candidates[0])
                else:
                    unresolved = True
                    ambiguous = ambiguous or len(day_candidates) > 1

            if unresolved:
                item["needs_confirmation"] = ambiguous
                continue

            fills = []
            total_qty = 0
            total_amount = 0.0
            for key, entry in candidates:
                qty = int(entry.get("qty") or 0)
                price = float(entry.get("price") or 0)
                amount = float(entry.get("amount") if entry.get("amount") is not None else qty * price)
                fills.append(
                    {
                        "date": _date_text(entry.get("date")),
                        "qty": qty,
                        "price": price,
                        "amount": amount,
                        "trade_key": key,
                    }
                )
                total_qty += qty
                total_amount += amount

            if not fills:
                continue
            keys = [fill["trade_key"] for fill in fills]
            item["status"] = STATUS_RECONCILED
            item["needs_confirmation"] = False
            item["actual"] = {
                "date": fills[0]["date"],
                "dates": [fill["date"] for fill in fills],
                "qty": total_qty,
                "price": total_amount / total_qty if total_qty else 0.0,
                "amount": total_amount,
                "fills": fills,
                "trade_key": keys[0] if len(keys) == 1 else "|".join(keys),
                "trade_keys": keys,
            }
            used_keys.update(keys)
    return updated


def calculate_open_quantity(entries: list[dict] | None) -> int:
    quantity = 0
    for entry in entries or []:
        qty = int(entry.get("qty") or 0)
        quantity += qty if entry.get("type") == "buy" else -qty
    return max(quantity, 0)


def summarize_plan(plan: dict) -> dict:
    items = [
        item
        for asset in plan.get("assets", {}).values()
        for item in asset.get("items", [])
    ]
    planned_total = sum(float(item.get("planned_amount") or 0) for item in items)
    confirmed_amount = sum(
        float(item.get("planned_amount") or 0)
        for item in items
        if item.get("status") in {STATUS_PENDING, STATUS_RECONCILED}
    )
    return {
        "planned_total": planned_total,
        "confirmed_amount": confirmed_amount,
        "remaining_amount": planned_total - confirmed_amount,
        "confirmed_count": sum(item.get("status") in {STATUS_PENDING, STATUS_RECONCILED} for item in items),
        "total_count": len(items),
    }


def build_position_progress(plan: dict, trades: dict, latest_prices: dict) -> dict:
    """Build independent, fixed-target position observations."""
    result = {}
    for symbol, asset in plan.get("assets", {}).items():
        target = float(asset.get("target") or 0)
        quantity = calculate_open_quantity((trades or {}).get(symbol, []))
        price = (latest_prices or {}).get(symbol)
        price_available = price is not None and not (isinstance(price, float) and math.isnan(price))
        market_value = quantity * float(price) if price_available else None
        pending_estimate = sum(
            float(item.get("planned_amount") or 0)
            for item in asset.get("items", [])
            if item.get("status") == STATUS_PENDING and not item.get("needs_confirmation")
        )
        display_value = (market_value or 0.0) + pending_estimate
        result[symbol] = {
            "name": asset.get("name", symbol),
            "color": asset.get("color", "#475467"),
            "soft_color": asset.get("soft_color", "#eaecf0"),
            "target": target,
            "open_quantity": quantity,
            "price": float(price) if price_available else None,
            "price_available": price_available,
            "market_value": market_value,
            "pending_estimate": pending_estimate,
            "display_value": display_value,
            "gap": max(target - display_value, 0.0),
            "is_overweight": display_value > target,
            "ratio": display_value / target if target else 0.0,
        }
    return result
