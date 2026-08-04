from data import load_data
from dashboard import compute_indicators
df = compute_indicators(load_data('159920'))
close = df['close'].values
dates = df.index

# 找所有跌幅>15%的回调，看后面怎么走
print('=== 恒生ETF 历史大跌（>15%）后走势 ===')
print()

for i in range(20, len(close)):
    # 找局部高点之后的回撤
    lookback_high = close[i-20:i].max()
    high_idx = i-20 + close[i-20:i].argmax()
    dd = (lookback_high - close[i]) / lookback_high * 100

    if dd >= 15 and close[i-1] < close[i]:  # 跌超15%且今天反弹
        # 回溯确认这是这波回调的最低点附近
        segment_low = close[high_idx:i+1].min()
        actual_dd = (close[high_idx] - segment_low) / close[high_idx] * 100

        from_date = dates[high_idx].strftime('%m/%d')
        low_date = dates[high_idx + close[high_idx:i+1].argmin()].strftime('%m/%d')
        curr_date = dates[i].strftime('%m/%d')

        # 后续表现
        results = []
        for horizon in [1, 5, 10, 20, 60]:
            if i + horizon < len(close):
                chg = (close[i+horizon] - close[i]) / close[i] * 100
                results.append(f'{chg:+.1f}%')
            else:
                results.append('N/A')

        print(f'{from_date}高{close[high_idx]:.4f} -> {low_date}低{segment_low:.4f}(-{actual_dd:.1f}%)')
        print(f'  {curr_date}反弹至{close[i]:.4f} | 隔日:{results[0]} 5日:{results[1]} 10日:{results[2]} 20日:{results[3]} 60日:{results[4]}')
        print()

print('=== 总结 ===')
# 统计所有跌超15%后第5/10/20天的表现
drops_5d = []
drops_10d = []
drops_20d = []
for i in range(20, len(close)):
    lookback_high = close[i-20:i].max()
    high_idx = i-20 + close[i-20:i].argmax()
    dd = (lookback_high - close[i]) / lookback_high * 100
    if dd >= 15 and close[i-1] < close[i]:
        if i+5 < len(close):
            drops_5d.append((close[i+5]-close[i])/close[i]*100)
        if i+10 < len(close):
            drops_10d.append((close[i+10]-close[i])/close[i]*100)
        if i+20 < len(close):
            drops_20d.append((close[i+20]-close[i])/close[i]*100)

import numpy as np
if drops_5d:
    print(f'5日后: avg={np.mean(drops_5d):+.1f}% win={sum(1 for x in drops_5d if x>0)}/{len(drops_5d)}')
if drops_10d:
    print(f'10日后: avg={np.mean(drops_10d):+.1f}% win={sum(1 for x in drops_10d if x>0)}/{len(drops_10d)}')
if drops_20d:
    print(f'20日后: avg={np.mean(drops_20d):+.1f}% win={sum(1 for x in drops_20d if x>0)}/{len(drops_20d)}')
