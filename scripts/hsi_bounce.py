from data import load_data
from dashboard import compute_indicators
import numpy as np

df = compute_indicators(load_data('HSI'))
c = df['close']
r = df['rsi']

recent = df.loc['2026-06-15':]
low = recent['close'].min()
low_date = recent.index[recent['close'].argmin()]
low_rsi = recent.loc[low_date, 'rsi']
now = c.iloc[-1]
bounce = (now - low) / low * 100
print(f'Low: {low:.0f} ({low_date.strftime("%m/%d")}) RSI={low_rsi:.0f}')
print(f'Now: {now:.0f} ({df.index[-1].strftime("%m/%d")})')
print(f'Bounce: +{bounce:.1f}%')
print()

# HSI历次RSI<30后60日涨幅
bounces = []
for i in range(1, len(c)):
    if r.iloc[i-1] < 30 and r.iloc[i] >= 30:
        if i+60 < len(c):
            peak_60d = c[i:i+60].max()
            bf = (peak_60d - c[i]) / c[i] * 100
            bounces.append(bf)
            print(f'{df.index[i].strftime("%m/%d")}: RSI exit 30 at {c[i]:.0f}, 60d max +{bf:.1f}%')

if bounces:
    print(f'\nAvg 60d max: +{np.mean(bounces):.1f}%')
    print(f'Min: +{min(bounces):.1f}%')
    print(f'Max: +{max(bounces):.1f}%')
