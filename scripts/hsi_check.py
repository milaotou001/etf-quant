from data import load_data
from dashboard import compute_indicators, _macd_cols
df = compute_indicators(load_data('159920'))
close = df['close']
m,c,h = _macd_cols(df)

print(f'Data range: {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
print(f'Current: {close.iloc[-1]:.4f}')
print(f'ATH: {close.max():.4f} ({df.index[close.argmax()].strftime("%Y-%m-%d")})')
print(f'ATL: {close.min():.4f} ({df.index[close.argmin()].strftime("%Y-%m-%d")})')

# Recent 1 year
recent = df.loc['2025-07-01':]
print(f'1Y High: {recent["close"].max():.4f}')
print(f'1Y Low: {recent["close"].min():.4f}')

# Key levels
print()
print('Recent lows:')
lows = recent.nsmallest(5, 'close')
for i, (idx, row) in enumerate(lows.iterrows()):
    print(f'  {idx.strftime("%m/%d")}: {row["close"]:.4f} RSI={row["rsi"]:.0f}')
