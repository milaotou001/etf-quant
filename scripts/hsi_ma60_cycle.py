"""HSI: MA60 与牛熊周期 —— MA60上方/下方买入后的表现"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']
r = df['rsi']

# 当前状态
now = df.iloc[-1]
pos = "上方" if now['close'] > now['ma60'] else "下方"
pct_from_ma60 = (now['close'] / now['ma60'] - 1) * 100
print(f"=== HSI 当前 ===")
print(f"日期: {df.index[-1].strftime('%Y-%m-%d')}")
print(f"收盘: {now['close']:.0f}  MA60: {now['ma60']:.0f}  ({pos} {pct_from_ma60:+.1f}%)")
print(f"RSI: {now['rsi']:.0f}")
print()

# MA60 上方 vs 下方，RSI<35 买入后的60日表现
print(f"=== HSI RSI<35 触发，按 MA60 位置分组 ===")
results = {'above': [], 'below': []}
triggered = False
for i in range(60, len(df)):
    if r.iloc[i] < 35 and not triggered:
        triggered = True
        if c.iloc[i] > df['ma60'].iloc[i]:
            key = 'above'
        else:
            key = 'below'
        if i + 60 < len(df):
            ret60 = (c.iloc[i+60] / c.iloc[i] - 1) * 100
            results[key].append({
                'date': df.index[i],
                'price': c.iloc[i],
                'rsi': r.iloc[i],
                'ret60': ret60
            })
    elif r.iloc[i] >= 45:
        triggered = False

for key, label in [('above', 'MA60上方（牛市回调）'), ('below', 'MA60下方（可能转熊）')]:
    trades = results[key]
    if trades:
        rets = [t['ret60'] for t in trades]
        wins = sum(1 for r_ in rets if r_ > 0)
        print(f"  {label}: {len(trades)}次 | 60日均{np.mean(rets):+.1f}% | 胜率{wins}/{len(trades)}({wins/len(trades)*100:.0f}%) | 最好{max(rets):+.1f}% 最差{min(rets):+.1f}%")
        for t in trades:
            print(f"    {t['date'].strftime('%Y-%m-%d')}  RSI={t['rsi']:.0f}  @{t['price']:.0f}  60日后{t['ret60']:+.1f}%")
    else:
        print(f"  {label}: 0次")

# 近一年走势
y = df.loc['2025-07-01':]
print(f"\n近一年: 高{y['close'].max():.0f} 低{y['close'].min():.0f}")
ath = c.max()
print(f"ATH: {ath:.0f}  当前距ATH: {(now['close']/ath-1)*100:+.1f}%")
