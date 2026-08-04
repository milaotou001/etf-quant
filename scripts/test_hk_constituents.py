"""Test HK index constituent sources."""
import akshare as ak

# Try HSI
print("=== HSI (恒生指数) ===")
for method in ['index_stock_cons_sina', 'index_stock_cons']:
    try:
        fn = getattr(ak, method)
        df = fn('HSI')
        print(f'{method}: {df.shape}, cols={list(df.columns[:3])}')
        # Find code column
        for col in df.columns:
            vals = df[col].astype(str).head(3).tolist()
            if any(len(v) >= 4 and v.isdigit() for v in vals):
                print(f'  Likely code col: {col}, samples={df[col].head(5).tolist()}')
                break
    except Exception as e:
        print(f'{method}: ERROR {e}')

# Try Hang Seng Tech
print("\n=== Hang Seng Tech (恒生科技) ===")
for code in ['HSTECH', 'HSTEC', 'HSI TECH']:
    for method in ['index_stock_cons_sina', 'index_stock_cons']:
        try:
            fn = getattr(ak, method)
            df = fn(code)
            print(f'{method}({code}): {df.shape}')
            break
        except Exception:
            continue
    else:
        continue
    break
else:
    print("Could not find Hang Seng Tech constituents via akshare")
