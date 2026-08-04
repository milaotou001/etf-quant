"""小米/腾讯 技术面快速分析"""
import sys; sys.path.insert(0, '.')
from data import load_data
from dashboard import compute_indicators, _macd_cols
import numpy as np

for sym, name in [("01810", "小米"), ("00700", "腾讯")]:
    df = compute_indicators(load_data(sym))
    latest = df.iloc[-1]
    c = latest['close']
    m, s, h = _macd_cols(df)

    print(f"=== {name} ({sym}) === {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"价格: {c:.2f}")

    # 均线位置
    for ma in ['ma5', 'ma10', 'ma20']:
        v = latest[ma]
        above = "上" if c > v else "下"
        print(f"  {ma.upper()}: {v:.2f}  ({above})")

    # RSI
    rsi = latest['rsi']
    print(f"RSI(14): {rsi:.0f}")

    # MACD
    dif = latest[m] if m else np.nan
    dea = latest[s] if s else np.nan
    hist = latest[h] if h else np.nan
    prev_hist = df.iloc[-2][h] if h and len(df) > 1 else np.nan
    print(f"MACD: DIF {dif:+.3f}  DEA {dea:+.3f}  HIST {hist:+.3f}")

    # 动能方向
    if not np.isnan(hist) and not np.isnan(prev_hist):
        if hist > prev_hist:
            print(f"  柱状图动能: 增强（绿柱变长/红柱缩短）")
        else:
            print(f"  柱状图动能: 减弱")

    # RVOL
    rvol = latest.get('rvol', np.nan)
    if not np.isnan(rvol):
        print(f"RVOL: {rvol:.2f}")

    # 布林带位置
    bb_upper = latest.get('bb_upper', np.nan)
    bb_lower = latest.get('bb_lower', np.nan)
    bb_mid = latest.get('bb_mid', np.nan)
    if not np.isnan(bb_upper):
        bb_pos = (c - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
        print(f"布林带: 上{bb_upper:.2f} 中{bb_mid:.2f} 下{bb_lower:.2f}  位置: {bb_pos:.0f}%")

    # 近期走势（最近20天涨跌幅）
    chg_5d = (c / df.iloc[-6]['close'] - 1) * 100 if len(df) > 5 else 0
    chg_10d = (c / df.iloc[-11]['close'] - 1) * 100 if len(df) > 10 else 0
    chg_20d = (c / df.iloc[-21]['close'] - 1) * 100 if len(df) > 20 else 0
    print(f"近5日: {chg_5d:+.1f}%  近10日: {chg_10d:+.1f}%  近20日: {chg_20d:+.1f}%")

    print()
