"""检验 ETF 份额变化对现有 RSI/三段战役的增量信息，不修改正式策略。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import filter_signals_by_gap, simulate_campaigns
from dashboard import compute_indicators
from etf_shares import (
    CACHE_COLUMNS,
    DEFAULT_CACHE_PATH,
    _read_cache,
    _write_cache_safely,
    fetch_sse_share_date,
)
from instruments import get_instrument

CORE_SYMBOLS = ["563360", "510300", "518880", "588000"]
FORWARD_WINDOWS = [5, 20, 60]
SHARE_FEATURES = ["share_change_1d", "share_change_5d", "share_change_20d"]


def load_price_cache(symbol: str) -> pd.DataFrame:
    path = ROOT / "cache" / f"{symbol}.csv"
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date").sort_index()
    return compute_indicators(frame, get_instrument(symbol))


def backfill_share_cache(trading_dates: pd.DatetimeIndex) -> pd.DataFrame:
    cached = _read_cache(DEFAULT_CACHE_PATH)
    cached_dates = set(pd.to_datetime(cached["date"]).dt.normalize()) if not cached.empty else set()
    missing = [date for date in trading_dates if date.normalize() not in cached_dates]
    collected: list[pd.DataFrame] = []
    failures: list[str] = []

    for number, date in enumerate(missing, start=1):
        date_text = date.strftime("%Y%m%d")
        try:
            fresh = fetch_sse_share_date(date_text)
            if fresh.empty:
                failures.append(f"{date_text}: empty")
            else:
                collected.append(fresh)
        except Exception as exc:
            failures.append(f"{date_text}: {exc}")

        if collected and (number % 10 == 0 or number == len(missing)):
            new_rows = pd.concat(collected, ignore_index=True)
            refreshed_dates = set(pd.to_datetime(new_rows["date"]).dt.normalize())
            if not cached.empty:
                cached = cached[~pd.to_datetime(cached["date"]).dt.normalize().isin(refreshed_dates)]
            cached = pd.concat([cached, new_rows], ignore_index=True)
            cached = cached.drop_duplicates(["date", "symbol"], keep="last")
            _write_cache_safely(cached[CACHE_COLUMNS], DEFAULT_CACHE_PATH)
            collected.clear()
        if number % 25 == 0 or number == len(missing):
            print(f"share backfill: {number}/{len(missing)} missing dates processed")

    if failures:
        print(f"share backfill warnings: {len(failures)}; first={failures[0]}")
    return _read_cache(DEFAULT_CACHE_PATH)


def forward_drawdown(close: pd.Series, window: int) -> pd.Series:
    values = close.to_numpy(dtype=float)
    result = np.full(len(values), np.nan)
    for index in range(len(values) - window):
        future = values[index + 1:index + window + 1]
        result[index] = (np.min(future) / values[index] - 1) * 100
    return pd.Series(result, index=close.index)


def prepare_symbol_frame(
    symbol: str,
    prices: pd.DataFrame,
    shares: pd.DataFrame,
    lookback: int,
) -> pd.DataFrame:
    share_rows = shares[shares["symbol"].astype(str).str.zfill(6) == symbol].copy()
    share_rows["date"] = pd.to_datetime(share_rows["date"])
    share_rows = share_rows.set_index("date").sort_index()
    frame = prices.join(share_rows[["shares"]], how="inner").tail(lookback).copy()
    frame["symbol"] = symbol
    frame["share_change_1d"] = frame["shares"].pct_change(1) * 100
    frame["share_change_5d"] = frame["shares"].pct_change(5) * 100
    frame["share_change_20d"] = frame["shares"].pct_change(20) * 100
    for window in FORWARD_WINDOWS:
        frame[f"forward_return_{window}d"] = (
            frame["close"].shift(-window) / frame["close"] - 1
        ) * 100
    for window in (20, 60):
        frame[f"forward_drawdown_{window}d"] = forward_drawdown(frame["close"], window)
    return frame


def circular_shift_pvalue(
    x: pd.Series,
    y: pd.Series,
    method: str,
    repetitions: int,
    seed: int,
) -> tuple[float, float, int]:
    pair = pd.concat([x, y], axis=1).dropna()
    if len(pair) < 30:
        return np.nan, np.nan, len(pair)
    left = pair.iloc[:, 0]
    right = pair.iloc[:, 1]
    if method == "spearman":
        left = left.rank(method="average")
        right = right.rank(method="average")
    observed = float(left.corr(right))
    if pd.isna(observed):
        return np.nan, np.nan, len(pair)
    rng = np.random.default_rng(seed)
    null_values = []
    min_shift = min(5, max(1, len(pair) // 4))
    for _ in range(repetitions):
        shift = int(rng.integers(min_shift, len(pair) - min_shift + 1))
        shifted = pd.Series(np.roll(left.to_numpy(), shift), index=left.index)
        null_values.append(float(shifted.corr(right)))
    pvalue = (1 + sum(abs(value) >= abs(observed) for value in null_values)) / (
        repetitions + 1
    )
    return observed, float(pvalue), len(pair)


def benjamini_hochberg(pvalues: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=pvalues.index, dtype=float)
    valid = pvalues.dropna().sort_values()
    if valid.empty:
        return result
    count = len(valid)
    adjusted = valid.to_numpy() * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result.loc[valid.index] = np.minimum(adjusted, 1.0)
    return result


def correlation_table(frames: dict[str, pd.DataFrame], repetitions: int) -> pd.DataFrame:
    rows = []
    analysis_frames = {**frames, "POOLED": pd.concat(frames.values()).sort_index()}
    for symbol, frame in analysis_frames.items():
        for feature in SHARE_FEATURES:
            for window in FORWARD_WINDOWS:
                outcome = f"forward_return_{window}d"
                for method in ("pearson", "spearman"):
                    corr, pvalue, sample = circular_shift_pvalue(
                        frame[feature], frame[outcome], method, repetitions, seed=20260713
                    )
                    rows.append(
                        {
                            "symbol": symbol,
                            "feature": feature,
                            "outcome": outcome,
                            "method": method,
                            "n": sample,
                            "correlation": corr,
                            "pvalue_circular_shift": pvalue,
                        }
                    )
    result = pd.DataFrame(rows)
    result["qvalue_bh"] = benjamini_hochberg(result["pvalue_circular_shift"])
    return result


def summarize_group(frame: pd.DataFrame, dates: list[pd.Timestamp], label: str) -> list[dict]:
    rows = []
    event_rows = frame.loc[frame.index.intersection(dates)].copy()
    for group_name, group in (
        ("全部", event_rows),
        ("份额5日增加", event_rows[event_rows["share_change_5d"] > 0]),
        ("份额5日未增加", event_rows[event_rows["share_change_5d"] <= 0]),
    ):
        row = {"event": label, "group": group_name, "n": len(group)}
        for window in (20, 60):
            returns = group[f"forward_return_{window}d"].dropna()
            drawdowns = group[f"forward_drawdown_{window}d"].dropna()
            row[f"mean_return_{window}d"] = returns.mean() if len(returns) else np.nan
            row[f"win_rate_{window}d"] = (returns > 0).mean() * 100 if len(returns) else np.nan
            row[f"mean_drawdown_{window}d"] = drawdowns.mean() if len(drawdowns) else np.nan
        rows.append(row)
    return rows


def campaign_event_frame(
    frame: pd.DataFrame,
    campaigns: list[dict],
    windows: tuple[int, ...] = (20, 60),
) -> pd.DataFrame:
    """按三笔各占1/3的真实战役成本计算确认后的组合收益与不利波动。"""
    rows = []
    for campaign in campaigns:
        confirmation_date = pd.Timestamp(campaign["entries"][-1]["date"])
        if confirmation_date not in frame.index:
            continue
        confirmation_index = frame.index.get_loc(confirmation_date)
        units = sum((1 / 3) / entry["price"] for entry in campaign["entries"])
        row = {
            "date": confirmation_date,
            "share_change_5d": frame.loc[confirmation_date, "share_change_5d"],
        }
        for window in windows:
            target_index = confirmation_index + window
            if target_index >= len(frame):
                row[f"forward_return_{window}d"] = np.nan
                row[f"forward_drawdown_{window}d"] = np.nan
                continue
            future_close = frame["close"].iloc[
                confirmation_index + 1:target_index + 1
            ]
            row[f"forward_return_{window}d"] = (
                units * frame["close"].iloc[target_index] - 1
            ) * 100
            row[f"forward_drawdown_{window}d"] = (
                units * future_close.min() - 1
            ) * 100
        rows.append(row)
    if not rows:
        columns = ["share_change_5d"]
        for window in windows:
            columns.extend(
                [f"forward_return_{window}d", f"forward_drawdown_{window}d"]
            )
        return pd.DataFrame(
            columns=columns,
            index=pd.DatetimeIndex([], name="date"),
        )
    return pd.DataFrame(rows).set_index("date").sort_index()


def event_tables(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rsi_rows = []
    campaign_rows = []
    for symbol, frame in frames.items():
        instrument = get_instrument(symbol)
        low_dates = filter_signals_by_gap(
            frame,
            instrument.rsi_second_entry,
            min_gap_days=30,
        )
        rsi_rows.extend(summarize_group(frame, low_dates, f"{symbol}_RSI第二观察位"))

        campaigns = [
            item for item in simulate_campaigns(frame, instrument)
            if item["status"] == "complete"
        ]
        campaign_frame = campaign_event_frame(frame, campaigns)
        campaign_rows.extend(
            summarize_group(
                campaign_frame,
                list(campaign_frame.index),
                f"{symbol}_三段战役确认",
            )
        )
    return pd.DataFrame(rsi_rows), pd.DataFrame(campaign_rows)


def pooled_event_summary(table: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if table.empty:
        return table
    rows = []
    for group in ["全部", "份额5日增加", "份额5日未增加"]:
        subset = table[table["group"] == group]
        weights = subset["n"].fillna(0)
        row = {"event": prefix, "group": group, "n": int(weights.sum())}
        for column in [
            "mean_return_20d", "win_rate_20d", "mean_drawdown_20d",
            "mean_return_60d", "win_rate_60d", "mean_drawdown_60d",
        ]:
            valid = subset[column].notna() & (weights > 0)
            row[column] = (
                np.average(subset.loc[valid, column], weights=weights[valid])
                if valid.any()
                else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    return frame[columns].to_markdown(index=False, floatfmt=".3f")


def write_report(
    frames: dict[str, pd.DataFrame],
    correlations: pd.DataFrame,
    rsi_events: pd.DataFrame,
    campaign_events: pd.DataFrame,
    output_dir: Path,
) -> None:
    pooled_corr = correlations[
        (correlations["symbol"] == "POOLED")
        & (correlations["method"] == "spearman")
    ].copy()
    pooled_corr = pooled_corr.sort_values("qvalue_bh")
    rsi_pooled = pooled_event_summary(rsi_events, "四ETF_RSI第二观察位")
    campaign_pooled = pooled_event_summary(campaign_events, "四ETF_三段战役确认")
    coverage = pd.DataFrame(
        [
            {
                "symbol": symbol,
                "start": frame.index.min().date(),
                "end": frame.index.max().date(),
                "rows": len(frame),
            }
            for symbol, frame in frames.items()
        ]
    )

    report = [
        "# ETF份额与原有指标相关性实验",
        "",
        "- Verification Status: ANALYZED",
        "- 数据：上交所官方ETF日频份额 + 本地ETF日K",
        "- 设计：观察性回测，不支持因果结论",
        "",
        "## 样本覆盖",
        "",
        markdown_table(coverage, ["symbol", "start", "end", "rows"]),
        "",
        "## 份额变化与未来收益：合并样本Spearman相关",
        "",
        markdown_table(
            pooled_corr,
            ["feature", "outcome", "n", "correlation", "pvalue_circular_shift", "qvalue_bh"],
        ),
        "",
        "## RSI第二观察位：份额5日方向分组",
        "",
        markdown_table(
            rsi_pooled,
            ["group", "n", "mean_return_20d", "win_rate_20d", "mean_drawdown_20d", "mean_return_60d", "win_rate_60d", "mean_drawdown_60d"],
        ),
        "",
        "## 三段战役右侧确认：份额5日方向分组",
        "",
        markdown_table(
            campaign_pooled,
            ["group", "n", "mean_return_20d", "win_rate_20d", "mean_drawdown_20d", "mean_return_60d", "win_rate_60d", "mean_drawdown_60d"],
        ),
        "",
        "## 解释边界",
        "",
        "- 使用循环移位检验，保留单序列自相关；所有相关性检验统一做Benjamini-Hochberg修正。",
        "- ETF份额与价格可能同时受行情、套利和机构配置影响，不能把相关性解释成资金流导致收益。",
        "- RSI极端事件和完整战役样本可能很少；样本量小于20的分组只作描述，不作为规则依据。",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "etf_share_correlation_report.md").write_text(
        "\n".join(report), encoding="utf-8"
    )
    correlations.to_csv(output_dir / "etf_share_correlations.csv", index=False)
    rsi_events.to_csv(output_dir / "etf_share_rsi_events.csv", index=False)
    campaign_events.to_csv(output_dir / "etf_share_campaign_events.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=250)
    parser.add_argument("--permutations", type=int, default=499)
    args = parser.parse_args()

    prices = {symbol: load_price_cache(symbol) for symbol in CORE_SYMBOLS}
    calendar = pd.DatetimeIndex(
        sorted(
            set().union(
                *(set(frame.index[-args.lookback:]) for frame in prices.values())
            )
        )
    )
    shares = backfill_share_cache(calendar)
    frames = {
        symbol: prepare_symbol_frame(symbol, prices[symbol], shares, args.lookback)
        for symbol in CORE_SYMBOLS
    }
    correlations = correlation_table(frames, args.permutations)
    rsi_events, campaign_events = event_tables(frames)
    output_dir = ROOT / "output" / "etf_share_correlation"
    write_report(frames, correlations, rsi_events, campaign_events, output_dir)
    print(f"report: {output_dir / 'etf_share_correlation_report.md'}")
    print(f"correlation rows: {len(correlations)}")
    print(f"rsi event rows: {len(rsi_events)}")
    print(f"campaign event rows: {len(campaign_events)}")


if __name__ == "__main__":
    main()
