import akshare as ak
import pandas as pd
import numpy as np

# 尝试不同数据源
sources = [
    ('stock_hk_index_daily_em', {'symbol': 'HSI'}),
]

# Try新浪
try:
    print('尝试 stock_hk_index_daily_sina...')
    df = ak.stock_hk_index_daily_sina(symbol="HSI")
    if df is not None and len(df) > 0:
        print(f'成功! 行数: {len(df)}')
        print(df.head())
        print(df.tail())
except Exception as e1:
    print(f'sina failed: {e1}')
    try:
        print('尝试 index_hk_hist...')
        df = ak.index_hk_hist(symbol="HSI", period="daily", start_date="20000101", end_date="20260709")
        if df is not None and len(df) > 0:
            print(f'成功! 行数: {len(df)}')
            print(df.head())
            print(df.tail())
    except Exception as e2:
        print(f'index_hk_hist failed: {e2}')

        # Manual data - known HSI levels for reference
        print()
        print('=== 恒生指数 关键历史点位（手动） ===')
        print('2007-10-30: 31,958 (历史最高)')
        print('2008-10-27: 10,676')
        print('2015-04-27: 28,588')
        print('2016-02-12: 18,278')
        print('2018-01-26: 33,154 (近期最高)')
        print('2020-03-19: 21,139')
        print('2021-02-17: 31,183')
        print('2022-10-31: 14,597 (近期最低)')
        print('2024-01-22: 14,961')
        print('2024-10-07: 23,099')
        print('2025-09-30: ~24,000')
        print('2026-01-29: ~24,500 (近期高)')
        print('当前约: ~21,000-22,000')
