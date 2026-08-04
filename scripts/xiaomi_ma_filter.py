"""小米：MA20 vs MA60 趋势过滤对比 — RSI<40 买入后的表现"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('01810'))
c = df['close']
r = df['rsi']

# RSI<40 触发点，分别看 MA20 和 MA60 过滤效果
for horizon, label in [(20, '20日'), (60, '60日'), (120, '120日')]:
    ma_col = f'ma{horizon}'
    if ma_col not in df.columns:
        continue

    results = {'above': [], 'below': []}

    triggered = False
    for i in range(1, len(df)):
        if r.iloc[i] < 40 and not triggered:
            triggered = True
            above_ma = c.iloc[i] > df[ma_col].iloc[i]
            key = 'above' if above_ma else 'below'
            # 持仓60日收益
            if i + 60 < len(df):
                ret = (c.iloc[i+60] / c.iloc[i] - 1) * 100
                results[key].append({
                    'date': df.index[i],
                    'close': c.iloc[i],
                    'ma': df[ma_col].iloc[i],
                    'rsi': r.iloc[i],
                    'ret60d': ret
                })
        elif r.iloc[i] >= 45:
            triggered = False  # RSI回到45以上才算信号结束

    print(f'=== RSI<40 + 价格>{label.upper()} 过滤 ===')
    for key, label2 in [('above', f'价格在{label.upper()}上方'), ('below', f'价格在{label.upper()}下方')]:
        trades = results[key]
        if trades:
            rets = [t['ret60d'] for t in trades]
            wins = sum(1 for r_ in rets if r_ > 0)
            print(f'  {label2}: {len(trades)}次')
            print(f'    平均60日收益: {np.mean(rets):+.1f}%')
            print(f'    胜率: {wins}/{len(trades)}')
            print(f'    最好: {max(rets):+.1f}%  最差: {min(rets):+.1f}%')
        else:
            print(f'  {label2}: 0次')
    print()
