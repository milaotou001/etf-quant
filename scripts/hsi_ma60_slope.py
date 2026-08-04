"""HSI: MA60斜率 vs 后续走势 —— 区分牛市回调/熊市开始"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']
r = df['rsi']

# MA60斜率: 当前MA60 vs 20日前MA60 的变化率
ma60 = df['ma60']
ma60_slope = (ma60 - ma60.shift(20)) / ma60.shift(20) * 100

# 当前状态
now = df.iloc[-1]
slope_now = ma60_slope.iloc[-1]
direction = "上升" if slope_now > 0.3 else ("走平" if slope_now > -0.3 else "下降")
print(f"=== HSI 当前 ===")
print(f"收盘: {now['close']:.0f}  MA60: {now['ma60']:.0f}")
print(f"MA60 20日斜率: {slope_now:+.1f}%  → {direction}")
print(f"RSI: {now['rsi']:.0f}")
print()

# RSI<35 买入，按 MA60斜率分组
print("=== RSI<35 触发，按 MA60 斜率分组 ===")
results_up = []    # MA60上升
results_flat = []  # MA60走平
results_down = []  # MA60下降
triggered = False

for i in range(60, len(df)):
    if r.iloc[i] < 35 and not triggered:
        triggered = True
        s = ma60_slope.iloc[i]
        if s > 0.5:
            key = 'up'
            results_up.append((df.index[i], c.iloc[i], r.iloc[i], s, c.iloc[i+60]/c.iloc[i]-1 if i+60<len(df) else np.nan))
        elif s < -0.5:
            key = 'down'
            results_down.append((df.index[i], c.iloc[i], r.iloc[i], s, c.iloc[i+60]/c.iloc[i]-1 if i+60<len(df) else np.nan))
        else:
            key = 'flat'
            results_flat.append((df.index[i], c.iloc[i], r.iloc[i], s, c.iloc[i+60]/c.iloc[i]-1 if i+60<len(df) else np.nan))
    elif r.iloc[i] >= 45:
        triggered = False

for label, data in [("MA60上升中（牛市回调）", results_up), ("MA60走平（方向不明）", results_flat), ("MA60下降中（熊市）", results_down)]:
    if data:
        rets = [d[4] for d in data if not np.isnan(d[4])]
        if rets:
            wins = sum(1 for r_ in rets if r_ > 0)
            print(f"  {label}: {len(data)}次 | 60日均{np.mean(rets)*100:+.1f}% | 胜率{wins}/{len(rets)}({wins/len(rets)*100:.0f}%) | 最好{max(rets)*100:+.1f}% 最差{min(rets)*100:+.1f}%")
            for d in data[:5]:
                print(f"    {d[0].strftime('%Y-%m')}  RSI={d[2]:.0f}  slope={d[3]:+.1f}%  60d={d[4]*100:+.1f}%")
    else:
        print(f"  {label}: 0次")
