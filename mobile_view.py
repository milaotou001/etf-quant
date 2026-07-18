"""Pure configuration helpers for the private mobile Streamlit view."""
from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable, Mapping

from purchase_plan import CURRENT_PLAN_VERSION


FULL_PAGE_OPTIONS = [
    "状态与图表",
    "复盘日志",
    "策略回测",
    "策略规则",
    "半年买入计划",
    "组合复盘",
    "战略方向",
]
READ_ONLY_PAGE_OPTIONS = ["状态与图表", "半年买入计划"]


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
