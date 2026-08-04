"""检查小米/腾讯近期RSI低位"""
import sys; sys.path.insert(0, '.')
from data import load_data
from dashboard import compute_indicators

for sym, name in [('01810','小米'),('00700','腾讯')]:
    df = compute_indicators(load_data(sym))
    recent = df.loc['2026-06-01':]
    print(f'=== {name} ===')
    low_idx = recent['close'].idxmin()
    low = recent.loc[low_idx]
    print(f'近期低点: {low["close"]:.2f} ({low_idx.strftime("%m/%d")}) RSI={low["rsi"]:.0f}')
    now = recent.iloc[-1]
    print(f'当前: {now["close"]:.2f} ({recent.index[-1].strftime("%m/%d")}) RSI={now["rsi"]:.0f}')
    bounce = (now['close'] / low['close'] - 1) * 100
    print(f'从低点反弹: +{bounce:.1f}%')

    below_40 = recent[recent['rsi'] < 40]
    if len(below_40) > 0:
        print(f'RSI<40:')
        for d, row in below_40.iterrows():
            print(f'  {d.strftime("%m/%d")} RSI={row["rsi"]:.0f} close={row["close"]:.2f}')
    below_35 = recent[recent['rsi'] < 35]
    if len(below_35) > 0:
        print(f'RSI<35:')
        for d, row in below_35.iterrows():
            print(f'  {d.strftime("%m/%d")} RSI={row["rsi"]:.0f} close={row["close"]:.2f}')
    print()
