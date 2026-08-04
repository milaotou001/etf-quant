"""港股个股 RSI<40 + MA60 过滤"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

for sym, name in [("01810", "小米"), ("00700", "腾讯")]:
    df = compute_indicators(load_data(sym))
    c = df['close']
    r = df['rsi']
    results = {'above': [], 'below': []}
    triggered = False

    for i in range(14, len(df)):
        if r.iloc[i] < 40 and not triggered:
            triggered = True
            if c.iloc[i] > df['ma60'].iloc[i]:
                key = 'above'
            else:
                key = 'below'
            if i + 60 < len(df):
                ret60 = (c.iloc[i+60] / c.iloc[i] - 1) * 100
                results[key].append(ret60)
        elif r.iloc[i] >= 50:
            triggered = False

    print(f"=== {name} RSI<40 ===")
    for key, label in [('above', 'MA60上方'), ('below', 'MA60下方')]:
        trades = results[key]
        if trades:
            wins = sum(1 for r_ in trades if r_ > 0)
            print(f"  {label}: {len(trades)}次 | 60日均{np.mean(trades):+.1f}% | 胜率{wins}/{len(trades)}({wins/len(trades)*100:.0f}%) | 最好{max(trades):+.1f}% 最差{min(trades):+.1f}%")
        else:
            print(f"  {label}: 0次")
    total = len(results['above']) + len(results['below'])
    above_pct = len(results['above']) / total * 100 if total > 0 else 0
    print(f"  → MA60上方占比: {above_pct:.0f}%")
    print()
