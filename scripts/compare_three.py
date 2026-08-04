"""HSI vs 沪深300 vs 黄金 当前对比"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators, RSI_THRESHOLDS

for sym, name in [("510300", "沪深300"), ("518880", "黄金"), ("HSI", "恒生指数")]:
    rsi_buy = RSI_THRESHOLDS.get(sym, 30 if sym == "518880" else 35)
    df = compute_indicators(load_data(sym))
    l = df.iloc[-1]
    prev = df.iloc[-2]
    chg = (l['close'] / prev['close'] - 1) * 100

    # 距近期低点
    recent = df.loc['2026-06-01':]
    low = recent['close'].min()
    low_date = recent['close'].idxmin()

    print(f"=== {name} ({sym}) ===")
    print(f"日期: {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"价格: {l['close']:.4f}  今日: {chg:+.2f}%")
    print(f"RSI: {l['rsi']:.0f}  (买入阈值: {rsi_buy})")
    print(f"距近期低点: {(l['close']/low-1)*100:+.1f}% ({low_date.strftime('%m/%d')} @{low:.4f})")
    print(f"RVOL: {l.get('rvol', np.nan):.2f}" if not np.isnan(l.get('rvol', np.nan)) else "RVOL: N/A")
    print(f"MA20: {l['ma20']:.4f}  {'上方' if l['close'] > l['ma20'] else '下方'}")

    # 买入条件检查（黄金/沪深300用三笔制）
    if sym != "HSI":
        cond1 = l['rsi'] < rsi_buy + 5  # RSI 接近买入区
        cond2 = l['close'] > l['ma20']   # 站上MA20
        cond3 = l['rvol'] > 1.0 if not np.isnan(l.get('rvol', np.nan)) else None
        print(f"RSI接近买入区(<{rsi_buy+5}): {'是' if cond1 else '否'}  |  站上MA20: {'是' if cond2 else '否'}")

    # 黄金特别：之前说4/4条件满足
    if sym == "518880":
        from dashboard import build_buy_checklist
        cl = build_buy_checklist(df, rsi_buy)
        if cl:
            print(f"买入条件: {cl['met']}/{cl['total']}满足")

    print()
