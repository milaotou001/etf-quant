"""上交所 ETF 日频份额观察：只描述份额变化，不生成交易判断。"""
from __future__ import annotations

import os
from collections.abc import Callable

import akshare as ak
import pandas as pd


CORE_SSE_ETFS = {"563360", "510300", "518880", "588000"}
# 暂不在日常 CLI/Streamlit 面板展示；行业 ETF 接入后可重新启用。
SHARE_OBSERVATION_ENABLED = False
NEUTRAL_BAND_PCT = 0.5
CACHE_COLUMNS = ["date", "symbol", "name", "etf_type", "shares"]
DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "cache", "sse_etf_shares.csv"
)


def _period_change(values: pd.Series, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    base = values.iloc[-1 - periods]
    latest = values.iloc[-1]
    if pd.isna(base) or pd.isna(latest) or base == 0:
        return None
    return float((latest / base - 1) * 100)


def _classify(change_5d: float | None, change_20d: float | None) -> str:
    if change_5d is None or change_20d is None:
        return "数据不足"
    if (
        abs(change_5d) <= NEUTRAL_BAND_PCT
        and abs(change_20d) <= NEUTRAL_BAND_PCT
    ):
        return "基本平稳"
    if change_5d > 0 and change_20d > 0:
        return "中短期均增加"
    if change_5d < 0 and change_20d < 0:
        return "中短期均减少"
    return "方向分化"


def _explain(state: str) -> str:
    messages = {
        "中短期均增加": (
            "近5日和近20日份额均增加，说明该ETF的创建份额持续上升；"
            "份额增加不等于价格必然上涨。"
        ),
        "中短期均减少": (
            "近5日和近20日份额均减少，说明该ETF份额持续收缩；"
            "份额减少不等于价格必然下跌。"
        ),
        "方向分化": (
            "近5日与近20日份额方向不一致，暂未形成一致趋势；"
            "份额变化不等于价格方向。"
        ),
        "基本平稳": (
            "近5日和近20日份额变化都在±0.5%内，当前基本平稳；"
            "该中性区只用于过滤微小变化。"
        ),
        "数据不足": "有效份额历史不足，暂不判断中短期方向。",
    }
    return messages[state]


def _prepare_history(history: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=["symbol", "shares"])
    frame = history.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.set_index("date")
    else:
        frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
    frame["shares"] = pd.to_numeric(frame["shares"], errors="coerce")
    frame = frame[
        (frame["symbol"] == symbol) & frame.index.notna() & frame["shares"].notna()
    ]
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.sort_index()


def build_share_observation(
    history: pd.DataFrame,
    symbol: str,
    market_date: pd.Timestamp | None = None,
) -> dict | None:
    """把份额历史转换成 CLI 和页面可共用的客观观察结果。"""
    symbol = str(symbol).zfill(6)
    frame = _prepare_history(history, symbol)
    if frame.empty:
        return None

    values = frame["shares"]
    latest_date = pd.Timestamp(frame.index[-1]).normalize()
    requested_date = (
        pd.Timestamp(market_date).normalize() if market_date is not None else latest_date
    )
    daily_change = _period_change(values, 1)
    change_5d = _period_change(values, 5)
    change_20d = _period_change(values, 20)
    state = _classify(change_5d, change_20d)

    return {
        "symbol": symbol,
        "latest_shares": float(values.iloc[-1]),
        "daily_change_pct": daily_change,
        "change_5d_pct": change_5d,
        "change_20d_pct": change_20d,
        "state": state,
        "explanation": _explain(state),
        "source": "上交所官方日频基金份额",
        "latest_date": latest_date,
        "market_date": requested_date,
        "lag_days": max(0, (requested_date - latest_date).days),
    }


def _normalize_sse_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=CACHE_COLUMNS)
    renamed = raw.rename(
        columns={
            "统计日期": "date",
            "基金代码": "symbol",
            "基金简称": "name",
            "ETF类型": "etf_type",
            "基金份额": "shares",
        }
    ).copy()
    if not {"date", "symbol", "shares"}.issubset(renamed.columns):
        return pd.DataFrame(columns=CACHE_COLUMNS)
    for column in ("name", "etf_type"):
        if column not in renamed.columns:
            renamed[column] = ""
    result = renamed[CACHE_COLUMNS]
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["symbol"] = result["symbol"].astype(str).str.zfill(6)
    result["shares"] = pd.to_numeric(result["shares"], errors="coerce")
    result = result.dropna(subset=["date", "symbol", "shares"])
    return result.drop_duplicates(["date", "symbol"], keep="last")


def fetch_sse_share_date(date: str) -> pd.DataFrame:
    """获取指定交易日的全部上交所 ETF 份额并统一字段。"""
    return _normalize_sse_frame(ak.fund_etf_scale_sse(date=date))


def _read_cache(cache_path: str) -> pd.DataFrame:
    if not os.path.exists(cache_path):
        return pd.DataFrame(columns=CACHE_COLUMNS)
    try:
        return _normalize_sse_frame(pd.read_csv(cache_path))
    except (OSError, ValueError, pd.errors.ParserError):
        return pd.DataFrame(columns=CACHE_COLUMNS)


def _write_cache_safely(frame: pd.DataFrame, cache_path: str) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    temp_path = f"{cache_path}.tmp"
    frame.sort_values(["date", "symbol"]).to_csv(temp_path, index=False)
    os.replace(temp_path, cache_path)


def load_share_observation(
    symbol: str,
    trading_dates: pd.Index,
    force_refresh: bool = False,
    cache_path: str | None = None,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
) -> dict | None:
    """补齐最近 25 个交易日份额，失败时保留并使用已有缓存。"""
    symbol = str(symbol).zfill(6)
    if symbol not in CORE_SSE_ETFS:
        return None

    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates, errors="coerce"))
    dates = dates[dates.notna()].normalize().unique().sort_values()[-25:]
    if len(dates) == 0:
        return None

    path = cache_path or DEFAULT_CACHE_PATH
    fetch = fetcher or fetch_sse_share_date
    cached = _read_cache(path)
    cached_dates = set(pd.to_datetime(cached["date"]).dt.normalize())
    target_dates = [d for d in dates if d not in cached_dates]
    if force_refresh and dates[-1] not in target_dates:
        target_dates.append(dates[-1])

    fetched_frames = []
    errors = []
    for date in target_dates:
        date_text = pd.Timestamp(date).strftime("%Y%m%d")
        try:
            fresh = _normalize_sse_frame(fetch(date_text))
            if fresh.empty:
                errors.append(f"{date_text}: 返回空数据")
                continue
            fetched_frames.append(fresh)
        except Exception as exc:
            errors.append(f"{date_text}: {exc}")

    combined = cached
    if fetched_frames:
        fresh_all = pd.concat(fetched_frames, ignore_index=True)
        refreshed_dates = set(fresh_all["date"].dt.normalize())
        if not combined.empty:
            combined = combined[~combined["date"].dt.normalize().isin(refreshed_dates)]
        combined = pd.concat([combined, fresh_all], ignore_index=True)
        combined = combined.drop_duplicates(["date", "symbol"], keep="last")
        _write_cache_safely(combined, path)

    observation = build_share_observation(combined, symbol, dates[-1])
    if observation is None:
        return None
    observation["freshness"] = "current" if fetched_frames else "cached"
    observation["refresh_error"] = " | ".join(errors)
    observation["cache_path"] = path
    return observation
