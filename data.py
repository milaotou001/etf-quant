"""563360 A500 ETF 数据获取与本地缓存"""
import os
import pandas as pd
from datetime import datetime, timedelta
import akshare as ak

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

COLUMNS_MAP = {
    "日期": "date", "开盘": "open", "最高": "high",
    "最低": "low", "收盘": "close", "成交量": "volume",
    "成交额": "amount",
}


def fetch_klines(symbol: str = "563360") -> pd.DataFrame:
    """从 akshare 获取日K线数据"""
    df = ak.fund_etf_hist_em(symbol=symbol, period="daily", adjust="")
    df.rename(columns=COLUMNS_MAP, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df = df.sort_index()

    cols = ["open", "high", "low", "close", "volume"]
    available = [c for c in cols if c in df.columns]
    return df[available]


def load_data(symbol: str = "563360", force_refresh: bool = False) -> pd.DataFrame:
    """加载数据，优先走本地缓存。缓存超过1天自动刷新。"""
    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")

    if not force_refresh and os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - mtime < timedelta(days=1):
            df = pd.read_csv(cache_path, parse_dates=["date"], index_col="date")
            if not df.empty:
                return df

    df = fetch_klines(symbol)
    df.to_csv(cache_path)
    return df
