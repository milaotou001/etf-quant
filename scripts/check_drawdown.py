from data import load_data
from dashboard import compute_indicators
import numpy as np

df = compute_indicators(load_data('563360'))

close = df['close'].values
dates = df.index

drawdowns = []
peak_idx = 0
for i in range(1, len(close)):
    if close[i] > close[peak_idx]:
        if peak_idx < i - 1:
            dd = (close[peak_idx] - close[i-1]) / close[peak_idx] * 100
            if dd > 3:
                drawdowns.append((dates[peak_idx], close[peak_idx],
                                  dates[i-1], close[i-1], dd))
        peak_idx = i
    elif i == len(close) - 1:
        dd = (close[peak_idx] - close[i]) / close[peak_idx] * 100
        if dd > 3:
            drawdowns.append((dates[peak_idx], close[peak_idx],
                              dates[i], close[i], dd))

print(f'当前价格: {close[-1]:.4f}  日期: {dates[-1].strftime("%Y-%m-%d")}')
print()

print('=== 563360 大幅回撤记录 (>3%) ===')
for i, (from_d, from_p, to_d, to_p, dd) in enumerate(drawdowns[-20:]):
    bar = '#' * int(dd)
    print(f'{i+1:2d}. {from_d.strftime("%m/%d")} -> {to_d.strftime("%m/%d")}: {from_p:.4f} -> {to_p:.4f}  -{dd:.1f}% {bar}')

print()
dd_pcts = [d[4] for d in drawdowns]
print(f'最大回撤: -{max(dd_pcts):.1f}%')
print(f'平均回撤: -{np.mean(dd_pcts):.1f}%')
print(f'中位数回撤: -{np.median(dd_pcts):.1f}%')
print(f'回撤次数: {len(dd_pcts)}')
