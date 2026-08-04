"""错题本警告系统的全历史回测
回答：警告触发后，后续收益是否系统性地更差？
"""
import sys; sys.path.insert(0, '.')
import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np, os
from dashboard import compute_indicators, _personalized_warnings

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
SINA_AVAILABLE = False  # Set True if sina data available

def get_data(symbol, use_sina=False):
    """Get data for a symbol"""
    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, parse_dates=['date'], index_col='date').sort_index()
        return df

    if use_sina and not symbol.startswith('6'):
        try:
            import akshare as ak
            market = f"sh{symbol}" if symbol.startswith(("5","6")) else f"sz{symbol}"
            df = ak.fund_etf_hist_sina(symbol=market)
            df["date"] = pd.to_datetime(df["date"]); df.set_index("date", inplace=True); df.sort_index(inplace=True)
            df["volume"] = df["volume"] / 100
            return df[["open","high","low","close","volume","amount"]]
        except: pass
    return None


def backtest(symbol, name, min_days=120):
    """Walk through history, record warnings and forward returns"""
    df = get_data(symbol)
    if df is None or len(df) < min_days:
        print(f"  {name} ({symbol}): SKIP (no data)")
        return None

    results = []
    for i in range(min_days, len(df) - 1):
        # Data up to day i (simulating "today")
        today_df = df.iloc[:i+1].copy()
        try:
            today_df = compute_indicators(today_df)
        except:
            continue

        today = today_df.iloc[-1]
        close = today["close"]
        warnings = _personalized_warnings(today, today_df)
        n_warn = len(warnings)

        # Forward returns
        future = df.iloc[i+1:]  # days after "today"
        if len(future) < 20:
            continue

        fwd_close = future["close"]
        ret_5d = (fwd_close.iloc[min(4, len(fwd_close)-1)] / close - 1) * 100
        ret_10d = (fwd_close.iloc[min(9, len(fwd_close)-1)] / close - 1) * 100
        ret_20d = (fwd_close.iloc[min(19, len(fwd_close)-1)] / close - 1) * 100

        # If enough future data for 60d
        ret_60d = np.nan
        if len(fwd_close) >= 60:
            ret_60d = (fwd_close.iloc[59] / close - 1) * 100

        # Max drawdown in next 60 days
        if len(fwd_close) >= 20:
            fwd60 = fwd_close.iloc[:min(60, len(fwd_close))]
            max_dd = (fwd60.min() / close - 1) * 100
        else:
            max_dd = np.nan

        # Also capture what indicators look like
        rsi = today.get("rsi", np.nan)
        ath = today_df["close"].max()
        ath_r = close / ath if ath > 0 else 0

        lookback = min(90, len(today_df))
        rc = today_df["close"].iloc[-lookback:]
        ph, pl = rc.max(), rc.min()
        pct_rank = (close - pl) / (ph - pl) * 100 if ph > pl else 50

        hist_c = [c for c in today_df.columns if c.startswith("MACDh_")]
        hist_v = today[hist_c[0]] if hist_c else np.nan

        results.append({
            "date": today_df.index[-1],
            "close": close, "n_warn": n_warn,
            "rsi": rsi, "ath_r": ath_r, "pct_rank": pct_rank,
            "hist": hist_v,
            "ret_5d": ret_5d, "ret_10d": ret_10d,
            "ret_20d": ret_20d, "ret_60d": ret_60d,
            "max_dd_60d": max_dd,
        })

    res_df = pd.DataFrame(results)
    res_df.set_index("date", inplace=True)

    # Analysis
    warn_days = res_df[res_df["n_warn"] > 0]
    nowarn_days = res_df[res_df["n_warn"] == 0]

    print(f"\n{'='*60}")
    print(f"  {name} ({symbol}) 全历史回测")
    print(f"{'='*60}")
    print(f"  总交易日: {len(res_df)}")
    print(f"  警告天数: {len(warn_days)} ({len(warn_days)/len(res_df)*100:.1f}%)")
    print(f"  无警告天数: {len(nowarn_days)}")

    # Compare forward returns
    for horizon, col in [("5日", "ret_5d"), ("10日", "ret_10d"), ("20日", "ret_20d"), ("60日", "ret_60d")]:
        w_avg = warn_days[col].mean()
        nw_avg = nowarn_days[col].mean()
        w_med = warn_days[col].median()
        nw_med = nowarn_days[col].median()
        diff = w_avg - nw_avg
        w_win = (warn_days[col] > 0).mean() * 100
        nw_win = (nowarn_days[col] > 0).mean() * 100
        print(f"  {horizon}收益: 警告日{w_avg:+.2f}% vs 无警告{nw_avg:+.2f}% (差{diff:+.2f}%)  |  "
              f"警告日胜率{w_win:.0f}% vs 无警告{nw_win:.0f}%")

    # Max drawdown
    w_dd = warn_days["max_dd_60d"].mean()
    nw_dd = nowarn_days["max_dd_60d"].mean()
    print(f"  60日最大回撤均值: 警告日{w_dd:+.2f}% vs 无警告{nw_dd:+.2f}%")

    # False positive analysis: warning days where 20d return > 0
    fp = warn_days[warn_days["ret_20d"] > 0]
    fn = nowarn_days[nowarn_days["ret_20d"] < -5]  # missed big drops
    print(f"  假阳性(警告后20日涨): {len(fp)}天 ({len(fp)/max(len(warn_days),1)*100:.0f}%)")
    print(f"  假阴性(无警告但20日跌>5%): {len(fn)}天")

    # Show top false negative examples (missed crashes)
    if len(fn) > 0:
        print(f"  假阴性示例 (前5):")
        for idx, row in fn.sort_values("ret_20d").head(5).iterrows():
            print(f"    {idx.strftime('%Y-%m-%d')}  close={row['close']:.3f}  RSI={row['rsi']:.0f}  "
                  f"%ile={row['pct_rank']:.0f}%  ATHr={row['ath_r']:.3f}  20d后={row['ret_20d']:+.1f}%")

    # Show top false positive examples (warning but market went up)
    if len(fp) > 0:
        print(f"  假阳性示例 (前3):")
        for idx, row in fp.sort_values("ret_20d", ascending=False).head(3).iterrows():
            print(f"    {idx.strftime('%Y-%m-%d')}  close={row['close']:.3f}  RSI={row['rsi']:.0f}  "
                  f"%ile={row['pct_rank']:.0f}%  ATHr={row['ath_r']:.3f}  20d后={row['ret_20d']:+.1f}%")

    return res_df


# Run for available ETFs
results = {}
for sym, name in [("518880", "黄金ETF"), ("563360", "A500"), ("510300", "沪深300"), ("588000", "科创50")]:
    res = backtest(sym, name)
    if res is not None:
        results[name] = res

# Summary
print(f"\n\n{'='*60}")
print(f"  总结：错题本警告有预测能力吗？")
print(f"{'='*60}")
for name, res in results.items():
    warn = res[res["n_warn"] > 0]
    nowarn = res[res["n_warn"] == 0]
    w20 = warn["ret_20d"].mean() if len(warn) > 0 else 0
    nw20 = nowarn["ret_20d"].mean() if len(nowarn) > 0 else 0
    diff = w20 - nw20
    fp_rate = (warn["ret_20d"] > 0).mean() * 100 if len(warn) > 0 else 0
    print(f"  {name}: 警告日20日收益 {w20:+.2f}% vs 无警告 {nw20:+.2f}% (差{diff:+.2f}%)  假阳性率{fp_rate:.0f}%")
