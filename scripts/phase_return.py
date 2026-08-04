"""四只ETF分阶段收益对比"""
import sys; sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from data import load_data

symbols = {'563360': 'A500', '510300': '沪深300', '588000': '科创50', '518880': '黄金'}

# 加载所有数据，对齐日期
dfs = {}
for sym in symbols:
    dfs[sym] = load_data(sym)

# 找共同日期范围
common_start = max(d.index[0] for d in dfs.values())
common_end = min(d.index[-1] for d in dfs.values())

print(f'数据范围: {common_start.strftime("%Y-%m-%d")} ~ {common_end.strftime("%Y-%m-%d")}')
print()

# 分阶段统计
phases = [
    ('2025上半年 (01-06)', '2025-01-02', '2025-06-30'),
    ('25年夏秋 (07-10)', '2025-07-01', '2025-10-31'),
    ('25年底 (11-12)', '2025-11-01', '2025-12-31'),
    ('26年初 (01-03)', '2026-01-01', '2026-03-31'),
    ('26年Q2至今 (04-07)', '2026-04-01', '2026-07-03'),
    ('全周期', common_start.strftime('%Y-%m-%d'), common_end.strftime('%Y-%m-%d')),
]

for phase_name, start, end in phases:
    print(f'【{phase_name}】')
    print(f'  {"ETF":<10} {"区间涨跌":>10} {"年化波动":>10}')
    print(f'  {"-"*30}')

    best = -999
    results = {}
    for sym, name in symbols.items():
        df = dfs[sym]
        mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        n = mask.sum()
        if n < 2:
            continue
        seg = df.loc[mask]
        chg = (seg['close'].iloc[-1] / seg['close'].iloc[0] - 1) * 100
        vol = seg['close'].pct_change().std() * np.sqrt(252) * 100
        results[name] = (chg, vol)
        if chg > best:
            best = chg

    for name, (chg, vol) in results.items():
        marker = ' *** 领涨' if chg == best else ''
        print(f'  {name:<10} {chg:>+9.1f}% {vol:>9.1f}%{marker}')
    print()
