"""HSI: 价格站上MA60 = 牛市确认？—— 看交叉后的收益"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('HSI'))
c = df['close']
ma60 = df['ma60']

# 找价格从下方穿越MA60的时点
crosses = []
for i in range(1, len(df)):
    if c.iloc[i-1] < ma60.iloc[i-1] and c.iloc[i] > ma60.iloc[i]:
        # 穿越发生
        cross_date = df.index[i]
        cross_price = c.iloc[i]
        cross_ma60 = ma60.iloc[i]
        # 1/3/6个月后收益
        for horizon, label in [(20, '1月'), (60, '3月'), (120, '6月')]:
            if i + horizon < len(df):
                ret = (c.iloc[i+horizon] / cross_price - 1) * 100
            else:
                ret = np.nan
            crosses.append({
                'date': cross_date,
                'price': cross_price,
                'horizon': label,
                'ret': ret
            })

# 按时间窗口汇总
for label in ['1月', '3月', '6月']:
    subset = [x for x in crosses if x['horizon'] == label and not np.isnan(x['ret'])]
    rets = [x['ret'] for x in subset]
    wins = sum(1 for r in rets if r > 0)
    if rets:
        print(f"价格上穿MA60后{label}: {len(rets)}次 | 均收益{np.mean(rets):+.1f}% | 胜率{wins}/{len(rets)}({wins/len(rets)*100:.0f}%) | 最好{max(rets):+.1f}% 最差{min(rets):+.1f}%")

# 而RSI<35买入（不设MA60条件）作为对照
print()
r = df['rsi']
rsi_ret20, rsi_ret60 = [], []
for i in range(14, len(df)):
    if r.iloc[i] < 35:
        if i + 20 < len(df):
            rsi_ret20.append((c.iloc[i+20]/c.iloc[i]-1)*100)
        if i + 60 < len(df):
            rsi_ret60.append((c.iloc[i+60]/c.iloc[i]-1)*100)
print(f"RSI<35（无条件）: 20日均{np.mean(rsi_ret20):+.1f}% 胜率{sum(1 for r in rsi_ret20 if r>0)}/{len(rsi_ret20)}")
print(f"RSI<35（无条件）: 60日均{np.mean(rsi_ret60):+.1f}% 胜率{sum(1 for r in rsi_ret60 if r>0)}/{len(rsi_ret60)}")

# 当前状态
now = df.iloc[-1]
print(f"\n当前: {now['close']:.0f} MA60: {now['ma60']:.0f} 差距: {(now['close']/now['ma60']-1)*100:+.1f}%")
print(f"需要涨{(now['ma60']/now['close']-1)*100:.1f}%才能站上MA60")
