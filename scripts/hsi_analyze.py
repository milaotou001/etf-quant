import akshare as ak
import pandas as pd
import numpy as np

df = ak.stock_hk_index_daily_sina(symbol="HSI")
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date').sort_index()
close = df['close']

print(f'恒生指数: {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
print(f'当前(7/8): {close.iloc[-1]:.0f}')
print(f'历史最高: {close.max():.0f} ({df.index[close.argmax()].strftime("%Y-%m-%d")})')
print(f'历史最低: {close.min():.0f} ({df.index[close.argmin()].strftime("%Y-%m-%d")})')
print()

# 高低区间位置
pct_pos = (close.iloc[-1] - close.min()) / (close.max() - close.min()) * 100
print(f'在历史区间位置: {pct_pos:.0f}% (0%=最低, 100%=最高)')
print(f'距最高: {(close.iloc[-1]/close.max()-1)*100:.1f}%')
print(f'距最低: {(close.iloc[-1]/close.min()-1)*100:.1f}%')
print()

# 年度数据
print('=== 年度表现 ===')
yearly = close.resample('YE').last()
prev = None
for year in range(2013, 2027):
    ts = pd.Timestamp(f'{year}-12-31')
    if ts in yearly.index:
        val = yearly.loc[ts]
        if prev is not None:
            chg = (val - prev) / prev * 100
            print(f'{year}: {val:.0f} ({chg:+.1f}%)')
        else:
            print(f'{year}: {val:.0f}')
        prev = val

print()

# 牛熊阶段
print('=== 关键牛熊周期 ===')
print(f'2018-01 高点: {close.loc["2018-01-01":"2018-01-31"].max():.0f}')
print(f'2020-03 低点: {close.loc["2020-03-01":"2020-03-31"].min():.0f}')
print(f'2021-02 高点: {close.loc["2021-02-01":"2021-02-28"].max():.0f}')
print(f'2022-10 低点: {close.loc["2022-10-01":"2022-10-31"].min():.0f}')
print(f'2025 高点: {close.loc["2025-01-01":"2025-12-31"].max():.0f}')
print(f'当前: {close.iloc[-1]:.0f}')
print()

# 从2018高点算起
ath_2018 = close.loc['2018-01-01':'2018-01-31'].max()
print(f'距2018年高点({ath_2018:.0f}): {(close.iloc[-1]/ath_2018-1)*100:.1f}%')
# 从2022低点算起
low_2022 = close.loc['2022-10-01':'2022-10-31'].min()
print(f'距2022年低点({low_2022:.0f}): {(close.iloc[-1]/low_2022-1)*100:.1f}%')
