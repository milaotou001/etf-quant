"""HSI: 大幅回调是牛市喘息还是熊市开始？"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']

# 找从6个月高点回撤>15%的时刻
results = []
for i in range(120, len(df)):
    high_6m = c.iloc[i-120:i].max()
    dd = (high_6m - c.iloc[i]) / high_6m * 100
    if dd > 15:
        # 往前看是不是已经在回撤中（避免同一波回撤重复计数）
        prev_dd = (high_6m - c.iloc[i-1]) / high_6m * 100 if i > 0 else 0
        if prev_dd > 15:
            continue  # 已经在回撤中，等它反弹再重新算

        # 往后看3/6/12个月
        for horizon, label in [(60, '3月'), (120, '6月'), (240, '12月')]:
            if i + horizon < len(df):
                ret = (c.iloc[i+horizon] / c.iloc[i] - 1) * 100
                new_high = c.iloc[i:i+horizon].max() > high_6m
                results.append({
                    'date': df.index[i],
                    'price': c.iloc[i],
                    'high_6m': high_6m,
                    'dd': dd,
                    'horizon': label,
                    'ret': ret,
                    'new_high': new_high
                })

# 去重：同一日期只算一次
seen = set()
unique_signals = []
for r_ in results:
    key = (r_['date'], r_['horizon'])
    if key not in seen:
        seen.add(key)
        unique_signals.append(r_)

print("=== HSI 从6月高点回撤>15% 后的表现 ===\n")
for label in ['3月', '6月', '12月']:
    subset = [x for x in unique_signals if x['horizon'] == label]
    rets = [x['ret'] for x in subset]
    wins = sum(1 for r_ in rets if r_ > 0)
    new_high_count = sum(1 for x in subset if x['new_high'])
    if rets:
        print(f"回撤>15%后{label}: {len(rets)}次 | 均收益{np.mean(rets):+.1f}% | 胜率{wins}/{len(rets)}({wins/len(rets)*100:.0f}%) | 创新高{new_high_count}/{len(rets)}")

# 最近的情况
print(f"\n=== 最近一次 ===")
recent_6m = c.iloc[-120:].max()
recent_dd = (recent_6m - c.iloc[-1]) / recent_6m * 100
print(f"6月高点: {recent_6m:.0f}  当前: {c.iloc[-1]:.0f}  回撤: {recent_dd:.1f}%")

# 牛市特征：2023-2025
print(f"\n=== 周期背景 ===")
bull_start = df.loc['2023-01-01':]
print(f"2023至今: 低{bull_start['close'].min():.0f} → 高{bull_start['close'].max():.0f} ({bull_start['close'].max()/bull_start['close'].min()*100-100:+.0f}%)")
