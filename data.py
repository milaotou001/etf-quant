"""ETF 数据获取与本地缓存 — 支持 A 股 ETF 和美股 ETF"""
import os
import json
import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
import akshare as ak

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

COLUMNS_MAP = {
    "日期": "date", "开盘": "open", "最高": "high",
    "最低": "low", "收盘": "close", "成交量": "volume",
    "成交额": "amount",
}

SOURCE_ORDER = ["东方财富", "新浪", "腾讯"]


def attach_data_quality(
    df: pd.DataFrame,
    source: str,
    amount_verified: bool,
    freshness: str,
    note: str = "",
) -> pd.DataFrame:
    """在 DataFrame 元数据中保留数据来源与可用于判断的边界。"""
    df.attrs["source"] = source
    df.attrs["amount_verified"] = amount_verified
    df.attrs["data_freshness"] = freshness
    df.attrs["data_note"] = note
    return df


def _cache_meta_path(cache_path: str) -> str:
    return f"{cache_path}.meta.json"


def _write_cache(df: pd.DataFrame, cache_path: str) -> None:
    df.to_csv(cache_path)
    metadata = {
        key: df.attrs.get(key)
        for key in ("source", "amount_verified", "data_freshness", "data_note")
    }
    with open(_cache_meta_path(cache_path), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)


def fetch_klines_eastmoney(symbol: str = "563360") -> pd.DataFrame:
    """东方财富（含成交额，push2his 偶有 IP 级反爬导致不可用）"""
    df = ak.fund_etf_hist_em(symbol=symbol, period="daily", adjust="")
    df.rename(columns=COLUMNS_MAP, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def fetch_klines_sina(symbol: str = "563360") -> pd.DataFrame:
    """新浪（含成交额，成交量股转手）"""
    market_symbol = f"sh{symbol}" if symbol.startswith(("5", "6")) else f"sz{symbol}"
    df = ak.fund_etf_hist_sina(symbol=market_symbol)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()
    df["volume"] = df["volume"] / 100
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def fetch_klines_tencent(symbol: str = "563360") -> pd.DataFrame:
    """腾讯数据源。ETF 的 amount 字段实际为成交量（手），需反推成交额。"""
    market_symbol = f"sh{symbol}" if symbol.startswith(("5", "6")) else f"sz{symbol}"
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist_tx(symbol=market_symbol, start_date=start_date, end_date=end_date)
    # API 返回英文列名：date, open, close, high, low, amount
    # 对 ETF 而言 amount 实际是成交量（手）
    if "amount" in df.columns:
        df.rename(columns={"amount": "volume"}, inplace=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
    df = df.sort_index()
    cols = ["open", "high", "low", "close", "volume"]
    df = df[[c for c in cols if c in df.columns]]
    # 由成交量反推成交额（元），用 (high+low+close)/3 估算均价
    if "volume" in df.columns and "close" in df.columns:
        avg_price = (df["high"] + df["low"] + df["close"]) / 3
        df["amount"] = df["volume"] * avg_price * 100
    return df


def _read_cache(cache_path: str) -> pd.DataFrame:
    df = pd.read_csv(cache_path, parse_dates=["date"], index_col="date")
    metadata = {}
    meta_path = _cache_meta_path(cache_path)
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    attach_data_quality(
        df,
        source="本地缓存",
        amount_verified=bool(metadata.get("amount_verified", False)),
        freshness="cached",
        note=metadata.get("data_note", "缓存来源与成交额口径未验证"),
    )
    if metadata.get("source"):
        df.attrs["origin_source"] = metadata["source"]
    df.attrs["cache_path"] = cache_path
    df.attrs["cache_mtime"] = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
    return df.sort_index()


def _has_amount(df: pd.DataFrame) -> bool:
    return "amount" in df.columns and not df["amount"].dropna().empty


def _cache_is_stale(cached_df: pd.DataFrame | None) -> bool:
    """缓存数据的最新日期是否早于今天（周末则对比周五）。"""
    if cached_df is None or cached_df.empty:
        return True
    today = datetime.now().date()
    if today.weekday() == 5:
        today = today - timedelta(days=1)
    elif today.weekday() == 6:
        today = today - timedelta(days=2)
    last_date = cached_df.index[-1]
    if hasattr(last_date, 'date'):
        last_date = last_date.date()
    else:
        last_date = pd.Timestamp(last_date).date()
    return last_date < today


def fetch_klines_hsi() -> pd.DataFrame:
    """恒生指数 — 新浪港股指数数据"""
    df = ak.stock_hk_index_daily_sina(symbol="HSI")
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def fetch_klines_hsi_yfinance() -> pd.DataFrame:
    """恒生指数 — yfinance（更新更快，用作新浪延迟时的补充）"""
    import yfinance as yf
    ticker = yf.Ticker("^HSI")
    df = ticker.history(period="max")
    if df.empty:
        raise ValueError("yfinance HSI 返回空数据")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    df = df.sort_index()
    df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                       "Close": "close", "Volume": "volume"}, inplace=True)
    df["amount"] = df["volume"]
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def load_data(symbol: str = "563360", force_refresh: bool = False) -> pd.DataFrame:
    """加载数据。缓存1天内有效；本地ETF走东方财富/新浪/腾讯，港股走新浪，DBO走新浪美股，HSI走新浪港股指数。"""
    if symbol == "DBO":
        return _load_dbo(force_refresh)
    if symbol == "HSI":
        return _load_hsi(force_refresh)
    if symbol.startswith("0") and len(symbol) == 5:
        return _load_hk(symbol, force_refresh)

    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    cached_df = None
    if os.path.exists(cache_path):
        cached_df = _read_cache(cache_path)

    if not force_refresh and not _cache_is_stale(cached_df):
        return cached_df

    refresh_errors = []
    fetchers = [
        ("东方财富", fetch_klines_eastmoney),
        ("新浪", fetch_klines_sina),
        ("腾讯", fetch_klines_tencent),
    ]

    best_df = None
    best_date = None
    today = datetime.now().date()

    for source_name, fetcher in fetchers:
        try:
            if source_name != "东方财富":
                time.sleep(random.uniform(0.5, 1.5))
            df = fetcher(symbol)
            if df.empty:
                raise ValueError("返回空数据")
            last_date = df.index[-1]
            if hasattr(last_date, 'date'):
                last_date = last_date.date()
            else:
                last_date = pd.Timestamp(last_date).date()
            # 跳过超过 1 天的陈旧数据
            if (today - last_date).days > 1:
                raise ValueError(f"数据不够新（最新{last_date}），尝试下一数据源")
            amount_verified = source_name in {"东方财富", "新浪"}
            note = "" if amount_verified else "成交额由成交量和均价估算，不用于正式 RVOL 判断"
            attach_data_quality(df, source_name, amount_verified, "current", note)
            df.attrs["_last_date"] = last_date
            if best_date is None or last_date > best_date:
                best_df = df
                best_date = last_date
            # 已拿到最新数据，无需继续
            if last_date == today:
                break
        except Exception as exc:
            refresh_errors.append(f"{source_name}: {exc}")

    if best_df is not None:
        df = best_df
        source = df.attrs["source"]
        if source != "东方财富":
            # 区分：东方财富失败 vs 东方财富数据不如备用源新
            eastmoney_failed = any("东方财富" in e for e in refresh_errors)
            if eastmoney_failed:
                df.attrs["refresh_note"] = f"东方财富刷新失败，已使用{source}数据源"
            else:
                df.attrs["refresh_note"] = f"已使用{source}数据源（数据较新）"
    else:
        if cached_df is not None:
            print(f"数据刷新失败，使用本地缓存：{' | '.join(refresh_errors)}")
            cached_df.attrs["refresh_error"] = " | ".join(refresh_errors)
            return cached_df
        raise RuntimeError(f"所有数据源均失败且无本地缓存：{' | '.join(refresh_errors)}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    _write_cache(df, cache_path)
    df.attrs["cache_path"] = cache_path
    df.attrs["cache_mtime"] = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
    return df


# ══════════════════════════════════════════════
# HSI（恒生指数）— 新浪港股指数 API
# ══════════════════════════════════════════════

def _load_hsi(force_refresh: bool = False) -> pd.DataFrame:
    """恒生指数数据加载。优先 yfinance（更新快），新浪兜底（历史数据全）。"""
    cache_path = os.path.join(CACHE_DIR, "HSI.csv")
    cached_df = None
    if os.path.exists(cache_path):
        cached_df = _read_cache(cache_path)

    if not force_refresh and not _cache_is_stale(cached_df):
        return cached_df

    df = None
    source = None
    errors = []

    # 优先 yfinance（更新更快）
    try:
        df = fetch_klines_hsi_yfinance()
        if not df.empty:
            source = "Yahoo Finance"
    except Exception as exc:
        errors.append(f"yfinance: {exc}")

    # 新浪兜底
    if df is None or df.empty:
        try:
            time.sleep(random.uniform(0.5, 1.5))
            df = fetch_klines_hsi()
            if not df.empty:
                source = "新浪港股"
        except Exception as exc:
            errors.append(f"新浪: {exc}")

    if df is None or df.empty:
        if cached_df is not None:
            cached_df.attrs["refresh_error"] = " | ".join(errors)
            return cached_df
        raise RuntimeError(f"HSI 数据获取失败且无本地缓存：{' | '.join(errors)}")

    amount_verified = source == "新浪港股" and "amount" in df.columns
    note = "" if amount_verified else "成交额不可验证，不用于正式 RVOL 判断"
    attach_data_quality(df, source, amount_verified, "current", note)
    os.makedirs(CACHE_DIR, exist_ok=True)
    _write_cache(df, cache_path)
    df.attrs["cache_path"] = cache_path
    df.attrs["cache_mtime"] = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
    return df


# ══════════════════════════════════════════════
# 港股个股 — akshare stock_hk_daily API
# ══════════════════════════════════════════════

def fetch_klines_hk(symbol: str) -> pd.DataFrame:
    """港股个股日线 — akshare stock_hk_daily（前复权）"""
    df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()
    # API 返回: open, high, low, close, volume, amount
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def _load_hk(symbol: str, force_refresh: bool = False) -> pd.DataFrame:
    """港股个股数据加载，带缓存。数据过期自动刷新。"""
    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    cached_df = None
    if os.path.exists(cache_path):
        cached_df = _read_cache(cache_path)

    if not force_refresh and not _cache_is_stale(cached_df):
        return cached_df

    try:
        time.sleep(random.uniform(0.5, 1.5))
        df = fetch_klines_hk(symbol)
        if df.empty:
            raise ValueError("返回空数据")
        last_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else pd.Timestamp(df.index[-1]).date()
        attach_data_quality(df, "港股个股", False, "current", "实验区数据不参与正式 RVOL 判断")
    except Exception as exc:
        if cached_df is not None:
            cached_df.attrs["refresh_error"] = str(exc)
            return cached_df
        raise RuntimeError(f"{symbol} 港股数据获取失败且无本地缓存：{exc}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    _write_cache(df, cache_path)
    df.attrs["cache_path"] = cache_path
    df.attrs["cache_mtime"] = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
    return df


# ══════════════════════════════════════════════
# DBO（美股 WTI 原油 ETF）— 新浪美股 API
# ══════════════════════════════════════════════

DBO_COLUMNS = {"d": "date", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "a": "amount"}


def _fetch_dbo_sina() -> pd.DataFrame:
    """从新浪美股 API 获取 DBO 日线数据。返回标准格式 DataFrame。"""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    url = (
        "https://stock.finance.sina.com.cn/usstock/api/json_v2.php/"
        "US_MinKService.getDailyK"
        f"?symbol=DBO&type=daily&startdate={start}&enddate={end}"
    )
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("DBO 返回空数据")

    df = pd.DataFrame(data)
    df.rename(columns=DBO_COLUMNS, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    cols = ["open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in cols if c in df.columns]]


def _load_dbo(force_refresh: bool = False) -> pd.DataFrame:
    """DBO 数据加载，带缓存。数据过期自动刷新。"""
    cache_path = os.path.join(CACHE_DIR, "DBO.csv")
    cached_df = None
    if os.path.exists(cache_path):
        cached_df = _read_cache(cache_path)

    if not force_refresh and not _cache_is_stale(cached_df):
        return cached_df

    try:
        time.sleep(random.uniform(0.5, 1.5))
        df = _fetch_dbo_sina()
        if df.empty:
            raise ValueError("返回空数据")
        last_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else pd.Timestamp(df.index[-1]).date()
        attach_data_quality(df, "新浪美股", False, "current", "实验区数据不参与正式 RVOL 判断")
    except Exception as exc:
        if cached_df is not None:
            cached_df.attrs["refresh_error"] = str(exc)
            return cached_df
        raise RuntimeError(f"DBO 数据获取失败且无本地缓存：{exc}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    _write_cache(df, cache_path)
    df.attrs["cache_path"] = cache_path
    df.attrs["cache_mtime"] = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
    return df
