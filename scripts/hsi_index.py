import akshare as ak
import pandas as pd
import numpy as np

# 恒生指数
try:
    df = ak.stock_hk_index_daily_em(symbol="HSI")
    df.columns = [c.lower() for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    close = df['close']

    print(f'恒生指数 数据范围: {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
    print(f'当前: {close.iloc[-1]:.0f}')
    print(f'历史最高: {close.max():.0f} ({df.index[close.argmax()].strftime("%Y-%m-%d")})')
    print(f'历史最低: {close.min():.0f} ({df.index[close.argmin()].strftime("%Y-%m-%d")})')

    # 当前相对历史位置
    pct_rank = (close.iloc[-1] - close.min()) / (close.max() - close.min()) * 100
    print(f'在历史高低区间位置: {pct_rank:.0f}%')

    # 距历史最高
    from_ath = (close.iloc[-1] / close.max() - 1) * 100
    print(f'距历史最高: {from_ath:.1f}%')
    print()

    # 历年表现
    print('=== 恒生指数 年度表现 ===')
    yearly = close.resample('YE').last()
    for year in range(yearly.index[0].year, yearly.index[-1].year + 1):
        if pd.Timestamp(f'{year}-12-31') in yearly.index:
            prev_year = pd.Timestamp(f'{year-1}-12-31')
            if prev_year in yearly.index:
                chg = (yearly.loc[pd.Timestamp(f'{year}-12-31')] / yearly.loc[prev_year] - 1) * 100
                print(f'{year}: {yearly.loc[pd.Timestamp(f"{year}-12-31")]:.0f} ({chg:+.1f}%)')
            else:
                print(f'{year}: {yearly.loc[pd.Timestamp(f"{year}-12-31")]:.0f}')

    # 最近几年
    print()
    print('=== 最近关键点位 ===')
    recent_years = close.loc['2020-01-01':]
    print(f'2020低: {recent_years.loc["2020-01-01":"2020-12-31"]["close"].min():.0f}')
    print(f'2021高: {recent_years.loc["2021-01-01":"2021-12-31"]["close"].max():.0f}')
    print(f'2022低: {recent_years.loc["2022-01-01":"2022-12-31"]["close"].min():.0f}')
    print(f'2024高: {recent_years.loc["2024-01-01":"2024-12-31"]["close"].max():.0f}')
    print(f'2025高: {recent_years.loc["2025-01-01":"2025-12-31"]["close"].max():.0f}')
    print(f'当前: {close.iloc[-1]:.0f}')

except Exception as e:
    print(f'Error: {e}')
    # Try alternative source
    print('Trying alternative...')
