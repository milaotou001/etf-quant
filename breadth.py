"""市场宽度模块：统计指数成分股站上 MA8/MA21 的比例。

数据策略：每日用 index_stock_cons_sina 一次拉取全部成分股收盘价，
写入累积价格历史。MA8/MA21 从历史数据计算，无需逐只查K线。
首次运行历史不足时，从项目已有 cache/{code}.csv 补充。
"""

from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import config

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "breadth")
os.makedirs(CACHE_DIR, exist_ok=True)

BREADTH_INDEX_MAP = {
    "510300": {"index_code": "000300", "name": "沪深300", "use_sina": True},
    "563360": {"index_code": "000510", "name": "A500", "use_sina": False},
    "588000": {"index_code": "000688", "name": "科创50", "use_sina": True},
    "159920": {"index_code": "HSI", "name": "恒生指数", "hk": True, "hk_source": "wiki", "hk_page": "Hang_Seng_Index"},
    "513180": {"index_code": "HSTECH", "name": "恒生科技", "hk": True, "hk_source": "hstech"},
}

_MAIN_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def supports_breadth(symbol: str) -> dict:
    """返回是否适用及原因。不适用时返回 structured reason。"""
    if symbol in BREADTH_INDEX_MAP:
        return {"applicable": True}
    return {"applicable": False, "reason": "该资产不具备股票成分股市场宽度"}


# ══════════════════════════════════════════════
# 成分股列表
# ══════════════════════════════════════════════

def _fetch_constituents_sina(index_code: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.index_stock_cons_sina(index_code)
    if df.empty:
        raise ValueError(f"index_stock_cons_sina({index_code}) 返回空数据")
    if "symbol" not in df.columns and "code" in df.columns:
        df = df.rename(columns={"code": "symbol"})
    df["symbol"] = df["symbol"].astype(str).str.replace(r"^(sh|sz)", "", regex=True)
    return df[["symbol"]]


def _fetch_constituents_generic(index_code: str) -> pd.DataFrame:
    """通过中证指数官方 API 获取成分股，避免 index_stock_cons 的重复/缺失问题。"""
    import akshare as ak
    df = ak.index_stock_cons_csindex(symbol=index_code)
    if df.empty:
        raise ValueError(f"index_stock_cons_csindex({index_code}) 返回空数据")
    # 列名可能乱码，第5列（索引4）是成分券代码
    code_col = df.columns[4]
    result = pd.DataFrame({"symbol": df[code_col].astype(str)})
    result = result.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    return result


def _fetch_constituents_wiki(page_title: str) -> pd.DataFrame:
    """从 Wikipedia 页面抓取恒生指数成分股（SEHK:XXXX 格式）。"""
    import requests
    from bs4 import BeautifulSoup
    url = f"https://en.wikipedia.org/wiki/{page_title}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    for table in soup.find_all("table", class_="wikitable"):
        rows = table.find_all("tr")
        if len(rows) < 20:
            continue
        codes = []
        for row in rows[1:]:
            for td in row.find_all("td"):
                text = td.get_text(strip=True)
                if text.startswith("SEHK:"):
                    code = text.replace("SEHK:", "").zfill(5)
                    codes.append(code)
                    break
        if len(codes) >= 20:
            return pd.DataFrame({"symbol": codes})
    return pd.DataFrame()


# HSTECH 30 只成分股，来源 Investing.com 2026-07，每季检讨时需复核。
_HSTECH_CODES = [
    "01211", "00992", "00981", "00285", "00700", "02382", "00241", "01347",
    "01810", "03690", "00780", "09988", "09999", "09618", "06618", "06690",
    "01024", "09888", "09626", "09961", "09868", "02015", "00020", "09866",
    "09863", "01698", "00300", "09660", "02513", "00100",
]


def _fetch_constituents_hstech() -> pd.DataFrame:
    """返回恒生科技指数 30 只成分股（硬编码，每季检讨后更新）。"""
    return pd.DataFrame({"symbol": _HSTECH_CODES})


def fetch_constituents(index_code: str, use_sina: bool, force_refresh: bool = False,
                      hk: bool = False, hk_source: str | None = None,
                      hk_page: str | None = None) -> pd.DataFrame:
    cache_path = os.path.join(CACHE_DIR, f"{index_code}_constituents.csv")
    if not force_refresh and os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if (datetime.now() - mtime).days < 1:
            df = pd.read_csv(cache_path, dtype={"symbol": str})
            if not df.empty:
                return df
    if hk:
        if hk_source == "wiki" and hk_page:
            df = _fetch_constituents_wiki(hk_page)
        elif hk_source == "hstech":
            df = _fetch_constituents_hstech()
        else:
            raise ValueError(f"未知的 HK 数据源：{hk_source}")
    else:
        fetcher = _fetch_constituents_sina if use_sina else _fetch_constituents_generic
        df = fetcher(index_code)
    df.to_csv(cache_path, index=False)
    return df


# ══════════════════════════════════════════════
# 每日价格快照 — 核心数据源
# ══════════════════════════════════════════════

def _price_history_path(index_code: str) -> str:
    return os.path.join(CACHE_DIR, f"{index_code}_price_history.csv")


def _fetch_today_snapshot(index_code: str, use_sina: bool, symbols: list[str] | None = None,
                           is_hk: bool = False) -> dict[str, float]:
    """拉取全部成分股当日收盘价。Sina 一次 API 全拿；其他指数走新浪 HTTP 批量拉。"""
    import akshare as ak
    if use_sina:
        df = ak.index_stock_cons_sina(index_code)
        if df.empty:
            return {}
        if "symbol" in df.columns:
            syms = df["symbol"].astype(str).str.replace(r"^(sh|sz)", "", regex=True)
        elif "code" in df.columns:
            syms = df["code"].astype(str)
        else:
            return {}
        prices = df["trade"] if "trade" in df.columns else df["close"]
        result = {}
        for sym, price in zip(syms, prices):
            try:
                result[str(sym)] = float(price)
            except (ValueError, TypeError):
                continue
        return result
    if symbols and len(symbols) > 0:
        return _fetch_today_snapshot_sina_http(symbols, is_hk=is_hk)
    return {}


def _fetch_today_snapshot_sina_http(symbols: list[str], is_hk: bool = False) -> dict[str, float]:
    """新浪 HTTP 批量行情 API — 一次请求最多约 800 只，500 只约 2-3 秒完成。
    不走 akshare，直接 requests HTTP GET，无 TLS 指纹问题。
    HK 股票用 hk 前缀，价格在 fields[4]（A 股在 fields[3]）。"""
    import requests

    def _prefix(sym: str) -> str:
        if is_hk:
            return f"hk{sym}"
        return f"sh{sym}" if sym.startswith(("5", "6")) else f"sz{sym}"

    result: dict[str, float] = {}
    chunk_size = 400  # 新浪单次上限约 800，留余量
    headers = {"Referer": "https://finance.sina.com.cn"}
    price_idx = 4 if is_hk else 3  # HK 多一个英文名称字段

    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        codes = [_prefix(s) for s in chunk]
        try:
            url = "http://hq.sinajs.cn/list=" + ",".join(codes)
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            for line in r.text.splitlines():
                line = line.strip()
                if not line.startswith("var hq_str_"):
                    continue
                prefix_end = line.find('="')
                if prefix_end == -1:
                    continue
                raw_code = line[11:prefix_end]  # hk00700 / sh600036 / sz000001
                code = raw_code[2:]  # strip market prefix
                data_start = prefix_end + 2
                data_end = line.find('"', data_start)
                if data_end == -1:
                    continue
                fields = line[data_start:data_end].split(",")
                if len(fields) <= price_idx:
                    continue
                try:
                    price = float(fields[price_idx])
                    if price > 0:
                        result[code] = price
                except (ValueError, TypeError):
                    continue
        except Exception:
            continue

    return result


def update_price_history(index_code: str, today_prices: dict[str, float]) -> None:
    """追加今日价格到累积历史。已存在同日数据则覆盖。"""
    hist_path = _price_history_path(index_code)
    today_str = date.today().isoformat()

    if os.path.exists(hist_path):
        hist = pd.read_csv(hist_path, index_col=0)
        # 去掉今天已有的行
        hist = hist[hist.index != today_str]
    else:
        hist = pd.DataFrame()

    row = pd.DataFrame([today_prices], index=[today_str])
    hist = pd.concat([hist, row])
    hist.to_csv(hist_path)


def load_price_history(index_code: str) -> pd.DataFrame:
    hist_path = _price_history_path(index_code)
    if not os.path.exists(hist_path):
        return pd.DataFrame()
    df = pd.read_csv(hist_path, index_col=0)
    df.index = pd.to_datetime(df.index, format="mixed")
    return df.sort_index()


# ══════════════════════════════════════════════
# 从已有主缓存补充历史 (cache/{code}.csv)
# ══════════════════════════════════════════════

def _backfill_from_main_cache(symbols: list[str], index_code: str) -> None:
    """从项目 cache/{code}.csv 读取已有K线，补充价格历史。只取近60天数据。"""
    hist = load_price_history(index_code)
    existing_dates = set(hist.index.strftime("%Y-%m-%d")) if not hist.empty else set()
    new_data: dict[str, dict[str, float]] = {}  # date -> {symbol: price}
    cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

    for sym in symbols[:500]:  # 补主缓存中所有已有数据
        cache_path = os.path.join(_MAIN_CACHE_DIR, f"{sym}.csv")
        if not os.path.exists(cache_path):
            continue
        try:
            stock_df = pd.read_csv(cache_path, parse_dates=["date"], index_col="date")
        except Exception:
            continue
        if "close" not in stock_df.columns:
            continue
        for idx, row in stock_df.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            if date_str < cutoff or date_str in existing_dates:
                continue
            new_data.setdefault(date_str, {})[sym] = float(row["close"])

    if not new_data:
        return

    backfill = pd.DataFrame(new_data).T
    backfill.index = pd.to_datetime(backfill.index)
    combined = backfill if hist.empty else backfill.combine_first(hist)
    combined.to_csv(_price_history_path(index_code))


# ══════════════════════════════════════════════
# 批量K线补充（首次历史不足时）
# ══════════════════════════════════════════════

def _bulk_fetch_stocks(symbols: list[str], index_code: str, max_fetch: int = 500) -> None:
    """并行拉取成分股K线补充到价格历史。腾讯源（stock_zh_a_hist_tx），15 线程。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    hist = load_price_history(index_code)
    need_fetch = []
    for sym in symbols:
        if sym not in hist.columns or hist[sym].dropna().shape[0] < 21:
            need_fetch.append(sym)

    if not need_fetch:
        return

    new_data: dict[str, dict[str, float]] = {}
    to_fetch = need_fetch[:max_fetch]

    def _get_one(sym):
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        market_sym = f"sh{sym}" if sym.startswith(("5", "6")) else f"sz{sym}"
        import akshare as ak
        import random as _random
        for attempt in range(3):
            try:
                df = ak.stock_zh_a_hist_tx(symbol=market_sym, start_date=start, end_date=end)
                if df is not None and not df.empty:
                    return sym, df
            except Exception:
                pass
            if attempt < 2:
                import time as _time
                _time.sleep(_random.uniform(1.0, 3.0))
        return sym, None

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(_get_one, sym): sym for sym in to_fetch}
        for future in as_completed(futures):
            sym, df = future.result()
            if df is not None and "close" in df.columns:
                for _, row in df.iterrows():
                    d = row["date"]
                    date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                    try:
                        new_data.setdefault(date_str, {})[sym] = float(row["close"])
                    except (ValueError, TypeError):
                        continue

    if not new_data:
        return

    # combine_first：已有数据保留，新数据填补空白格子
    backfill = pd.DataFrame(new_data).T
    backfill.index = pd.to_datetime(backfill.index)
    combined = backfill if hist.empty else backfill.combine_first(hist)
    combined.to_csv(_price_history_path(index_code))


def _bulk_fetch_hk_stocks(symbols: list[str], index_code: str, max_fetch: int = 200) -> None:
    """并行拉取港股成分股K线补充到价格历史。使用 ak.stock_hk_daily（前复权），8 线程。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    hist = load_price_history(index_code)
    need_fetch = []
    for sym in symbols:
        if sym not in hist.columns or hist[sym].dropna().shape[0] < 21:
            need_fetch.append(sym)

    if not need_fetch:
        return

    new_data: dict[str, dict[str, float]] = {}
    to_fetch = need_fetch[:max_fetch]

    def _get_one(sym):
        import akshare as ak
        import random as _random
        for attempt in range(3):
            try:
                df = ak.stock_hk_daily(symbol=sym, adjust="qfq")
                if df is not None and not df.empty:
                    return sym, df
            except Exception:
                pass
            if attempt < 2:
                import time as _time
                _time.sleep(_random.uniform(1.0, 3.0))
        return sym, None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_get_one, sym): sym for sym in to_fetch}
        for future in as_completed(futures):
            sym, df = future.result()
            if df is not None and "close" in df.columns:
                for _, row in df.iterrows():
                    d = row["date"]
                    date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                    try:
                        new_data.setdefault(date_str, {})[sym] = float(row["close"])
                    except (ValueError, TypeError):
                        continue

    if not new_data:
        return

    backfill = pd.DataFrame(new_data).T
    backfill.index = pd.to_datetime(backfill.index)
    combined = backfill if hist.empty else backfill.combine_first(hist)
    combined.to_csv(_price_history_path(index_code))


# ══════════════════════════════════════════════
# 宽度计算
# ══════════════════════════════════════════════

def compute_breadth_from_history(hist: pd.DataFrame, total_stocks: int | None = None) -> dict:
    """从价格历史 DataFrame 计算宽度。total_stocks 为指数实际成分股数。"""
    if total_stocks is None:
        total_stocks = len(hist.columns)
    if hist.empty or len(hist) < 8:
        return {
            "pct_above_ma8": None,
            "pct_above_ma21": None,
            "total_stocks": total_stocks,
            "stocks_with_ma8": 0,
            "stocks_with_ma21": 0,
            "stocks_with_price": 0,
            "history_days": len(hist),
        }

    ma8 = hist.rolling(8).mean().iloc[-1]
    ma21 = hist.rolling(21).mean().iloc[-1] if len(hist) >= 21 else pd.Series(index=hist.columns, dtype=float)
    latest = hist.iloc[-1]

    stocks_with_price = 0
    stocks_with_ma8 = 0
    stocks_with_ma21 = 0
    above_ma8 = 0
    above_ma21 = 0

    for col in hist.columns:
        p = latest[col]
        m8 = ma8[col]
        m21 = ma21[col] if len(hist) >= 21 else np.nan
        if pd.isna(p):
            continue
        stocks_with_price += 1
        if not pd.isna(m8):
            stocks_with_ma8 += 1
            if p > m8:
                above_ma8 += 1
        if not pd.isna(m21):
            stocks_with_ma21 += 1
            if p > m21:
                above_ma21 += 1

    return {
        "pct_above_ma8": round(above_ma8 / stocks_with_ma8 * 100, 1) if stocks_with_ma8 > 0 else None,
        "pct_above_ma21": round(above_ma21 / stocks_with_ma21 * 100, 1) if stocks_with_ma21 > 0 else None,
        "total_stocks": total_stocks,
        "stocks_with_ma8": stocks_with_ma8,
        "stocks_with_ma21": stocks_with_ma21,
        "stocks_with_price": stocks_with_price,
        "history_days": len(hist),
    }


def classify_breadth(pct: float | None) -> str:
    if pct is None:
        return "积累中"
    if pct > config.BREADTH_HOT * 100:
        return "偏热"
    elif pct < config.BREADTH_COLD * 100:
        return "偏冷"
    else:
        return "正常"


# 默认框架（A 股指数用，数据积累中，表述偏保守）
_DEFAULT_FRAMEWORK = {
    "多头市场": {
        "strong": ("追高性价比低", "趋势确认后多数涨幅已兑现。历史数据显示追涨的中期回报往往为负或持平。已在场内的继续观察，不在场内的等回踩。"),
        "neutral": ("涨势集中", "指数强但个股参与面不够。权重股在抬指数，警惕分化后回调。"),
        "deteriorating": ("上涨松动", "多头排列但宽度快速收窄，上涨结构在弱化。注意止盈或减仓信号。"),
    },
    "偏多震荡": {
        "strong": ("反弹有基础", "个股跟上指数，偏多环境中有望继续走好。观察能否形成多头排列，控制仓位参与。"),
        "neutral": ("方向待确认", "偏多但宽度不确认。等更明确信号，控制仓位。"),
        "deteriorating": ("警惕下行", "宽度收窄时偏多结构容易瓦解。注意风险，等待宽度企稳。"),
    },
    "震荡市场": {
        "strong": ("个股活跃但无方向", "指数震荡但多数个股走强。观察能否带动指数突破，目前仍以观望为主。"),
        "neutral": ("多看少动", "指数和宽度均无方向。耐心等待，不勉强操作。"),
        "deteriorating": ("偏谨慎", "指数震荡但多数个股走弱。警惕向下突破，控制风险。"),
    },
    "偏空震荡": {
        "strong": ("反弹乏力", "宽度改善在偏空环境中往往不可靠。可能的反弹更适合减仓而非追入。"),
        "neutral": ("卖压减缓", "偏空但宽度未恶化。卖压在消退，可能是机会窗口但不要急于进场。"),
        "deteriorating": ("持续偏弱", "指数偏空且宽度恶化。下跌面广，继续等待，不抄底。"),
    },
    "空头市场": {
        "strong": ("底部试探", "空头排列中宽度走强，可能是底部信号。等确认后再动，不要左侧抄底。"),
        "neutral": ("卖压衰竭", "空头但宽度稳定。卖方力量在消退，可关注反转但不急于进场。"),
        "deteriorating": ("系统性下跌", "空头排列叠加宽度恶化。不进场，等宽度企稳后再考虑。"),
    },
}

# 恒生指数框架（85只成分股，3100+天回测）
_HSI_FRAMEWORK = {
    "多头市场": {
        "strong": ("追高性价比低", "447天样本，20日均-0.3%，胜51%。HSI 多头确认后追涨，中期回报接近零甚至为负。趋势已计价，不再有优势。"),
        "neutral": ("信号偏弱", "仅55天样本，20日均基本持平。数据不足以给出强结论，但至少说明多头+宽度中性在 HSI 中不常见。"),
        "deteriorating": ("上涨松动", "82天样本，20日均-0.4%，胜51%。多头排列但宽度收窄，上涨结构在弱化，注意止盈。"),
    },
    "偏多震荡": {
        "strong": ("偏积极", "311天样本，20日均+0.6%，胜56%。是偏多震荡中表现最好的格子，但收益幅度有限，不宜重仓。"),
        "neutral": ("方向偏积极", "76天样本，20日均+0.4%，胜54%。方向偏积极但幅度不大，控制仓位等待更明确信号。"),
        "deteriorating": ("警惕下行", "94天样本，20日均-0.3%，胜44%。宽度收窄时偏多结构容易瓦解，注意风险。"),
    },
    "震荡市场": {
        "strong": ("个股活跃但无方向", "496天样本，20日均+0.1%，胜45%。指数震荡宽度偏强，个股活跃但未能带动指数突破，观望为宜。"),
        "neutral": ("多看少动", "161天样本，20日均+0.4%，胜47%。指数和宽度均无方向，没有明显的交易信号。"),
        "deteriorating": ("偏谨慎", "374天样本，20日均-0.3%，胜44%。震荡+宽度恶化，多数个股走弱，警惕向下突破。"),
    },
    "偏空震荡": {
        "strong": ("反弹乏力", "157天样本，20日均-0.7%，胜44%。宽度改善在偏空环境中不可靠，反弹常常是陷阱。"),
        "neutral": ("卖压减缓", "127天样本，20日均基本持平，胜53%。卖压消退但反弹未至，可观察等待，不急于进场。"),
        "deteriorating": ("超跌反弹可能", "241天样本，20日均+0.3%，胜52%。HSI 在此格反有微弱正收益——极度悲观后可能出现超跌反弹。但幅度有限，不要过度依赖。"),
    },
    "空头市场": {
        "strong": ("底部试探", "81天样本，20日均-0.1%，胜54%。宽度率先改善可能是底部信号，但空头趋势未扭转，等确认后再动。"),
        "neutral": ("最佳反弹窗口", "156天样本，20日均+1.7%，胜65%。HSI 表现最好的格子：卖压衰竭时空头尾声的反弹性价比最高。不是号召抄底，而是说这个组合历史上赔率最好。"),
        "deteriorating": ("极度悲观后反弹", "233天样本，20日均+1.5%，胜61%。HSI 在看似最差的环境里反而有较好的中期回报——市场极度悲观时往往已接近底部。"),
    },
}

# 恒生科技框架（30只成分股，1400+天回测）
_HSTECH_FRAMEWORK = {
    "多头市场": {
        "strong": ("追高性价比低", "145天样本，20日均-1.0%，胜41%。HSTECH 多头确认后追涨，中期大概率亏损。科技股弹性大，趋势已充分计价。"),
        "neutral": ("样本不足", "仅11天样本，统计意义极弱。HSTECH 多头市中很少出现宽度中性——科技股上涨时通常大面积跟涨。"),
        "deteriorating": ("警惕回调", "32天样本，20日均-0.6%，胜34%。多头松动时科技股回调风险高，注意止盈。"),
    },
    "偏多震荡": {
        "strong": ("最好的格子", "103天样本，20日均+1.2%，胜52%。HSTECH 表现最好的状态：个股跟得上指数，反弹有基础。但仍需控制仓位——胜率仅略过半。"),
        "neutral": ("样本不足", "仅15天样本，20日均-3.1%。数据太少不做判断，但值得注意：HSTECH 偏多时宽度中性极为罕见。"),
        "deteriorating": ("警惕下行", "42天样本，20日均-0.5%，胜43%。宽度收窄时 HSTECH 偏多结构容易瓦解，保持警惕。"),
    },
    "震荡市场": {
        "strong": ("个股活跃但无方向", "243天样本，20日均+0.1%，胜44%。震荡中宽度偏强但未能带动指数突破，观望。"),
        "neutral": ("高波动无方向", "57天样本，20日均+1.7%但胜率仅37%。高波动、方向不确定，不适宜操作。"),
        "deteriorating": ("偏谨慎", "172天样本，20日均-1.1%，胜33%。震荡+宽度恶化，多数个股走弱，HSTECH 下行风险加大。"),
    },
    "偏空震荡": {
        "strong": ("反弹陷阱", "65天样本，20日均-2.0%，胜48%。宽度改善在 HSTECH 偏空环境中不但不可靠，反而是陷阱——反弹常常是出货机会。"),
        "neutral": ("持续偏弱", "76天样本，20日均-2.1%，胜38%。HSTECH 偏空+宽度中性是表现最差的格子之一，不要幻想反转。"),
        "deteriorating": ("超跌反弹可能", "107天样本，20日均+1.2%，胜48%。看似矛盾——偏空+恶化反而正收益。HSTECH 极度悲观后弹性大，但波动也大，不要作为主要依据。"),
    },
    "空头市场": {
        "strong": ("持续偏弱", "35天样本，20日均-3.7%，胜仅34%。HSTECH 空头趋势是主要矛盾，宽度走强不足以扭转。这是最危险的格子之一。"),
        "neutral": ("卖压衰竭", "108天样本，20日均+1.4%，胜58%。卖压消退后 HSTECH 反弹弹性大。空头尾声、宽度企稳——值得关注但不等于是买点。"),
        "deteriorating": ("分歧较大", "157天样本，20日均-0.6%，胜54%。收益为负但胜率过半——方向分歧大。HSTECH 在极端空头环境中行为不稳定，谨慎对待。"),
    },
}

# 沪深300框架（300只成分股，1939天回测，2018-2026覆盖多轮牛熊）
_CSI300_FRAMEWORK = {
    "多头市场": {
        "strong": ("趋势已确认", "261天样本，20日均+0.1%胜49%。多头确认后追涨空间极为有限，趋势已充分计价，已在场内的继续观察。"),
        "neutral": ("涨势集中", "77天样本，20日均基本持平胜48%。沪深300多头市中宽度中性不常见——权重股拉升时个股常大范围跟涨。"),
        "deteriorating": ("回调即机会", "75天样本，20日均+1.4%胜48%。多头市中宽度短期恶化往往是买点而非卖点，但胜率不足一半需注意择时。"),
    },
    "偏多震荡": {
        "strong": ("反弹有基础", "170天样本，20日均+0.3%胜61%。偏多+宽度强时胜率最好，但收益幅度有限——适合控制仓位参与。"),
        "neutral": ("方向待确认", "72天样本，20日均基本持平胜50%。偏多但宽度不确认，等更明确信号。"),
        "deteriorating": ("宽度收窄但偏积极", "95天样本，20日均+0.7%胜52%。偏多+恶化时沪深300并未走弱，权重股可能仍在支撑。"),
    },
    "震荡市场": {
        "strong": ("个股活跃，偏积极", "258天样本，20日均+0.9%胜60%。震荡+宽度强是沪深300表现较好的组合——个股活跃往往能带动指数突破。"),
        "neutral": ("多看少动", "182天样本，20日均基本持平胜52%。方向不明确，耐心等待。"),
        "deteriorating": ("偏谨慎", "201天样本，20日均-0.1%胜42%。震荡+恶化是沪深300少数收益为负的格子，警惕向下。"),
    },
    "偏空震荡": {
        "strong": ("可能筑底", "70天样本，20日均+0.8%胜50%。宽度改善时偏空环境可能接近尾声。"),
        "neutral": ("卖压减缓", "96天样本，20日均+0.7%胜59%。卖压消退，可关注反转信号。"),
        "deteriorating": ("偏积极", "85天样本，20日均+0.3%胜50%。偏空+恶化时沪深300表现平稳——极度悲观后常有反弹。"),
    },
    "空头市场": {
        "strong": ("底部区域", "39天样本，20日均+7.8%胜69%。空头+宽度强在沪深300中极为罕见且回报极高——是历史赔率最好的信号之一。"),
        "neutral": ("最佳反弹窗口", "96天样本，20日均+3.8%胜59%。空头尾声+宽度企稳是赔率很好的组合——卖压衰竭时反弹概率和幅度均较高。"),
        "deteriorating": ("极度悲观后反弹", "162天样本，20日均+4.3%胜54%。空头+恶化在沪深300中反而预示强反弹——市场最悲观时往往离底不远。"),
    },
}

# A500框架（500只成分股，1057天回测，2025-2026年数据，周期覆盖不完整）
_A500_FRAMEWORK = {
    "多头市场": {
        "strong": ("趋势健康", "185天样本，20日均+1.9%胜62%。A500多头+宽度强趋势健康，但指数仅运行~1.5年，数据周期偏短。"),
        "neutral": ("涨势偏集中", "65天样本，20日均+1.2%胜62%。A500多头+宽度中性时仍偏积极。"),
        "deteriorating": ("回调即机会", "68天样本，20日均+2.7%胜68%。多头市中宽度短期恶化可能是加仓机会。"),
    },
    "偏多震荡": {
        "strong": ("信号偏弱", "135天样本，20日均-1.4%胜40%。A500偏多+宽度强反而是负收益——偏多时追强可能短期被套。"),
        "neutral": ("方向偏积极", "72天样本，20日均+0.9%胜58%。方向偏积极，控制仓位。"),
        "deteriorating": ("积极信号", "63天样本，20日均+2.6%胜76%。A500偏多+宽度恶化反而是好信号——可能权重股在蓄力。"),
    },
    "震荡市场": {
        "strong": ("最好的格子", "142天样本，20日均+3.5%胜91%。A500震荡+宽度强是表现最好的组合——个股全面活跃往往意味着指数即将突破。"),
        "neutral": ("多看少动", "64天样本，20日均+0.8%胜56%。方向不明确，耐心等待。"),
        "deteriorating": ("中性偏弱", "151天样本，20日均+0.2%胜52%。震荡+恶化时A500基本持平，无明显方向。"),
    },
    "偏空震荡": {
        "strong": ("可能筑底", "26天样本，20日均+3.7%。A500历史太短，偏空环境样本极少，不要过度解读。"),
        "neutral": ("数据不足", "41天样本，20日均+6.5%但全样本正值——A500尚未经历完整市场周期。"),
        "deteriorating": ("数据不足", "33天样本，20日均+6.5%。A500历史太短，偏空格子均不可靠。"),
    },
    "空头市场": {
        "strong": ("数据不足", "无样本。A500成立以来尚未出现空头+宽度强组合。"),
        "neutral": ("数据不足", "仅6天样本，统计意义为零。A500空头市场样本极少。"),
        "deteriorating": ("数据不足", "仅6天样本。A500历史太短，空头格子均不可靠。"),
    },
}

# 科创50框架（50只成分股，1939天回测，覆盖多轮牛熊，高Beta特性）
_KC50_FRAMEWORK = {
    "多头市场": {
        "strong": ("趋势已确认", "225天样本，20日均+2.5%胜45%。科创50弹性大，多头+宽度强时中期正收益但胜率不高——波动大是双刃剑。"),
        "neutral": ("信号偏弱", "40天样本，20日均基本持平。科创50多头市中宽度中性极为罕见。"),
        "deteriorating": ("回调即机会", "80天样本，20日均+7.4%胜58%。科创50多头市中宽度恶化往往是好的入场点——科技股回调后弹性更大。"),
    },
    "偏多震荡": {
        "strong": ("信号偏弱", "161天样本，20日均-0.3%胜45%。更多数据后确认：科创50偏多+宽度强未必是好信号，追强可能短期被套。"),
        "neutral": ("方向待确认", "41天样本，20日均+0.2%但胜率仅31%。数据太少，方向不确定。"),
        "deteriorating": ("积极信号", "76天样本，20日均+3.8%胜50%。科创50偏多+恶化时中期正收益——科技股回调后机构往往加仓。"),
    },
    "震荡市场": {
        "strong": ("个股活跃", "342天样本，20日均+3.7%胜46%。科创50震荡+宽度强时中期收益高但胜率近半——高波动带来高收益也带来高风险。"),
        "neutral": ("多看少动", "104天样本，20日均基本持平胜38%。方向不明确，科创50在震荡+宽度中性时表现偏弱。"),
        "deteriorating": ("偏谨慎", "207天样本，20日均+2.1%胜41%。震荡+恶化但科创50仍有正收益——高Beta特性使得反弹来得快。"),
    },
    "偏空震荡": {
        "strong": ("偏积极", "84天样本，20日均+2.3%胜54%。科创50偏空+宽度强时反弹概率较高——科技股率先企稳是常见模式。"),
        "neutral": ("卖压减缓", "75天样本，20日均+1.1%胜64%。卖压消退时科创50有较好的反弹预期。"),
        "deteriorating": ("偏积极", "135天样本，20日均+2.6%胜64%。科创50偏空+恶化时表现反而不错——可能因为利空出尽后弹性释放。"),
    },
    "空头市场": {
        "strong": ("底部区域", "57天样本，20日均+1.6%胜53%。更多数据后回归均值——空头+宽度强反弹幅度不如之前极端，但仍偏积极。"),
        "neutral": ("最佳反弹窗口", "141天样本，20日均+14.8%胜68%。科创50空头尾声+宽度企稳的反弹弹性远超其他指数——样本扩大后仍是最强信号。"),
        "deteriorating": ("分歧较大", "171天样本，20日均+1.8%胜40%。收益正但胜率不过半——空头+恶化时科创50行为不稳定，谨慎对待。"),
    },
}

# 按指数名索引框架
_FRAMEWORK_BY_INDEX = {
    "恒生指数": _HSI_FRAMEWORK,
    "恒生科技": _HSTECH_FRAMEWORK,
    "沪深300": _CSI300_FRAMEWORK,
    "A500": _A500_FRAMEWORK,
    "科创50": _KC50_FRAMEWORK,
}


def get_framework(index_name: str | None) -> dict:
    """返回指定指数的解读框架。无数据时返回默认框架。"""
    if index_name and index_name in _FRAMEWORK_BY_INDEX:
        return _FRAMEWORK_BY_INDEX[index_name]
    return _DEFAULT_FRAMEWORK


# 兼容旧引用：默认框架
FRAMEWORK = _DEFAULT_FRAMEWORK

STATE_ORDER = ["多头市场", "偏多震荡", "震荡市场", "偏空震荡", "空头市场"]
COL_ORDER = ["strong", "neutral", "deteriorating"]
COL_NAMES = {"strong": "宽度偏强", "neutral": "宽度中性", "deteriorating": "宽度恶化"}


def _classify_breadth_col(breadth_label: str) -> str:
    if "恶化" in breadth_label or "恐慌" in breadth_label:
        return "deteriorating"
    if "修复" in breadth_label or "强势" in breadth_label or "过热" in breadth_label or "强" in breadth_label:
        return "strong"
    return "neutral"


def market_summary(market_state: dict, breadth_result: dict | None, index_name: str | None = None) -> dict:
    """返回当前状态 × 宽度在解读框架中的位置，以及完整框架供 UI 渲染。"""
    state = market_state.get("state_label", "—")
    base_state = state.split("（")[0] if "（" in state else state

    if breadth_result is None or "error" in breadth_result:
        if "多头" in base_state:
            label, note = "趋势偏多", "宽度数据暂缺，继续积累。"
        elif "空头" in base_state:
            label, note = "趋势偏空", "宽度数据暂缺，继续积累。"
        else:
            label, note = "数据积累中", "宽度数据暂缺，继续积累。"
        return {
            "label": label, "note": note,
            "state": base_state, "breadth_col": None,
            "has_data": False,
        }

    judgment = breadth_result.get("judgment", {})
    breadth_label = judgment.get("label", "—")
    breadth_col = _classify_breadth_col(breadth_label)

    fw = get_framework(index_name)
    default_fw = _DEFAULT_FRAMEWORK
    cell = fw.get(base_state, default_fw["震荡市场"]).get(breadth_col)
    if cell is None:
        cell = default_fw["震荡市场"]["neutral"]

    return {
        "label": cell[0],
        "note": cell[1],
        "state": base_state,
        "breadth_col": breadth_col,
        "breadth_label": breadth_label,
        "has_data": True,
    }


def classify_trend(current: float | None, previous: float | None) -> str:
    """多级变化分类：明显改善/小幅改善/基本稳定/小幅恶化/明显恶化。"""
    if current is None or previous is None:
        return "数据不足"
    diff = current - previous  # 百分点变化
    if diff > config.BREADTH_CHANGE_STRONG_IMPROVE:
        return "明显改善"
    elif diff > config.BREADTH_CHANGE_MODERATE_IMPROVE:
        return "小幅改善"
    elif diff < config.BREADTH_CHANGE_STRONG_WORSEN:
        return "明显恶化"
    elif diff < config.BREADTH_CHANGE_MODERATE_WORSEN:
        return "小幅恶化"
    else:
        return "基本稳定"


def breadth_judgment(ma21_pct: float | None, ma21_change_5d: float | None) -> dict:
    """综合 MA21 宽度水平和变化方向，给出一个判断结论。"""
    if ma21_pct is None:
        return {"label": "数据积累中", "class": "neutral",
                "one_liner": "历史数据不足以计算 MA21 宽度，每日自动扩充。"}

    # 偏热 >70%
    if ma21_pct > config.BREADTH_HOT * 100:
        if ma21_change_5d is not None and ma21_change_5d > 3:
            return {"label": "宽度过热", "class": "hot",
                    "one_liner": f"超 {config.BREADTH_HOT*100:.0f}% 个股站上 MA21 且仍在扩散，短期情绪亢奋，追涨风险加大。"}
        return {"label": "强势宽度", "class": "warm",
                "one_liner": f"多数个股处于中期均线上方，市场宽度健康，强势环境可维持。"}

    # 偏冷 <30%
    if ma21_pct < config.BREADTH_COLD * 100:
        if ma21_change_5d is not None and ma21_change_5d < -3:
            return {"label": "宽度恐慌", "class": "cold",
                    "one_liner": f"不足 {config.BREADTH_COLD*100:.0f}% 个股站上 MA21 且仍在恶化，普跌加速，不宜抄底。"}
        return {"label": "宽度低迷", "class": "cool",
                "one_liner": f"少数个股维持中期均线，市场宽度偏弱但跌势放缓，关注是否企稳。"}

    # 正常区间 30%-70%，看变化方向
    if ma21_change_5d is not None and ma21_change_5d < config.BREADTH_CHANGE_STRONG_WORSEN:
        return {"label": "宽度恶化", "class": "worsening",
                "one_liner": f"MA21 宽度近 5 日快速收窄（{ma21_change_5d:+.0f}pp），多数个股正在回调，不宜急于进场。"}
    if ma21_change_5d is not None and ma21_change_5d > config.BREADTH_CHANGE_STRONG_IMPROVE:
        return {"label": "宽度修复", "class": "improving",
                "one_liner": f"MA21 宽度近 5 日快速扩大（{ma21_change_5d:+.0f}pp），反弹参与面广，修复有持续性。"}
    if ma21_change_5d is not None and ma21_change_5d < config.BREADTH_CHANGE_MODERATE_WORSEN:
        return {"label": "宽度偏弱", "class": "weakening",
                "one_liner": f"MA21 宽度小幅收窄，短期偏谨慎，但尚未形成普遍回调。"}
    if ma21_change_5d is not None and ma21_change_5d > config.BREADTH_CHANGE_MODERATE_IMPROVE:
        return {"label": "宽度偏强", "class": "strengthening",
                "one_liner": f"MA21 宽度小幅扩大，短期偏积极，个股逐步修复。"}
    return {"label": "宽度中性", "class": "neutral",
            "one_liner": "MA21 宽度稳定在正常区间，个股分化，无明显宽度信号。"}


def _serial_fill_gaps(symbols: list[str], index_code: str) -> None:
    """并行批量拉取后补刀：串行拉取仍缺失的股票，间隔 1.5s 防反爬。"""
    import time as _time
    hist = load_price_history(index_code)
    # 每次最多补 100 只（每只~1.5s，约 2.5 分钟），剩余下次加载继续补
    missing = [s for s in symbols if s not in hist.columns or hist[s].dropna().shape[0] < 21]
    missing = missing[:100]
    if not missing:
        return
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    import akshare as ak
    new_data: dict[str, dict[str, float]] = {}
    for sym in missing:
        market_sym = f"sh{sym}" if sym.startswith(("5", "6")) else f"sz{sym}"
        try:
            df = ak.stock_zh_a_hist_tx(symbol=market_sym, start_date=start, end_date=end)
            if df is not None and not df.empty and "close" in df.columns:
                for _, row in df.iterrows():
                    d = row["date"]
                    date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                    try:
                        new_data.setdefault(date_str, {})[sym] = float(row["close"])
                    except (ValueError, TypeError):
                        continue
        except Exception:
            pass
        _time.sleep(1.5)
    if new_data:
        backfill = pd.DataFrame(new_data).T
        backfill.index = pd.to_datetime(backfill.index)
        combined = backfill if hist.empty else backfill.combine_first(hist)
        combined.to_csv(_price_history_path(index_code))


# ══════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════

def load_breadth(symbol: str, force_refresh: bool = False) -> dict | None:
    index_info = BREADTH_INDEX_MAP.get(symbol)
    if index_info is None:
        return None

    index_code = index_info["index_code"]
    use_sina = index_info.get("use_sina", False)
    is_hk = index_info.get("hk", False)
    hk_source = index_info.get("hk_source")
    hk_page = index_info.get("hk_page")
    today_str = date.today().isoformat()

    # 1. 获取成分股列表
    try:
        constituents = fetch_constituents(
            index_code, use_sina, force_refresh,
            hk=is_hk, hk_source=hk_source, hk_page=hk_page,
        )
    except Exception:
        return None
    if constituents.empty:
        return None
    symbols = constituents["symbol"].tolist()

    # 2. 尝试获取今日快照
    hist = load_price_history(index_code)
    hist_dates = set(hist.index.strftime("%Y-%m-%d")) if not hist.empty else set()
    already_warm = use_sina or (not hist.empty and len(hist.columns) >= (30 if is_hk else 100))
    if today_str not in hist_dates and already_warm:
        today_prices = _fetch_today_snapshot(index_code, use_sina, symbols, is_hk=is_hk)
        if today_prices:
            update_price_history(index_code, today_prices)
            hist = load_price_history(index_code)

    actual_total = len(symbols)

    if is_hk:
        # HK：从 ak.stock_hk_daily 批量拉取历史
        stocks_with_enough = 0
        stocks_any_data = 0
        if not hist.empty:
            stocks_with_enough = sum(1 for c in hist.columns if hist[c].dropna().shape[0] >= 21)
            stocks_any_data = len(hist.columns)
        need_bulk = (stocks_any_data < actual_total * 0.95 or
                     stocks_with_enough < actual_total * 0.95)
        if need_bulk:
            _bulk_fetch_hk_stocks(symbols, index_code)
            hist = load_price_history(index_code)
    else:
        # A 股：从主缓存 + 腾讯源补充历史
        hist_dates = set(hist.index.strftime("%Y-%m-%d")) if not hist.empty else set()
        if today_str not in hist_dates or len(hist) < 21:
            _backfill_from_main_cache(symbols, index_code)
            hist = load_price_history(index_code)

        stocks_with_enough = 0
        stocks_any_data = 0
        if not hist.empty:
            stocks_with_enough = sum(1 for c in hist.columns if hist[c].dropna().shape[0] >= 21)
            stocks_any_data = len(hist.columns)
        need_bulk = (stocks_any_data < actual_total * 0.95 or
                     stocks_with_enough < actual_total * 0.95)
        if need_bulk:
            _bulk_fetch_stocks(symbols, index_code)
            hist = load_price_history(index_code)
            if not use_sina:
                _serial_fill_gaps(symbols, index_code)
                hist = load_price_history(index_code)

    # 4. 计算宽度
    breadth = compute_breadth_from_history(hist, actual_total)

    total = breadth["total_stocks"]
    sma8 = breadth["stocks_with_ma8"]
    sma21 = breadth["stocks_with_ma21"]
    sprice = breadth["stocks_with_price"]
    coverage_ratio = sma21 / total if total > 0 else 0

    if sprice < max(10, total * 0.1):
        return {
            "applicable": True,
            "error": "insufficient_data",
            "breadth": breadth,
            "index_name": index_info["name"],
            "coverage_ratio": round(coverage_ratio, 3),
            "survivorship_bias_note": "历史宽度使用当前成分股名单回算，可能存在幸存者偏差。",
        }

    current_ma8 = breadth["pct_above_ma8"]
    current_ma21 = breadth["pct_above_ma21"]
    prev_ma8 = None
    prev_ma21 = None
    ma8_change_5d = None
    ma21_change_5d = None
    if len(hist) >= 8:
        prev_hist = hist.iloc[: -5] if len(hist) >= 8 else hist
        prev_b = compute_breadth_from_history(prev_hist, actual_total)
        prev_ma8 = prev_b.get("pct_above_ma8")
        prev_ma21 = prev_b.get("pct_above_ma21")
        if current_ma8 is not None and prev_ma8 is not None:
            ma8_change_5d = round(current_ma8 - prev_ma8, 1)
        if current_ma21 is not None and prev_ma21 is not None:
            ma21_change_5d = round(current_ma21 - prev_ma21, 1)

    ma21_state = classify_breadth(current_ma21)
    ma8_state = classify_breadth(current_ma8)
    direction = classify_trend(current_ma21, prev_ma21)

    is_sampled = coverage_ratio < 0.8 and sma21 < total * 0.8
    coverage_warning = coverage_ratio < config.COVERAGE_MIN

    above_ma8_ratio = round(current_ma8 / 100, 3) if current_ma8 is not None else 0
    above_ma21_ratio = round(current_ma21 / 100, 3) if current_ma21 is not None else 0

    ma8_display = f"{current_ma8:.1f}%" if current_ma8 is not None else "—"
    ma21_display = f"{current_ma21:.1f}%" if current_ma21 is not None else "—"

    explanation_parts = []
    if current_ma21 is not None:
        if ma21_state == "偏热":
            explanation_parts.append(f"超{config.BREADTH_HOT*100:.0f}%成分股站上21日均线，短期整体偏热。偏热不代表马上下跌，强多头环境中宽度可能长期偏热")
        elif ma21_state == "偏冷":
            explanation_parts.append(f"不足{config.BREADTH_COLD*100:.0f}%成分股站上21日均线，短期整体偏弱。偏冷不代表马上反弹，空头环境中宽度可能长期偏冷")
        else:
            explanation_parts.append(f"约{ma21_display}成分股站上21日均线，处于正常范围")
    else:
        remaining = max(1, 21 - breadth.get('history_days', 0))
        explanation_parts.append(f"MA21数据积累中（{sma21}/{total}只有足够历史），预计{remaining}个交易日后可用")

    if ma21_change_5d is not None:
        if direction == "明显恶化":
            explanation_parts.append(f"MA21宽度近5日下降{abs(ma21_change_5d):.0f}个百分点，多数成分股近期正在回调")
        elif direction == "明显改善":
            explanation_parts.append(f"MA21宽度近5日上升{ma21_change_5d:.0f}个百分点，参与反弹的成分股明显增多")
        elif direction == "小幅改善":
            explanation_parts.append("MA21宽度近5日小幅改善")
        elif direction == "小幅恶化":
            explanation_parts.append("MA21宽度近5日小幅收窄")
        else:
            explanation_parts.append("MA21宽度近5日基本稳定")

    notes = []
    if is_sampled and sma21 > 0:
        notes.append(f"当前为采样宽度（{sma21}/{total}只成分股有足够数据），每日自动扩充")
    if coverage_warning:
        notes.append(f"成分股数据覆盖率{coverage_ratio:.1%}低于{config.COVERAGE_MIN:.0%}，宽度结论仅供参考")
    if notes:
        explanation_parts.append("。".join(notes))

    judgment = breadth_judgment(current_ma21, ma21_change_5d)

    return {
        "applicable": True,
        "judgment": judgment,
        "above_ma8_ratio": above_ma8_ratio,
        "above_ma21_ratio": above_ma21_ratio,
        "ma8_state": ma8_state,
        "ma21_state": ma21_state,
        "ma8_change_5d": ma8_change_5d,
        "ma21_change_5d": ma21_change_5d,
        "direction": direction,
        "coverage_ratio": round(coverage_ratio, 3),
        "survivorship_bias_note": "历史宽度使用当前成分股名单回算，可能存在幸存者偏差。",
        "pct_above_ma8": current_ma8,
        "pct_above_ma21": current_ma21,
        "ma8_display": ma8_display,
        "ma21_display": ma21_display,
        "state": ma21_state,
        "trend": direction,
        "total_stocks": total,
        "stocks_with_ma8": sma8,
        "stocks_with_ma21": sma21,
        "stocks_with_price": sprice,
        "history_days": breadth.get("history_days", 0),
        "coverage": round(coverage_ratio, 2),
        "is_sampled": is_sampled,
        "index_name": index_info["name"],
        "explanation": "".join(explanation_parts),
    }
