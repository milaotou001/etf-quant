"""所有标的 MA60 趋势过滤效果回测"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators, RSI_THRESHOLDS

SYMBOLS = [
    ("563360", "A500"),
    ("510300", "沪深300"),
    ("518880", "黄金"),
    ("588000", "科创50"),
    ("159920", "恒生ETF"),
    ("513180", "恒生科技"),
    ("01810", "小米"),
    ("00700", "腾讯"),
]

for sym, name in SYMBOLS:
    rsi_buy = RSI_THRESHOLDS.get(sym, 35)
    try:
        df = compute_indicators(load_data(sym))
    except Exception as e:
        print(f"=== {name} ({sym}) === 数据加载失败: {e}")
        print()
        continue

    c = df['close']
    r = df['rsi']

    results = {'above': [], 'below': [], 'no_ma60': []}
    triggered = False

    for i in range(14, len(df)):  # skip warmup
        if r.iloc[i] < rsi_buy and not triggered:
            triggered = True
            if 'ma60' not in df.columns or pd.isna(df['ma60'].iloc[i]):
                key = 'no_ma60'
            elif c.iloc[i] > df['ma60'].iloc[i]:
                key = 'above'
            else:
                key = 'below'
            if i + 60 < len(df):
                ret60 = (c.iloc[i+60] / c.iloc[i] - 1) * 100
                ret20 = (c.iloc[i+20] / c.iloc[i] - 1) * 100
                results[key].append(ret60)
        elif r.iloc[i] >= max(rsi_buy + 15, 50):
            triggered = False

    print(f"=== {name} ({sym})  RSI<{rsi_buy} 阈值 ===")
    print(f"数据: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")

    for key, label in [('above', 'MA60上方'), ('below', 'MA60下方'), ('no_ma60', '无MA60')]:
        trades = results[key]
        if trades:
            wins = sum(1 for r_ in trades if r_ > 0)
            print(f"  {label}: {len(trades)}次 | 60日均{np.mean(trades):+.1f}% | 胜率{wins}/{len(trades)}({wins/len(trades)*100:.0f}%) | 最好{max(trades):+.1f}% 最差{min(trades):+.1f}%")
        elif key == 'no_ma60':
            pass  # don't print if 0 and it's the no_ma60 category
        else:
            print(f"  {label}: 0次")

    total = len(results['above']) + len(results['below'])
    if total > 0:
        above_pct = len(results['above']) / total * 100
        print(f"  → MA60上方信号占比: {above_pct:.0f}% ({len(results['above'])}/{total})")
    elif len(results['above']) == 0:
        print(f"  → ⚠ 无信号或全部在MA60下方 — MA60过滤在此标的不适用")
    print()
