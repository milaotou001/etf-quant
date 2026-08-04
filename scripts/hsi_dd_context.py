"""HSI: 回撤>15% — 分离前期趋势向上 vs 向下"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']

# 判断信号发生前的1年趋势方向
results_up = []    # 前期1年趋势向上（类似现在）
results_down = []  # 前期1年趋势向下

for i in range(240, len(df)):
    high_6m = c.iloc[i-120:i].max()
    dd = (high_6m - c.iloc[i]) / high_6m * 100
    if dd > 15:
        prev_dd = (high_6m - c.iloc[i-1]) / high_6m * 100 if i > 0 else 0
        if prev_dd > 15:
            continue

        # 前1年趋势：价格是否高于1年前
        prior_up = c.iloc[i] > c.iloc[i-240]  # 类似现在：1年前在更低位置

        if i + 120 < len(df):
            ret60 = (c.iloc[i+60] / c.iloc[i] - 1) * 100
            ret120 = (c.iloc[i+120] / c.iloc[i] - 1) * 100
            new_high = c.iloc[i:i+120].max() > high_6m
            entry = {'date': df.index[i], 'price': c.iloc[i], 'dd': dd,
                     'ret60': ret60, 'ret120': ret120, 'new_high': new_high}
            if prior_up:
                results_up.append(entry)
            else:
                results_down.append(entry)

print("=== 前期1年趋势向上的回撤（类似现在：2023-2026是牛市）===")
if results_up:
    rets60 = [x['ret60'] for x in results_up]
    rets120 = [x['ret120'] for x in results_up]
    nh = sum(1 for x in results_up if x['new_high'])
    print(f"{len(results_up)}次 | 6月均{np.mean(rets60):+.1f}% | 12月均{np.mean(rets120):+.1f}% | 创新高{nh}/{len(results_up)}({nh/len(results_up)*100:.0f}%)")
    for x in results_up:
        print(f"  {x['date'].strftime('%Y-%m')} dd={x['dd']:.0f}% @{x['price']:.0f}  6m={x['ret60']:+.1f}%  12m={x['ret120']:+.1f}%  {'新高' if x['new_high'] else '未新高'}")
else:
    print("  无信号")

print(f"\n=== 前期1年趋势向下的回撤 ===")
if results_down:
    rets60_d = [x['ret60'] for x in results_down]
    rets120_d = [x['ret120'] for x in results_down]
    print(f"{len(results_down)}次 | 6月均{np.mean(rets60_d):+.1f}% | 12月均{np.mean(rets120_d):+.1f}%")
else:
    print("  无")

# 当前
print(f"\n当前: {c.iloc[-1]:.0f}  1年前: {c.iloc[-240]:.0f}  前期趋势: {'向上' if c.iloc[-1] > c.iloc[-240] else '向下'}")
