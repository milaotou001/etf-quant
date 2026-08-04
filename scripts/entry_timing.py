"""沪深300：RSI买入时机分析 — 延迟1天影响 + 不同RSI路径"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('510300'))
c = df['close']
r = df['rsi']

# ═══ 1. 延迟一天买的影响 ═══
print("=== 1. RSI<35 当天买 vs 第二天买 ===")
lag_results = []
for i in range(14, len(df) - 5):
    if r.iloc[i] < 35 and r.iloc[i-1] >= 35:  # 刚跌破35那天
        price_same = c.iloc[i]       # 当天收盘买
        price_next = c.iloc[i+1]     # 第二天开盘/收盘买
        # 后续收益
        for horizon, h_name in [(20, '20日'), (60, '60日')]:
            if i + horizon < len(df):
                ret_same = (c.iloc[i+horizon] / price_same - 1) * 100
                ret_next = (c.iloc[i+horizon] / price_next - 1) * 100
                lag_results.append({
                    'date': df.index[i], 'rsi': r.iloc[i],
                    'horizon': h_name,
                    'diff': (price_next / price_same - 1) * 100,  # 第二天便宜/贵了多少
                    'ret_same': ret_same,
                    'ret_next': ret_next
                })

for h in ['20日', '60日']:
    entries = [x for x in lag_results if x['horizon'] == h]
    if entries:
        diffs = [x['diff'] for x in entries]
        print(f"  延迟1天买入,{h}维度:")
        print(f"    平均价差: {np.mean(diffs):+.2f}% (正=第二天更贵)")
        print(f"    当天买{np.mean([x['ret_same'] for x in entries]):+.1f}% vs 第二天买{np.mean([x['ret_next'] for x in entries]):+.1f}%")
        print(f"    延迟导致少赚: {np.mean([x['ret_same']-x['ret_next'] for x in entries]):+.2f}%")

# ═══ 2. RSI路径分析 ═══
print("\n=== 2. RSI 跌到不同深度后的反弹 ===")
# 找 RSI 从45以上开始下跌的过程
paths = []
for i in range(20, len(df)):
    if r.iloc[i-1] >= 45 and r.iloc[i] < 45:  # RSI开始进入低位
        # 找这次下跌的最低RSI
        min_rsi = r.iloc[i]
        min_idx = i
        for j in range(i+1, min(i+30, len(df))):
            if r.iloc[j] < min_rsi:
                min_rsi = r.iloc[j]
                min_idx = j
            if r.iloc[j] >= 50:  # RSI回到50以上，这轮结束
                break
        # 分类
        if min_rsi >= 40:
            category = "只到40-45就反弹"
        elif min_rsi >= 35:
            category = "到35-40反弹"
        elif min_rsi >= 30:
            category = "到30-35反弹"
        else:
            category = "跌破30"

        if min_idx + 60 < len(df):
            ret60 = (c.iloc[min_idx+60] / c.iloc[min_idx] - 1) * 100
            paths.append({'date': df.index[i], 'category': category, 'min_rsi': min_rsi, 'ret60': ret60})

for cat in ["只到40-45就反弹", "到35-40反弹", "到30-35反弹", "跌破30"]:
    entries = [x for x in paths if x['category'] == cat]
    if entries:
        rets = [x['ret60'] for x in entries]
        wins = sum(1 for r_ in rets if r_ > 0)
        print(f"  {cat}: {len(entries)}次 | 60日均{np.mean(rets):+.1f}% | 胜率{wins}/{len(entries)}({wins/len(entries)*100:.0f}%)")
    else:
        print(f"  {cat}: 0次")
