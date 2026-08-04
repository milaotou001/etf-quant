"""A500 周期频率分析 + 多ETF对比"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from data import load_data

df = load_data('563360')
close = df['close']
df['ma20'] = close.rolling(20).mean()
above = close > df['ma20']

# 找MA20上下穿转换点
switches = []
prev = above.iloc[0]
for i in range(1, len(above)):
    if above.iloc[i] != prev:
        date = above.index[i]
        direction = 'up' if above.iloc[i] else 'down'
        switches.append((date, direction))
        prev = above.iloc[i]

phases = []
for i in range(len(switches)):
    start = switches[i][0]
    end = switches[i+1][0] if i+1 < len(switches) else above.index[-1]
    days = (end - start).days
    label = 'above' if switches[i][1] == 'up' else 'below'
    phases.append((start, end, days, label))

print('=== A500 涨跌周期 (2025-03~2026-07) ===')
print()
for s, e, d, label in phases:
    tag = 'UP' if label == 'above' else 'DOWN'
    flag = ' << 短' if d < 15 else ''
    print(f'  {s.strftime("%Y-%m-%d")} ~ {e.strftime("%Y-%m-%d")} [{tag}] {d:3d}天{flag}')

# 统计
days_list = [d for _,_,d,_ in phases]
mid = len(days_list) // 2
first = days_list[:mid]
second = days_list[mid:]
print()
print(f'前半段平均: {np.mean(first):.0f}天  后半段平均: {np.mean(second):.0f}天')
if np.mean(second) < np.mean(first):
    print('>>> 周期在缩短，频率在加快')
print()

# 多ETF对比
print('=== 多ETF对比：近半年MA20上下穿越次数 ===')
for sym in ['563360', '510300', '588000', '518880']:
    d = load_data(sym)
    ma = d['close'].rolling(20).mean()
    ab = d['close'] > ma
    crosses = 0
    pv = ab.iloc[0]
    for i in range(1, len(ab)):
        if ab.iloc[i] != pv:
            crosses += 1
            pv = ab.iloc[i]
    # 只算最近半年
    half = d.index[-1] - pd.Timedelta(days=182)
    recent_ab = ab[ab.index >= half]
    rc = 0
    rpv = recent_ab.iloc[0]
    for i in range(1, len(recent_ab)):
        if recent_ab.iloc[i] != rpv:
            rc += 1
            rpv = recent_ab.iloc[i]
    names = {'563360': 'A500', '510300': '沪深300', '588000': '科创50', '518880': '黄金'}
    print(f'  {names.get(sym, sym)}: 近半年 {rc} 次穿越MA20')
