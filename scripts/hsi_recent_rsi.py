"""HSI 近期RSI走势"""
import sys; sys.path.insert(0, '.')
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']
r = df['rsi']

# 最近半年
recent = df.loc['2026-01-01':]
print("=== HSI 2026年 RSI < 35 的日子 ===")
for d, row in recent.iterrows():
    if row['rsi'] < 35:
        print(f"  {d.strftime('%Y-%m-%d')}  RSI={row['rsi']:.0f}  close={row['close']:.0f}")

# ATH后的高低点
ath_date = recent['close'].idxmax()
atl_date = recent['close'].idxmin()
ath = recent.loc[ath_date]
atl = recent.loc[atl_date]
print(f"\n近半年高: {ath['close']:.0f} ({ath_date.strftime('%Y-%m-%d')}) RSI={ath['rsi']:.0f}")
print(f"近半年低: {atl['close']:.0f} ({atl_date.strftime('%Y-%m-%d')}) RSI={atl['rsi']:.0f}")
print(f"从高到低跌幅: {(atl['close']/ath['close']-1)*100:.1f}%")
print(f"当前: {c.iloc[-1]:.0f} RSI={r.iloc[-1]:.0f}  从低点反弹: {(c.iloc[-1]/atl['close']-1)*100:.1f}%")
