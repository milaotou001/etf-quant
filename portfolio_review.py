"""轻量组合复盘：计划交易贡献记分卡与当前持仓压力回放。"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd


ATTRIBUTION_START = pd.Timestamp("2026-07-18")
ACCOUNT_BASE_AMOUNT = 285_000.0
DRAWDOWN_BUDGET = 42_750.0
CONCENTRATION_LIMIT = 0.40

CLUSTER_SYMBOLS = {
    "A股宽基": {"563360", "510300"},
    "科技成长": {"588000", "159995", "159819"},
    "黄金": {"518880"},
    "产业卫星": {"561380", "516150", "159570"},
}

COMPARATOR_BY_SYMBOL = {
    "563360": "510300",
    "510300": "563360",
    "561380": "159326",
    "516150": "516780",
    "159570": "159567",
    "159995": "159801",
    "159819": "515070",
}


def risk_cluster(symbol: str) -> str:
    for cluster, symbols in CLUSTER_SYMBOLS.items():
        if symbol in symbols:
            return cluster
    return "其他观察"


def _close_series(frame) -> pd.Series | None:
    if frame is None:
        return None
    series = frame["close"] if isinstance(frame, pd.DataFrame) else frame
    series = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if series.empty:
        return None
    series.index = pd.DatetimeIndex(series.index)
    return series


def _price_on_or_after(series: pd.Series | None, value) -> float | None:
    if series is None:
        return None
    available = series[series.index >= pd.Timestamp(value)]
    return None if available.empty else float(available.iloc[0])


def _price_on_or_before(series: pd.Series | None, value) -> float | None:
    if series is None:
        return None
    available = series[series.index <= pd.Timestamp(value)]
    return None if available.empty else float(available.iloc[-1])


def _return_pct(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return (end / start - 1) * 100


def build_attribution_rows(
    plan: dict,
    price_frames: dict,
    as_of=None,
    start_date=ATTRIBUTION_START,
) -> list[dict]:
    """Build independent scorecards for reconciled plan trades after the official start."""
    cutoff = pd.Timestamp(start_date)
    end_date = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()
    closes = {symbol: _close_series(frame) for symbol, frame in (price_frames or {}).items()}
    benchmark = closes.get("510300")
    rows = []

    for symbol, asset in (plan or {}).get("assets", {}).items():
        selected = closes.get(symbol)
        for item in asset.get("items", []):
            actual = item.get("actual") or {}
            actual_date = actual.get("date")
            if item.get("status") != "reconciled" or not actual_date:
                continue
            actual_date = pd.Timestamp(actual_date)
            if actual_date < cutoff or actual_date > end_date:
                continue

            actual_price = float(actual.get("price") or 0)
            amount = float(actual.get("amount") or 0)
            current_price = _price_on_or_before(selected, end_date)
            selected_return = _return_pct(actual_price, current_price)
            benchmark_start = _price_on_or_after(benchmark, actual_date)
            benchmark_end = _price_on_or_before(benchmark, end_date)
            benchmark_return = _return_pct(benchmark_start, benchmark_end)
            direction_excess = (
                selected_return - benchmark_return
                if selected_return is not None and benchmark_return is not None
                else None
            )

            comparator_symbol = COMPARATOR_BY_SYMBOL.get(symbol)
            comparator = closes.get(comparator_symbol) if comparator_symbol else None
            comparator_start = _price_on_or_after(comparator, actual_date)
            comparator_end = _price_on_or_before(comparator, end_date)
            comparator_return = _return_pct(comparator_start, comparator_end)
            etf_selection = (
                selected_return - comparator_return
                if selected_return is not None and comparator_return is not None
                else None
            )

            timing_effect = None
            planned_date = item.get("planned_date")
            planned_price = _price_on_or_after(selected, planned_date) if planned_date else None
            if actual_price and current_price is not None and planned_price:
                actual_value = amount / actual_price * current_price
                planned_value = amount / planned_price * current_price
                timing_effect = actual_value - planned_value

            forward_returns = {}
            if selected is not None:
                position = selected.index.searchsorted(actual_date)
                for window in (20, 60, 120):
                    target = position + window
                    forward_returns[window] = (
                        _return_pct(actual_price, float(selected.iloc[target]))
                        if target < len(selected)
                        else None
                    )

            rows.append(
                {
                    "item_id": item.get("id"),
                    "symbol": symbol,
                    "name": asset.get("name", symbol),
                    "actual_date": actual_date.strftime("%Y-%m-%d"),
                    "amount": amount,
                    "execution_type": item.get("execution_type") or "unclassified",
                    "deviation_reason": item.get("deviation_reason"),
                    "direction_excess_pct": direction_excess,
                    "comparator_symbol": comparator_symbol,
                    "etf_selection_pct": etf_selection,
                    "timing_effect_amount": timing_effect,
                    "forward_returns": forward_returns,
                }
            )
    return rows


def build_cluster_exposure(progress: dict) -> list[dict]:
    grouped = defaultdict(lambda: {"value": 0.0, "pending_estimate": 0.0, "symbols": []})
    for symbol, item in (progress or {}).items():
        cluster = risk_cluster(symbol)
        grouped[cluster]["value"] += float(item.get("display_value") or 0)
        grouped[cluster]["pending_estimate"] += float(item.get("pending_estimate") or 0)
        grouped[cluster]["symbols"].append(symbol)
    order = [*CLUSTER_SYMBOLS, "其他观察"]
    return [
        {"cluster": cluster, **grouped[cluster]}
        for cluster in order
        if grouped[cluster]["value"] or grouped[cluster]["symbols"]
    ]


def run_pressure_replay(
    price_frames: dict,
    position_values: dict,
    lookback: int = 250,
    account_base: float = ACCOUNT_BASE_AMOUNT,
    drawdown_budget: float = DRAWDOWN_BUDGET,
) -> dict:
    """Back-cast today's position amounts and attribute the worst drawdown window."""
    closes = {}
    unavailable = []
    for symbol, amount in (position_values or {}).items():
        if float(amount or 0) <= 0:
            continue
        series = _close_series((price_frames or {}).get(symbol))
        if series is None:
            unavailable.append(symbol)
        else:
            closes[symbol] = series.rename(symbol)

    empty = {
        "sample_days": 0,
        "peak_date": None,
        "trough_date": None,
        "max_drawdown_pct": None,
        "pressure_loss": 0.0,
        "budget_usage_pct": 0.0,
        "over_budget": False,
        "cluster_losses": {},
        "concentration_warning": False,
        "unavailable": unavailable,
    }
    if not closes:
        return empty

    aligned = pd.concat(closes.values(), axis=1, join="inner").dropna().tail(lookback)
    if len(aligned) < 2:
        return {**empty, "sample_days": len(aligned)}

    values = pd.DataFrame(index=aligned.index)
    included_amount = 0.0
    for symbol in aligned.columns:
        amount = float(position_values[symbol])
        included_amount += amount
        values[symbol] = aligned[symbol] * (amount / float(aligned[symbol].iloc[-1]))
    cash = account_base - included_amount
    portfolio = values.sum(axis=1) + cash
    running_peak = portfolio.cummax()
    drawdown = portfolio / running_peak - 1
    trough_date = drawdown.idxmin()
    peak_date = portfolio.loc[:trough_date].idxmax()
    peak_value = float(portfolio.loc[peak_date])
    trough_value = float(portfolio.loc[trough_date])
    pressure_loss = max(peak_value - trough_value, 0.0)

    cluster_losses = defaultdict(float)
    for symbol in values.columns:
        cluster_losses[risk_cluster(symbol)] += float(
            values.loc[peak_date, symbol] - values.loc[trough_date, symbol]
        )
    cluster_losses = dict(cluster_losses)
    positive_loss = sum(max(value, 0.0) for value in cluster_losses.values())
    concentration = any(
        value > 0 and positive_loss > 0 and value / positive_loss > CONCENTRATION_LIMIT
        for value in cluster_losses.values()
    )

    return {
        "sample_days": len(aligned),
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "max_drawdown_pct": pressure_loss / peak_value * 100 if peak_value else 0.0,
        "pressure_loss": pressure_loss,
        "budget_usage_pct": pressure_loss / drawdown_budget * 100 if drawdown_budget else 0.0,
        "over_budget": pressure_loss > drawdown_budget,
        "cluster_losses": cluster_losses,
        "concentration_warning": concentration,
        "unavailable": unavailable,
    }
