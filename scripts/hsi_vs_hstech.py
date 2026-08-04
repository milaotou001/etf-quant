from data import load_data
from dashboard import compute_indicators, _macd_cols
import numpy as np

for sym, name in [('159920', '恒生ETF'), ('513180', '恒生科技')]:
    df = compute_indicators(load_data(sym))
    c = df['close']
    m,s,h = _macd_cols(df)
    latest = df.iloc[-1]

    print(f'\n=== {name} ({sym}) ===')
    print(f'价格: {c.iloc[-1]:.4f}')
    print(f'ATH: {c.max():.4f} | ATL: {c.min():.4f}')
    print(f'距ATH: {(c.iloc[-1]/c.max()-1)*100:+.1f}% | 距ATL: {(c.iloc[-1]/c.min()-1)*100:+.1f}%')
    print(f'RSI: {latest["rsi"]:.0f} | MACD: DIF={latest[m]:+.4f} DEA={latest[s]:+.4f} HIST={latest[h]:+.4f}')
    print(f'MA5/10/20/60: {latest["ma5"]:.4f}/{latest["ma10"]:.4f}/{latest["ma20"]:.4f}/{latest["ma60"]:.4f}')

    vol_20d = c.pct_change().dropna().tail(20).std() * np.sqrt(252) * 100
    print(f'年化波动率: {vol_20d:.1f}%')

    recent = df.loc['2026-05-01':]
    rl = recent['close'].min()
    bounce = (c.iloc[-1] - rl) / rl * 100
    print(f'近3月低点: {rl:.4f} | 反弹: +{bounce:.1f}%')

    # 历史跌>10%后反弹统计
    cv = c.values
    b5,b10,b20 = [],[],[]
    for i in range(20, len(cv)):
        lbh = cv[i-20:i].max()
        dd = (lbh - cv[i]) / lbh * 100
        if dd >= 10 and cv[i-1] < cv[i]:
            if i+5 < len(cv): b5.append((cv[i+5]-cv[i])/cv[i]*100)
            if i+10 < len(cv): b10.append((cv[i+10]-cv[i])/cv[i]*100)
            if i+20 < len(cv): b20.append((cv[i+20]-cv[i])/cv[i]*100)

    if b5:
        print(f'跌>10%后买入: 5d {np.mean(b5):+.1f}% ({sum(1 for x in b5 if x>0)}/{len(b5)}) | 10d {np.mean(b10):+.1f}% ({sum(1 for x in b10 if x>0)}/{len(b10)}) | 20d {np.mean(b20):+.1f}% ({sum(1 for x in b20 if x>0)}/{len(b20)})')
        pos = [x for x in b10 if x>0]; neg = [x for x in b10 if x<=0]
        if neg: print(f'10日盈亏比: {np.mean(pos)/abs(np.mean(neg)):.1f}:1')
