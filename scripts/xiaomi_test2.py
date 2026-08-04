import akshare as ak

for sym, name in [("01810", "小米"), ("00700", "腾讯")]:
    print(f'=== {name} ({sym}) ===')

    # stock_hk_daily (no period param)
    try:
        df = ak.stock_hk_daily(symbol=sym, adjust="qfq")
        print(f'  stock_hk_daily: OK {len(df)} rows')
        print(f'  Columns: {list(df.columns)}')
        print(f'  Last: {df.iloc[-1].to_dict()}')
        print()
        continue
    except Exception as e:
        print(f'  stock_hk_daily: {str(e)[:100]}')

    # Try Sina HK stock
    try:
        df = ak.stock_hk_spot_em()
        print(f'  stock_hk_spot_em: OK')
        break
    except:
        pass

    print()
