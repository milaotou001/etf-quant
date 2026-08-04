from data import load_data
from dashboard import compute_indicators, _macd_cols
import numpy as np

df = compute_indicators(load_data('513180'))
c = df['close']
m,s,h = _macd_cols(df)
latest = df.iloc[-1]

print(f'恒生科技 当前: {c.iloc[-1]:.4f} ({df.index[-1].strftime("%Y-%m-%d")})')
print(f'ATH: {c.max():.4f}  ATL: {c.min():.4f}')
print(f'距ATH: {(c.iloc[-1]/c.max()-1)*100:+.1f}%')
print(f'距ATL: {(c.iloc[-1]/c.min()-1)*100:+.1f}%')
print()

# 近期低点
recent = df.loc['2026-06-01':]
low = recent['close'].min()
low_date = recent.index[recent['close'].argmin()]
low_rsi = recent.loc[low_date, 'rsi']
bounce = (c.iloc[-1] - low) / low * 100
print(f'近期低点: {low:.4f} ({low_date.strftime("%m/%d")}) RSI={low_rsi:.0f}')
print(f'反弹幅度: +{bounce:.1f}%')
print()

# 长中期统计
cv = c.values
dates = df.index
for label, horizon in [('10日',10), ('20日',20), ('60日',60), ('120日',120)]:
    chgs = []
    for i in range(20, len(cv)):
        lbh = cv[i-20:i].max()
        dd = (lbh - cv[i]) / lbh * 100
        if dd >= 10 and cv[i-1] < cv[i] and i+horizon < len(cv):
            chgs.append((cv[i+horizon]-cv[i])/cv[i]*100)
    if chgs:
        wins = sum(1 for x in chgs if x>0)
        print(f'{label}: avg {np.mean(chgs):+.1f}%  win {wins}/{len(chgs)}  max {max(chgs):+.1f}%  min {min(chgs):+.1f}%')

# 盈亏比
chgs_20d = []
for i in range(20, len(cv)):
    lbh = cv[i-20:i].max()
    dd = (lbh - cv[i]) / lbh * 100
    if dd >= 10 and cv[i-1] < cv[i] and i+20 < len(cv):
        chgs_20d.append((cv[i+20]-cv[i])/cv[i]*100)
pos = [x for x in chgs_20d if x>0]
neg = [x for x in chgs_20d if x<=0]
if neg and pos:
    print(f'\n20日盈亏比: {np.mean(pos)/abs(np.mean(neg)):.1f}:1')
