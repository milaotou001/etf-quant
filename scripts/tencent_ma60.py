import sys; sys.path.insert(0, '.')
from data import load_data
from dashboard import compute_indicators
df = compute_indicators(load_data('00700'))
l = df.iloc[-1]
pos = "上方" if l['close'] > l['ma60'] else "下方"
print(f"腾讯: {l['close']:.2f}  MA60: {l['ma60']:.2f}  ({pos})")
