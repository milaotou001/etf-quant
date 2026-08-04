"""小米：2025年RSI<30案例 + 当前趋势结构"""
import sys; sys.path.insert(0, '.')
import pandas as pd
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('01810'))
c = df['close']
r = df['rsi']
ma60 = df['ma60']
ma120 = df.get('ma120', None)

# 2025年10月前后 RSI<30
print("=== 2025年 RSI<30 触发 ===")
oct_lows = df.loc['2025-09-01':'2025-12-31']
for d, row in oct_lows.iterrows():
    if row['rsi'] < 30:
        above_ma60 = "上" if row['close'] > row['ma60'] else "下"
        print(f"  {d.strftime('%Y-%m-%d')} RSI={row['rsi']:.0f} close={row['close']:.2f} MA60={row['ma60']:.2f} ({above_ma60})")

# 看看那次之后的表现
print("\n=== 2025/10 RSI<30 之后走势 ===")
start = df.loc['2025-10-01':].iloc[0]
start_date = df.loc['2025-10-01':].index[0]
print(f"10月初: {start['close']:.2f} (RSI={start['rsi']:.0f})")
for months in [1, 3, 6]:
    end_date = start_date + pd.DateOffset(months=months)
    if end_date in df.index:
        end_c = df.loc[end_date, 'close']
        chg = (end_c / start['close'] - 1) * 100
        print(f"  +{months}月: {end_c:.2f} ({chg:+.1f}%)")

# 当前趋势
print("\n=== 当前趋势结构 ===")
now = df.iloc[-1]
print(f"现在: {now['close']:.2f} ({df.index[-1].strftime('%Y-%m-%d')})")
print(f"MA60: {now['ma60']:.2f}  {'上' if now['close'] > now['ma60'] else '下'}")
if ma120 is not None:
    print(f"MA120: {now['ma120']:.2f}  {'上' if now['close'] > now['ma120'] else '下'}")

# 最近一年的高低结构
y = df.loc['2025-07-01':]
print(f"\n近一年: 高 {y['close'].max():.2f}  低 {y['close'].min():.2f}")
print(f"当前距高: {(now['close']/y['close'].max()-1)*100:+.1f}%")
print(f"当前距低: {(now['close']/y['close'].min()-1)*100:+.1f}%")
