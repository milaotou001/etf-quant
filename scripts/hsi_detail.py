from data import load_data
from dashboard import compute_indicators
import numpy as np

df = compute_indicators(load_data('159920'))
c = df['close'].values
dates = df.index

print('恒生ETF 跌>10%后反弹日买入，10日后表现')
print('='*70)
print(f'{"日期":8s} {"高点":>8s} {"低点":>8s} {"反弹买入":>8s} {"跌幅":>6s} {"10日后":>8s} {"盈亏":>7s}')
print('-'*70)

all_10d = []
for i in range(20, len(c)):
    lbh = c[i-20:i].max()
    hi = i-20 + c[i-20:i].argmax()
    dd = (lbh - c[i]) / lbh * 100
    if dd >= 10 and c[i-1] < c[i]:
        if i+10 < len(c):
            chg10 = (c[i+10] - c[i]) / c[i] * 100
            seg_low = c[hi:i+1].min()
            actual_dd = (c[hi] - seg_low) / c[hi] * 100
            all_10d.append(chg10)
            win_loss = 'WIN' if chg10 > 0 else 'LOSE'
            print(f'{dates[i].strftime("%m/%d"):8s} {c[hi]:8.4f} {seg_low:8.4f} {c[i]:8.4f} {-actual_dd:5.1f}% {c[i+10]:8.4f} {chg10:+6.1f}% {win_loss}')

print()
print(f'总次数: {len(all_10d)}')
pos = [x for x in all_10d if x > 0]
neg = [x for x in all_10d if x <= 0]
print(f'胜: {len(pos)}, 负: {len(neg)}')
print(f'胜率: {len(pos)/len(all_10d):.0%}')
print(f'平均正收益: {np.mean(pos):+.1f}%')
if neg:
    print(f'平均负收益: {np.mean(neg):+.1f}%')
    print(f'盈亏比: {np.mean(pos)/abs(np.mean(neg)):.1f}:1')
print()
print('159920 上市日期: 2023-07-10 (数据源限制)')
