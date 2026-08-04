"""小米/腾讯 历史价格位置分析"""
import sys; sys.path.insert(0, '.')
from data import load_data
import numpy as np

for sym, name in [("01810", "小米"), ("00700", "腾讯")]:
    df = load_data(sym)
    c = df['close']
    now = c.iloc[-1]
    ath = c.max()
    atl = c.min()
    pct = (c < now).mean() * 100  # percentile

    # 近期高低点
    y1 = df.loc['2025-07-01':]
    y1_high = y1['close'].max()
    y1_low = y1['close'].min()

    print(f"=== {name} ({sym}) ===")
    print(f"当前: {now:.2f}  ({df.index[-1].strftime('%Y-%m-%d')})")
    print(f"ATH:  {ath:.2f}  距ATH: {(now/ath-1)*100:+.1f}%")
    print(f"ATL:  {atl:.2f}  距ATL: {(now/atl-1)*100:+.1f}%")
    print(f"历史分位: {pct:.0f}%（{len(c)}个交易日中高于 {pct:.0f}% 的交易日）")
    print(f"近一年高: {y1_high:.2f}  近一年低: {y1_low:.2f}")
    print()

    # 分位段
    for q in [10, 25, 50, 75, 90]:
        v = np.percentile(c, q)
        marker = " <--" if now > v else ""
        print(f"  P{q}: {v:.2f}{marker}")
    print()
