"""HSI: 均线多头排列 + 首次RSI<40 = 买入信号"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']
r = df['rsi']

# MA斜率: 用5日前的MA值计算方向
ma5_up = df['ma5'] > df['ma5'].shift(5)
ma10_up = df['ma10'] > df['ma10'].shift(5)
ma20_up = df['ma20'] > df['ma20'].shift(5)
all_mas_up = ma5_up & ma10_up & ma20_up  # 多头排列且向上

signals = []
in_uptrend = False
rsi_triggered = False  # 本轮上升趋势中是否已经触发过RSI<40

for i in range(40, len(df)):
    if not in_uptrend and all_mas_up.iloc[i]:
        in_uptrend = True
        rsi_triggered = False  # 新上升趋势，重置
    elif in_uptrend and not all_mas_up.iloc[i]:
        # 连续3天不在多头排列才算趋势结束
        if i >= 2 and not all_mas_up.iloc[i-2:i+1].any():
            in_uptrend = False
            rsi_triggered = False

    if in_uptrend and not rsi_triggered and r.iloc[i] < 40:
        rsi_triggered = True
        if i + 60 < len(df):
            ret20 = (c.iloc[i+20] / c.iloc[i] - 1) * 100
            ret60 = (c.iloc[i+60] / c.iloc[i] - 1) * 100
            signals.append({
                'date': df.index[i],
                'price': c.iloc[i],
                'rsi': r.iloc[i],
                'ret20': ret20,
                'ret60': ret60
            })

print(f"多头排列中首次RSI<40: 共{len(signals)}次")
if signals:
    rets20 = [s['ret20'] for s in signals]
    rets60 = [s['ret60'] for s in signals]
    wins20 = sum(1 for r_ in rets20 if r_ > 0)
    wins60 = sum(1 for r_ in rets60 if r_ > 0)
    print(f"  20日均收益: {np.mean(rets20):+.1f}%  胜率{wins20}/{len(rets20)}({wins20/len(rets20)*100:.0f}%)")
    print(f"  60日均收益: {np.mean(rets60):+.1f}%  胜率{wins60}/{len(rets60)}({wins60/len(rets60)*100:.0f}%)")
    print()
    for s in signals:
        print(f"  {s['date'].strftime('%Y-%m-%d')}  RSI={s['rsi']:.0f}  @{s['price']:.0f}  20d={s['ret20']:+.1f}%  60d={s['ret60']:+.1f}%")
else:
    print("  无信号（跟A股回测一样，多头排列时RSI到不了40？）")

# 当前状态
print(f"\n=== 当前 ===")
now = df.iloc[-1]
print(f"MA5: {now['ma5']:.0f}  MA10: {now['ma10']:.0f}  MA20: {now['ma20']:.0f}")
ma5_dir = "向上" if ma5_up.iloc[-1] else "向下"
ma10_dir = "向上" if ma10_up.iloc[-1] else "向下"
ma20_dir = "向上" if ma20_up.iloc[-1] else "向下"
print(f"MA5方向: {ma5_dir}  MA10方向: {ma10_dir}  MA20方向: {ma20_dir}")
print(f"多头排列: {'是' if all_mas_up.iloc[-1] else '否'}")
print(f"RSI: {now['rsi']:.0f}")
