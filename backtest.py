"""RSI<30买入后不同止盈策略回测"""
import pandas as pd
import pandas_ta as ta
import numpy as np


def sim_rsi_target(df, buy_idx, target):
    """RSI达到目标值卖出"""
    entry = df.iloc[buy_idx]['close']
    for i in range(buy_idx + 1, len(df)):
        if df.iloc[i]['rsi'] >= target:
            return (df.iloc[i]['close'] / entry - 1) * 100, (df.index[i] - df.index[buy_idx]).days
    return (df.iloc[-1]['close'] / entry - 1) * 100, (df.index[-1] - df.index[buy_idx]).days


def sim_trailing(df, buy_idx, trail_pct):
    """移动止盈：从买入后最高点回落 trail_pct% 卖出"""
    entry = df.iloc[buy_idx]['close']
    peak = entry
    for i in range(buy_idx + 1, len(df)):
        price = df.iloc[i]['close']
        peak = max(peak, price)
        if price <= peak * (1 - trail_pct / 100):
            return (price / entry - 1) * 100, (df.index[i] - df.index[buy_idx]).days
    return (df.iloc[-1]['close'] / entry - 1) * 100, (df.index[-1] - df.index[buy_idx]).days


def sim_fixed_days(df, buy_idx, days):
    """固定天数后卖出"""
    entry = df.iloc[buy_idx]['close']
    sell_idx = min(buy_idx + days, len(df) - 1)
    return (df.iloc[sell_idx]['close'] / entry - 1) * 100, (df.index[sell_idx] - df.index[buy_idx]).days


def sim_ma_cross(df, buy_idx, ma_len):
    """收盘价跌破MA卖出"""
    entry = df.iloc[buy_idx]['close']
    ma_col = f'ma_{ma_len}'
    if ma_col not in df.columns:
        df[ma_col] = ta.sma(df['close'], length=ma_len)
    for i in range(buy_idx + 1, len(df)):
        if df.iloc[i]['close'] < df[ma_col].iloc[i]:
            return (df.iloc[i]['close'] / entry - 1) * 100, (df.index[i] - df.index[buy_idx]).days
    return (df.iloc[-1]['close'] / entry - 1) * 100, (df.index[-1] - df.index[buy_idx]).days


def run_backtest(df, buy_condition='rsi30'):
    """运行全部止盈策略回测，返回 (DataFrame, 条件标签, 信号次数)"""
    df = df.copy()
    if 'rsi' not in df.columns:
        df['rsi'] = ta.rsi(df['close'], length=14)

    if buy_condition == 'rsi35':
        buy_dates = df.index[df['rsi'] < 35]
        cond_label = 'RSI<35'
    elif buy_condition == 'rsi30':
        buy_dates = df.index[df['rsi'] < 30]
        cond_label = 'RSI<30'
    elif buy_condition == 'rsi25':
        buy_dates = df.index[df['rsi'] < 25]
        cond_label = 'RSI<25'
    else:
        raise ValueError(f"Unknown buy condition: {buy_condition}")

    strategies = {
        '买到持有(不卖)': lambda df, idx: ((df.iloc[-1]['close'] / df.iloc[idx]['close'] - 1) * 100, (df.index[-1] - df.index[idx]).days),
        'RSI70就卖': lambda df, idx: sim_rsi_target(df, idx, 70),
        'RSI60就卖': lambda df, idx: sim_rsi_target(df, idx, 60),
        '回落5%卖': lambda df, idx: sim_trailing(df, idx, 5),
        '回落8%卖': lambda df, idx: sim_trailing(df, idx, 8),
        '回落10%卖': lambda df, idx: sim_trailing(df, idx, 10),
        '20天就卖': lambda df, idx: sim_fixed_days(df, idx, 20),
        '40天就卖': lambda df, idx: sim_fixed_days(df, idx, 40),
        '60天就卖': lambda df, idx: sim_fixed_days(df, idx, 60),
        '跌破MA20卖': lambda df, idx: sim_ma_cross(df, idx, 20),
    }

    results = []
    for name, fn in strategies.items():
        trades = []
        for bd in buy_dates:
            if bd >= df.index[-1]:
                continue
            idx = df.index.get_loc(bd)
            ret, dur = fn(df, idx)
            trades.append({'ret': ret, 'dur': dur})

        rets = [t['ret'] for t in trades]
        durs = [t['dur'] for t in trades]
        wins = sum(1 for r in rets if r > 0)

        results.append({
            '策略': name,
            '信号次数': len(rets),
            '胜率': f"{wins/len(rets)*100:.0f}%",
            '平均收益': f"{np.mean(rets):+.2f}%",
            '中位收益': f"{np.median(rets):+.2f}%",
            '最差': f"{np.min(rets):+.2f}%",
            '最好': f"{np.max(rets):+.2f}%",
            '平均持有天': f"{np.mean(durs):.0f}天",
        })

    rdf = pd.DataFrame(results)
    rdf = rdf.sort_values('平均收益', key=lambda x: x.str.replace('%', '').str.replace('+', '').astype(float), ascending=False)
    return rdf, cond_label, len(buy_dates)
