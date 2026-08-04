import sys, os
sys.path.insert(0, r"C:\Users\admin\Desktop\etf量化工具")
from data import load_data
from dashboard import compute_indicators, build_market_state
import pandas as pd

df = load_data("561380", force_refresh=False)
df = compute_indicators(df)
latest = df.iloc[-1]
prev = df.iloc[-2]

# Market state
ms = build_market_state(df)

# Key metrics
print("=== 最新行情 ===")
print(f"日期: {df.index[-1].strftime('%Y-%m-%d')}")
print(f"收盘: {latest['close']:.4f} (前日 {prev['close']:.4f}, 涨跌 {latest.get('chg', 0):+.2%})")
print(f"MA5: {latest['ma5']:.4f}")
print(f"MA20: {latest['ma20']:.4f}")
print(f"MA60: {latest['ma60']:.4f}")
print(f"MA150: {latest['ma150']:.4f}")
print(f"RSI: {latest['rsi']:.2f}")

# MACD
macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
signal_col = [c for c in df.columns if c.startswith('MACDs_')][0]
hist_col = [c for c in df.columns if c.startswith('MACDh_')][0]
print(f"MACD DIF: {latest[macd_col]:.6f}")
print(f"MACD DEA: {latest[signal_col]:.6f}")
print(f"MACD HIST: {latest[hist_col]:.6f} (prev: {prev[hist_col]:.6f})")

print(f"\n=== 市场状态 ===")
print(f"状态: {ms['state_label']}")
print(f"说明: {ms['explanation']}")
print(f"评分: {ms['score']}")
print(f"MA60方向: {ms['ma60_direction']}")
print(f"MA150方向: {ms['ma150_direction']}")
print(f"排列: {ms['alignment']}")

# Price relative to key MAs
print(f"\n=== 价格位置 ===")
for ma in ['ma5','ma10','ma20','ma60','ma150']:
    if ma in latest.index and not pd.isna(latest[ma]):
        above = "上方" if latest['close'] > latest[ma] else "下方"
        pct = (latest['close']/latest[ma] - 1)*100
        print(f"vs {ma.upper()}: {above} ({pct:+.1f}%)")

# Recent trend
print(f"\n=== 近期走势 ===")
for i in [-20, -10, -5]:
    d = df.index[i]
    c = df['close'].iloc[i]
    print(f"{d.strftime('%Y-%m-%d')}: close={c:.4f}")

# Volume
print(f"\n=== 成交量 ===")
print(f"RVOL: {latest.get('rvol', 'N/A')}")
