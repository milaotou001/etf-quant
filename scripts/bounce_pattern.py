from data import load_data
from dashboard import compute_indicators
import numpy as np
import pandas as pd

df = compute_indicators(load_data('563360'))
close = df['close'].values
dates = df.index

# 找之前有一波6%+回调、然后单日大涨2%以上的日子，看看后续表现
print('=== 历史：大跌后单日暴涨2%+，后续怎么走 ===')
print()

for i in range(20, len(close)):
    today_chg = (close[i] - close[i-1]) / close[i-1] * 100

    if today_chg < 2.0:
        continue

    # 前20天的高点
    lookback = min(20, i)
    prev_high = close[i-lookback:i].max()
    prev_low = close[i-lookback:i].min()
    max_dd = (prev_high - prev_low) / prev_high * 100

    if max_dd < 4:
        continue

    # 找到这波回调的最低点
    dd_start = close[i-lookback:i].argmax() + (i-lookback)
    dd_end = close[dd_start:i].argmin() + dd_start
    dd_pct = (close[dd_start] - close[dd_end]) / close[dd_start] * 100

    if dd_pct < 4:
        continue

    date_str = dates[i].strftime('%m/%d')

    # 后续1天、3天、5天、10天的表现
    results = []
    for horizon in [1, 3, 5, 10]:
        if i + horizon < len(close):
            fwd_chg = (close[i+horizon] - close[i]) / close[i] * 100
            results.append(f'{fwd_chg:+.1f}%')
        else:
            results.append('N/A')

    # 看看弹之前的最低点离当前有多远
    low_to_now = (close[i] - close[dd_end]) / close[dd_end] * 100

    print(f'{date_str} 单日涨{close[i]:.4f}({today_chg:+.1f}%) '
          f'| 前回调{dates[dd_start].strftime("%m/%d")}→{dates[dd_end].strftime("%m/%d")} -{dd_pct:.1f}% '
          f'| 离低点已反弹{low_to_now:+.1f}%')
    print(f'  → 隔日:{results[0]} 3日:{results[1]} 5日:{results[2]} 10日:{results[3]}')

    # 如果是V型反弹次日，找第二天买入的胜率
    if len(results) >= 2:
        pass  # just print for now

print()
print('=== 总结 ===')
# 统计V型反弹次日的规律
bounce_next_day = []
for i in range(20, len(close)-1):
    today_chg = (close[i] - close[i-1]) / close[i-1] * 100
    if today_chg < 2.0:
        continue
    lookback = min(20, i)
    prev_high = close[i-lookback:i].max()
    prev_low = close[i-lookback:i].min()
    max_dd = (prev_high - prev_low) / prev_high * 100
    if max_dd < 4:
        continue
    next_chg = (close[i+1] - close[i]) / close[i] * 100
    bounce_next_day.append(next_chg)

if bounce_next_day:
    print(f'低位后单日暴涨>2%共{len(bounce_next_day)}次')
    print(f'次日平均: {np.mean(bounce_next_day):+.1f}%')
    print(f'次日上涨概率: {sum(1 for x in bounce_next_day if x > 0)}/{len(bounce_next_day)}')
    print(f'次日最大涨幅: +{max(bounce_next_day):.1f}%')
    print(f'次日最大跌幅: {min(bounce_next_day):.1f}%')
