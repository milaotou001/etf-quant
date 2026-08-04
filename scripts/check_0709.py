"""Check A500/300 after 7/9 close"""
import sys; sys.path.insert(0, '.')
from data import load_data
from dashboard import compute_indicators

for sym, name in [("563360", "A500"), ("510300", "沪深300")]:
    try:
        df = compute_indicators(load_data(sym, force_refresh=True))
    except:
        df = compute_indicators(load_data(sym))
    l = df.iloc[-1]
    prev = df.iloc[-2]
    chg = (l['close'] / prev['close'] - 1) * 100
    chg_5d = (l['close'] / df.iloc[-6]['close'] - 1) * 100 if len(df) > 5 else 0
    chg_20d = (l['close'] / df.iloc[-21]['close'] - 1) * 100 if len(df) > 20 else 0

    print(f"=== {name} ({sym}) ===")
    print(f"最新: {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"收盘: {l['close']:.4f}  今日涨跌: {chg:+.2f}%")
    print(f"RSI: {l['rsi']:.0f}")
    print(f"MA5: {l['ma5']:.4f}  MA10: {l['ma10']:.4f}  MA20: {l['ma20']:.4f}")
    print(f"近5日: {chg_5d:+.1f}%  近20日: {chg_20d:+.1f}%")
    print(f"数据源: {df.attrs.get('source', '?')}")
    print()
