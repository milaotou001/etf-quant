"""复盘关键错误时刻 -- 用缓存+备用源"""
import sys; sys.path.insert(0, '.')
import os, io, pandas as pd, numpy as np, time, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dashboard import compute_indicators, build_market_analysis, _reminders, _personalized_warnings, get_rsi_threshold

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')

# 关键错误时刻 — 基于真实 trades.csv 数据
mistakes = [
    # 黄金：最贵 10.921 (2/27)，最大仓 9.170 (3/23)
    ("黄金ETF",     "518880",  "2026-02-27", 10.921, 1000,  10921, False),
    ("黄金ETF",     "518880",  "2026-03-23", 9.170,  4600,  42182, False),
    # 洛阳钼业：最高买价 24.84
    ("洛阳钼业",    "603993",  "2026-01-30", 24.84,  300,    7452, True),
    # 恒生科技：两笔重仓
    ("恒生科技ETF", "513180",  "2026-01-06", 0.771,  16600, 12799, False),
    ("恒生科技ETF", "513180",  "2026-01-13", 0.780,  14300, 11154, False),
    # 恒生ETF：高位加仓
    ("恒生ETF",     "159920",  "2025-07-21", 1.533,  4000,   6132, False),
    ("恒生ETF",     "159920",  "2026-01-06", 1.613,  5000,   8065, False),
]


def load_cached(symbol):
    """读取本地缓存CSV"""
    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, parse_dates=['date'], index_col='date')
        df = df.sort_index()
        return df
    return None


def fetch_sina_etf(symbol):
    """新浪ETF数据源"""
    import akshare as ak
    try:
        market = f"sh{symbol}" if symbol.startswith(("5", "6")) else f"sz{symbol}"
        df = ak.fund_etf_hist_sina(symbol=market)
        df["date"] = pd.to_datetime(df["date"]); df.set_index("date", inplace=True); df = df.sort_index()
        df["volume"] = df["volume"] / 100
        # 新浪返回: open, high, low, close, volume, amount
        return df[["open","high","low","close","volume","amount"]]
    except Exception as e:
        return None


def fetch_stock(symbol):
    """股票数据"""
    import akshare as ak
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                start_date="20240101", end_date="20260704", adjust="qfq")
        df.rename(columns={"日期":"date","开盘":"open","最高":"high","最低":"low",
                          "收盘":"close","成交量":"volume","成交额":"amount"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"]); df.set_index("date", inplace=True); df = df.sort_index()
        return df[["open","high","low","close","volume","amount"]]
    except Exception as e:
        return None


def run():
    results = []
    for name, symbol, date, price, shares, amount, is_stock in mistakes:
        print(f"\n{'='*60}")
        print(f"  {name} ({symbol}) -- {date}")
        print(f"  BUY {shares} shares @ {price:.3f}  = {amount:.0f} yuan")
        print(f"{'='*60}")

        end_dt = pd.Timestamp(date)

        # 尝试多种数据源
        df = None
        source = ""

        # 1. 本地缓存
        cached = load_cached(symbol)
        if cached is not None and not cached.empty:
            df = cached[cached.index <= end_dt].copy()
            if len(df) >= 60:
                source = "cache"
                print(f"  [using cache, {len(df)} rows]")

        # 2. 新浪ETF
        if df is None or len(df) < 60:
            if not is_stock:
                df = fetch_sina_etf(symbol)
                if df is not None:
                    df = df[df.index <= end_dt]
                    if len(df) >= 60:
                        source = "sina"
                        print(f"  [using sina, {len(df)} rows]")

        # 3. 股票API
        if df is None or len(df) < 60:
            if is_stock:
                time.sleep(random.uniform(0.5, 1.0))
                df = fetch_stock(symbol)
                if df is not None:
                    df = df[df.index <= end_dt]
                    if len(df) >= 60:
                        source = "stock_api"
                        print(f"  [using stock API, {len(df)} rows]")

        if df is None or len(df) < 60:
            print(f"  SKIP: insufficient data ({len(df) if df is not None else 0} rows)")
            continue

        # 确保有amount列
        if "amount" not in df.columns:
            df["amount"] = np.nan

        try:
            df = compute_indicators(df)
        except Exception as e:
            print(f"  indicator error: {e}")
            continue

        latest = df.iloc[-1]
        rsi_buy = get_rsi_threshold(symbol)

        rsi_val = latest.get("rsi", np.nan)
        ma20 = latest.get("ma20", np.nan)
        ma60 = latest.get("ma60", np.nan)
        close = latest["close"]
        chg = latest.get("chg", np.nan)
        rvol = latest.get("rvol", np.nan)

        hist_c = [c for c in df.columns if c.startswith("MACDh_")]
        dif_c = [c for c in df.columns if c.startswith("MACD_") and not c.startswith("MACDs_") and not c.startswith("MACDh_")]
        dea_c = [c for c in df.columns if c.startswith("MACDs_")]
        hist_v = latest[hist_c[0]] if hist_c else np.nan
        dif_v = latest[dif_c[0]] if dif_c else np.nan
        dea_v = latest[dea_c[0]] if dea_c else np.nan

        lookback = min(90, len(df))
        rc = df["close"].iloc[-lookback:]
        ph, pl = rc.max(), rc.min()
        pct_rank = (close - pl) / (ph - pl) * 100 if ph > pl else 50

        bb_u = [c for c in df.columns if c.startswith("BBU_")]
        bb_l = [c for c in df.columns if c.startswith("BBL_")]
        bb_upper = latest[bb_u[0]] if bb_u else np.nan
        bb_lower = latest[bb_l[0]] if bb_l else np.nan
        dist_ma20 = (close / ma20 - 1) * 100 if not pd.isna(ma20) else np.nan

        # ---- INDICATORS ----
        print(f"\n  [Indicators on {date}] (source: {source})")
        print(f"  Close:      {close:.3f}")
        print(f"  MA20:       {ma20:.3f}     (dist: {dist_ma20:+.1f}%)")
        print(f"  MA60:       {ma60:.3f}" if not pd.isna(ma60) else "  MA60:       N/A")
        print(f"  RSI(14):    {rsi_val:.0f}")
        print(f"  MACD DIF:   {dif_v:+.4f}  DEA: {dea_v:+.4f}  HIST: {hist_v:+.4f}  {'[RED]' if hist_v>0 else '[GREEN]'}")
        print(f"  RVOL:       {rvol:.2f}" if not pd.isna(rvol) else "  RVOL:       N/A")
        print(f"  BB Upper:   {bb_upper:.3f}" if not pd.isna(bb_upper) else "  BB Upper:   N/A")
        print(f"  90d %rank:  {pct_rank:.0f}%  (90d high {ph:.3f} / low {pl:.3f})")

        # ---- DASHBOARD OUTPUT ----
        try:
            analysis = build_market_analysis(df)
            state = analysis.get("state_label", "N/A")
        except:
            state = "N/A"

        reminders = _reminders(latest, df, rsi_buy_threshold=rsi_buy)
        personalized = _personalized_warnings(latest, df)

        print(f"\n  [Dashboard State]")
        print(f"  State: {state}")

        if reminders:
            print(f"  Reminders ({len(reminders)}):")
            for r in reminders:
                print(f"    - {r}")
        else:
            print(f"  Reminders: (none)")

        if personalized:
            print(f"  >>> PERSONALIZED WARNINGS ({len(personalized)}):")
            for w in personalized:
                print(f"    - {w}")
        elif pct_rank >= 65:
            print(f"  >>> Price at {pct_rank:.0f}%ile but no personalized warning -- CHECK LOGIC")

        # ---- AFTERMATH ----
        print(f"\n  [Aftermath -- what happened after buying at {price}]")
        # 从缓存读取完整数据看后续
        full_df = load_cached(symbol) if not is_stock else fetch_stock(symbol)
        if full_df is not None and not full_df.empty:
            fc = full_df[full_df.index > end_dt]
            if "close" in fc.columns and not fc.empty:
                fc_series = fc["close"]
                for days in [30, 60, 90]:
                    tgt = end_dt + pd.Timedelta(days=days)
                    c2 = fc_series[fc_series.index <= tgt]
                    if not c2.empty:
                        fp = c2.iloc[-1]
                        ret = (fp/price-1)*100
                        print(f"  {days}d later ({c2.index[-1].strftime('%Y-%m-%d')}): {fp:.3f} ({ret:+.1f}%)")
                lo = fc_series.min()
                lo_d = fc_series.idxmin()
                lo_r = (lo/price-1)*100
                print(f"  Low ({lo_d.strftime('%Y-%m-%d')}): {lo:.3f} ({lo_r:+.1f}%)")
            else:
                print(f"  (no future data)")
        else:
            print(f"  (could not get future data)")

        results.append({
            "name": name, "date": date, "price": price, "amount": amount,
            "rsi": rsi_val, "pct_rank": pct_rank, "hist": hist_v,
            "rvol": rvol, "state": state, "dist_ma20": dist_ma20,
            "n_personalized": len(personalized), "n_reminders": len(reminders),
            "hist_color": "RED" if hist_v > 0 else "GREEN",
            "ma20_position": "ABOVE" if close > ma20 else "BELOW",
        })

    # Summary
    print(f"\n\n{'='*60}")
    print(f"  SUMMARY: Would the tool have warned you?")
    print(f"{'='*60}")
    print(f"  {'Name':<14} {'Date':<12} {'Price':>7} {'RSI':>4} {'%ile':>5} {'HIST':>8} {'vMA20':>6} {'State':<18} {'Warn':>4}")
    print(f"  {'-'*85}")
    for r in results:
        hist_str = f"{r['hist']:+.4f}" if not pd.isna(r['hist']) else "N/A"
        state_str = r['state'][:18] if r['state'] else "N/A"
        print(f"  {r['name']:<14} {r['date']:<12} {r['price']:>7.3f} {r['rsi']:>4.0f} {r['pct_rank']:>4.0f}% {hist_str:>8} {r['ma20_position']:>6} {state_str:<18} {r['n_personalized']:>4}")

    print(f"\n  === CONCLUSION ===")
    high_pct = [r for r in results if r['pct_rank'] >= 80]
    mid_pct = [r for r in results if 65 <= r['pct_rank'] < 80]
    if high_pct:
        print(f"  {len(high_pct)}/{len(results)} trades at 80%+ percentile -- max PERSONALIZED warning would fire.")
        for r in high_pct:
            print(f"    {r['name']} {r['date']}: {r['pct_rank']:.0f}%ile, RSI={r['rsi']:.0f}, state='{r['state']}'")
    if mid_pct:
        print(f"  {len(mid_pct)}/{len(results)} trades at 65-80% percentile -- elevated warning would fire.")
        for r in mid_pct:
            print(f"    {r['name']} {r['date']}: {r['pct_rank']:.0f}%ile, RSI={r['rsi']:.0f}, state='{r['state']}'")


if __name__ == "__main__":
    run()
