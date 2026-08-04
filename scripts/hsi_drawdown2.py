from data import load_data
from dashboard import compute_indicators
import numpy as np
df = compute_indicators(load_data('159920'))
close = df['close'].values
dates = df.index

print('=== 恒生ETF 历史大跌（>10%）后走势 ===')
print()

for i in range(20, len(close)):
    lookback_high = close[i-20:i].max()
    high_idx = i-20 + close[i-20:i].argmax()
    dd = (lookback_high - close[i]) / lookback_high * 100

    if dd >= 10 and close[i-1] < close[i]:  # 跌超10%且今天反弹
        segment_low = close[high_idx:i+1].min()
        actual_dd = (close[high_idx] - segment_low) / close[high_idx] * 100
        low_offset = high_idx + close[high_idx:i+1].argmin()

        from_date = dates[high_idx].strftime('%m/%d')
        low_date = dates[low_offset].strftime('%m/%d')
        curr_date = dates[i].strftime('%m/%d')

        results = []
        for horizon in [1, 5, 10, 20]:
            if i + horizon < len(close):
                chg = (close[i+horizon] - close[i]) / close[i] * 100
                results.append(f'{chg:+.1f}%')
            else:
                results.append('N/A')

        # 跌了多久
        days_down = low_offset - high_idx
        days_up = i - low_offset

        print(f'{from_date}高{close[high_idx]:.4f} -> {low_date}低{segment_low:.4f}(-{actual_dd:.1f}% 跌{days_down}天)')
        print(f'  {curr_date}反弹{close[i]:.4f}(弹{days_up}天) | 隔日:{results[0]} 5日:{results[1]} 10日:{results[2]} 20日:{results[3]}')
        print()

# Stats
drops_5d = []
drops_10d = []
drops_20d = []
for i in range(20, len(close)):
    lookback_high = close[i-20:i].max()
    dd = (lookback_high - close[i]) / lookback_high * 100
    if dd >= 10 and close[i-1] < close[i]:
        if i+5 < len(close):
            drops_5d.append((close[i+5]-close[i])/close[i]*100)
        if i+10 < len(close):
            drops_10d.append((close[i+10]-close[i])/close[i]*100)
        if i+20 < len(close):
            drops_20d.append((close[i+20]-close[i])/close[i]*100)

print('=== 统计：跌>10%后反弹日买入，后续胜率 ===')
if drops_5d:
    print(f'5日: avg={np.mean(drops_5d):+.1f}% win={sum(1 for x in drops_5d if x>0)}/{len(drops_5d)}')
if drops_10d:
    print(f'10日: avg={np.mean(drops_10d):+.1f}% win={sum(1 for x in drops_10d if x>0)}/{len(drops_10d)}')
if drops_20d:
    print(f'20日: avg={np.mean(drops_20d):+.1f}% win={sum(1 for x in drops_20d if x>0)}/{len(drops_20d)}')
