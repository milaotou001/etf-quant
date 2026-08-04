import pandas as pd
hist = pd.read_csv(r'C:\Users\admin\Desktop\etf量化工具\cache\breadth\000300_price_history.csv', index_col=0)
print(f'Days: {len(hist)}')
print(f'Stocks: {len(hist.columns)}')
enough = sum(1 for c in hist.columns if hist[c].dropna().shape[0] >= 21)
print(f'Stocks with >=21 days: {enough}')
print(f'Date range: {hist.index[0]} ~ {hist.index[-1]}')
