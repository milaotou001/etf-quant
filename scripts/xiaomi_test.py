import akshare as ak

for sym, name in [("01810", "小米"), ("00700", "腾讯")]:
    print(f'=== {name} ({sym}) ===')
    for func_name in ['stock_hk_hist', 'stock_hk_daily']:
        try:
            fn = getattr(ak, func_name)
            df = fn(symbol=sym, period="daily", start_date="20230101", end_date="20260709", adjust="qfq")
            print(f'  {func_name}: OK {len(df)} rows, last: {df.index[-1] if hasattr(df,"index") else df.iloc[-1].iloc[0]}')
            print(f'  Columns: {list(df.columns)}')
            print(f'  Last row: {df.iloc[-1].to_dict()}')
            break
        except Exception as e:
            print(f'  {func_name}: {str(e)[:80]}')
    print()
