from data import load_data
from dashboard import compute_indicators
import numpy as np

df = compute_indicators(load_data('159920'))
c = df['close'].values
dates = df.index

print('恒生ETF 大跌(>10%)后中长期表现')
print('=' * 85)
print(f'{"买入日":8s} {"买入价":>7s} {"跌幅":>6s} {"20日":>7s} {"60日":>7s} {"120日":>7s} {"250日":>7s} {"终点":>7s}')
print('-' * 85)

for i in range(20, len(c)):
    lbh = c[i-20:i].max()
    hi = i-20 + c[i-20:i].argmax()
    dd = (lbh - c[i]) / lbh * 100
    if dd >= 10 and c[i-1] < c[i]:
        seg_low = c[hi:i+1].min()
        results = []
        for h in [20, 60, 120, 250]:
            if i+h < len(c):
                chg = (c[i+h]-c[i])/c[i]*100
                results.append(f'{chg:+5.1f}%')
            else:
                results.append('N/A')
        final = f'{c[min(i+250, len(c)-1)]:.4f}' if i+250 < len(c) else 'N/A'
        print(f'{dates[i].strftime("%m/%d"):8s} {c[i]:7.4f} {-dd:5.1f}% {results[0]:>7s} {results[1]:>7s} {results[2]:>7s} {results[3]:>7s} {final:>7s}')

print()
print('当前: 07/09 1.4250 -20.5% (从1.685)')
print()

# 统计中长期胜率
for horizon, label in [(60, '60日'), (120, '120日'), (250, '250日')]:
    chgs = []
    for i in range(20, len(c)):
        lbh = c[i-20:i].max()
        dd = (lbh - c[i]) / lbh * 100
        if dd >= 10 and c[i-1] < c[i] and i+horizon < len(c):
            chgs.append((c[i+horizon]-c[i])/c[i]*100)
    if chgs:
        wins = sum(1 for x in chgs if x>0)
        print(f'{label}: avg {np.mean(chgs):+.1f}%  win {wins}/{len(chgs)}  max {max(chgs):+.1f}%  min {min(chgs):+.1f}%')
