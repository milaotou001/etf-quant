"""A股宽度历史回填 v2 — 使用腾讯源 stock_zh_a_hist_tx，逐只稳健拉取。

策略：
- 每次拉取一只股票，间隔 0.3s，避免被封
- 10 线程并行，每批 100 只
- 目标：每只股票 2 年日线（约 500 个交易日）
"""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import akshare as ak

from breadth import (
    BREADTH_INDEX_MAP, _price_history_path,
    fetch_constituents, load_price_history,
)

START_DATE = "20240101"

def backfill_index(index_code, index_name, use_sina, max_workers=10):
    print(f"\n{'='*60}")
    print(f"回填 {index_name} ({index_code})")
    print(f"{'='*60}")

    # 1. 获取成分股
    try:
        constituents = fetch_constituents(index_code, use_sina, force_refresh=False)
    except Exception as e:
        print(f"  获取成分股失败: {e}")
        return
    symbols = constituents["symbol"].tolist()
    print(f"  成分股: {len(symbols)} 只")

    # 2. 现有数据
    hist = load_price_history(index_code)
    existing_cols = set(hist.columns) if not hist.empty else set()
    end_date = datetime.now().strftime("%Y%m%d")

    # 3. 找出需要拉取的股票（历史 < 200 天）
    need_fetch = []
    for sym in symbols:
        if sym not in existing_cols:
            need_fetch.append(sym)
        elif sym in hist.columns:
            if hist[sym].dropna().shape[0] < 200:
                need_fetch.append(sym)

    if not need_fetch:
        print(f"  所有 {len(symbols)} 只成分股数据充足，无需回填")
        return

    print(f"  需拉取: {len(need_fetch)}/{len(symbols)} 只")

    # 4. 逐批拉取
    new_data = {}
    total = len(need_fetch)

    def fetch_one(sym):
        market_sym = f"sh{sym}" if sym.startswith(("5", "6", "9")) else f"sz{sym}"
        for attempt in range(3):
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=market_sym, start_date=START_DATE, end_date=end_date)
                if df is not None and not df.empty and "close" in df.columns:
                    return sym, df
            except Exception:
                pass
            if attempt < 2:
                time.sleep(random.uniform(0.5, 1.5))
        return sym, None

    batch_size = 150
    for batch_start in range(0, total, batch_size):
        batch = need_fetch[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        t0 = time.time()
        print(f"  批次 {batch_num}/{total_batches}: {len(batch)} 只...", flush=True)

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(fetch_one, s): s for s in batch}
            for f in as_completed(futures):
                sym, df = f.result()
                if df is not None:
                    new_data[sym] = df

        elapsed = time.time() - t0
        print(f"    完成: {len(new_data)}/{total} 成功, 耗时 {elapsed:.0f}s", flush=True)

        if batch_start + batch_size < total:
            time.sleep(1.0)

    if not new_data:
        print("  无新数据")
        return

    # 5. 构建价格矩阵
    print(f"  构建价格矩阵...", flush=True)
    price_dict = {}
    for sym, df in new_data.items():
        for _, row in df.iterrows():
            d = row["date"]
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
            try:
                price_dict.setdefault(date_str, {})[sym] = float(row["close"])
            except (ValueError, TypeError):
                continue

    new_df = pd.DataFrame(price_dict).T
    new_df.index = pd.to_datetime(new_df.index)
    new_df = new_df.sort_index()

    # 6. 合并
    if not hist.empty:
        combined = new_df.combine_first(hist)
    else:
        combined = new_df

    for sym in symbols:
        if sym not in combined.columns:
            combined[sym] = np.nan

    ordered_cols = [s for s in symbols if s in combined.columns]
    combined = combined[ordered_cols]

    # 7. 保存
    hist_path = _price_history_path(index_code)
    combined.to_csv(hist_path)
    print(f"  保存: {len(combined)} 天 x {len(combined.columns)} 只")
    print(f"  日期: {combined.index[0].date()} ~ {combined.index[-1].date()}")

    s21 = sum(1 for c in combined.columns if combined[c].dropna().shape[0] >= 21)
    s200 = sum(1 for c in combined.columns if combined[c].dropna().shape[0] >= 200)
    print(f"  数据>=21天: {s21}, >=200天: {s200}")


def main():
    print("A股宽度历史回填 v2")
    print(f"开始: {datetime.now().strftime('%H:%M:%S')}")

    indices = [
        ("000688", "科创50", True),    # 50只，最快
        ("000300", "沪深300", True),    # 300只
        ("000510", "A500", False),      # 500只
    ]

    for index_code, index_name, use_sina in indices:
        try:
            backfill_index(index_code, index_name, use_sina)
        except Exception as e:
            print(f"  !! {index_name} 失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n完成: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
