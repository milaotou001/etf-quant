"""A500: RSI从低位反弹到50附近后，后续走势"""
import sys; sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('563360'))
c = df['close']
r = df['rsi']

# 找 RSI 从 <35 反弹到 45-55 区间的情况
# 然后看之后20日是否回踩（价格跌破反弹时价格）
cases = []
for i in range(20, len(df)):
    # 前20天内有RSI<35
    if r.iloc[i-20:i].min() < 35:
        # 当前RSI在45-55
        if 45 <= r.iloc[i] <= 55:
            entry_price = c.iloc[i]
            entry_date = df.index[i]
            # 之后20天
            if i + 20 < len(df):
                future = c.iloc[i+1:i+21]
                low_20d = future.min()
                pullback_pct = (low_20d / entry_price - 1) * 100
                close_20d = c.iloc[i+20]
                ret_20d = (close_20d / entry_price - 1) * 100
                cases.append({
                    'date': entry_date,
                    'price': entry_price,
                    'rsi': r.iloc[i],
                    'low_20d': low_20d,
                    'pullback': pullback_pct,
                    'ret_20d': ret_20d,
                })

# 去重：相邻30天内的只算一次
filtered = []
for case in cases:
    if not filtered or (case['date'] - filtered[-1]['date']).days > 30:
        filtered.append(case)

print(f"找到 {len(filtered)} 次 RSI从低位反弹到45-55")
print()
any_pullback = 0
no_pullback = 0

for c_ in filtered:
    had_pb = "回踩" if c_['pullback'] < -1 else "未回踩"
    if c_['pullback'] < -1:
        any_pullback += 1
    else:
        no_pullback += 1
    print(f"  {c_['date'].strftime('%Y-%m-%d')}  RSI={c_['rsi']:.0f}  {c_['price']:.4f}")
    print(f"    20日最低: {c_['low_20d']:.4f} ({c_['pullback']:.1f}%)  {had_pb}")
    print(f"    20日后: {c_['ret_20d']:+.1f}%")

if filtered:
    print(f"\n回踩(>1%): {any_pullback}/{len(filtered)}次")
    pullbacks = [c_['pullback'] for c_ in filtered]
    print(f"平均回踩幅度: {np.mean(pullbacks):.1f}%")
    print(f"最深回踩: {min(pullbacks):.1f}%")
