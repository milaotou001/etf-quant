"""A 股市场宽度历史数据回填。

从 akshare 拉取指数成分股的近 2 年日线，构建完整的 cache/breadth/ 价格历史。
沪深300 (000300): 300 只，A500 (000510): 500 只，科创50 (000688): 50 只。

预计耗时：850 只 × ~0.3s/只 ÷ 15 线程 ≈ 17 秒（理想情况），实际约 2-5 分钟（含重试和限流）。
"""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from breadth import (
    BREADTH_INDEX_MAP, CACHE_DIR, _price_history_path,
    fetch_constituents, load_price_history, update_price_history,
)

def backfill_index(index_code, index_name, use_sina, start_date="20240101", max_workers=15):
    """回填单个指数的完整价格历史。"""
    print(f"\n{'='*60}")
    print(f"回填 {index_name} ({index_code})")
    print(f"{'='*60}")

    # 1. 获取成分股列表
    try:
        constituents = fetch_constituents(index_code, use_sina, force_refresh=False)
    except Exception as e:
        print(f"  获取成分股失败: {e}")
        return

    symbols = constituents["symbol"].tolist()
    print(f"  成分股: {len(symbols)} 只")

    # 2. 加载现有价格历史
    hist = load_price_history(index_code)
    existing_cols = set(hist.columns) if not hist.empty else set()
    print(f"  现有历史: {len(hist)} 天, {len(existing_cols)} 只有数据")

    end_date = datetime.now().strftime("%Y%m%d")

    # 3. 确定需要拉取的股票
    # 检查哪些股票数据不足（< 200 天视为不足）
    need_fetch = []
    for sym in symbols:
        if sym not in existing_cols:
            need_fetch.append(sym)
        elif sym in hist.columns:
            data_count = hist[sym].dropna().shape[0]
            if data_count < 200:
                need_fetch.append(sym)

    if not need_fetch:
        print(f"  所有成分股数据充足，无需回填")
        return

    print(f"  需拉取: {len(need_fetch)} 只 (已有 {len(symbols) - len(need_fetch)} 只数据充足)")

    # 4. 分批并行拉取 (防止 akshare 反爬)
    new_data = {}  # symbol -> DataFrame
    total = len(need_fetch)
    done = 0

    def fetch_one(sym):
        """拉取单只股票 2 年日线。"""
        market_sym = f"sh{sym}" if sym.startswith(("5", "6", "9")) else f"sz{sym}"
        for attempt in range(3):
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=market_sym,
                    start_date=start_date,
                    end_date=end_date,
                )
                if df is not None and not df.empty and "close" in df.columns:
                    return sym, df
            except Exception:
                pass
            if attempt < 2:
                time.sleep(random.uniform(0.5, 2.0))
        return sym, None

    import akshare as ak

    # 分批次处理，每批 200 只
    batch_size = 200
    for batch_start in range(0, total, batch_size):
        batch = need_fetch[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"\n  批次 {batch_num}/{total_batches}: {len(batch)} 只...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, sym): sym for sym in batch}
            for future in as_completed(futures):
                sym, df = future.result()
                if df is not None:
                    new_data[sym] = df
                done += 1
                if done % 50 == 0:
                    print(f"    进度: {done}/{total} ({done*100//total}%), 成功 {len(new_data)}")

        if batch_start + batch_size < total:
            time.sleep(2.0)  # 批次间休息

    print(f"\n  拉取完成: 成功 {len(new_data)}/{total}")

    if not new_data:
        print("  无新数据，跳过写入")
        return

    # 5. 构建新的价格历史 DataFrame
    # 收集所有日期的所有股票价格
    all_dates = set()
    for sym, df in new_data.items():
        for _, row in df.iterrows():
            d = row["date"]
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
            all_dates.add(date_str)

    # 构建完整的价格矩阵
    price_dict = {}  # date_str -> {sym: price}
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

    # 6. 与现有数据合并
    if not hist.empty:
        # combine_first: 新数据优先，旧数据补充空白
        combined = new_df.combine_first(hist)
    else:
        combined = new_df

    # 确保所有成分股列都存在
    for sym in symbols:
        if sym not in combined.columns:
            combined[sym] = np.nan

    # 按成分股列表排序
    ordered_cols = [s for s in symbols if s in combined.columns]
    combined = combined[ordered_cols]

    # 7. 保存
    hist_path = _price_history_path(index_code)
    combined.to_csv(hist_path)
    print(f"  保存完成: {len(combined)} 天 x {len(combined.columns)} 只")
    print(f"  日期范围: {combined.index[0].date()} ~ {combined.index[-1].date()}")

    # 统计
    stocks_21d = sum(1 for c in combined.columns if combined[c].dropna().shape[0] >= 21)
    stocks_200d = sum(1 for c in combined.columns if combined[c].dropna().shape[0] >= 200)
    print(f"  数据>=21天: {stocks_21d} 只, >=200天: {stocks_200d} 只")


def main():
    print("A 股市场宽度历史数据回填")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标指数: 沪深300(000300), A500(000510), 科创50(000688)")

    # 回填顺序：科创50（50只快）→ 沪深300（300只）→ A500（500只）
    indices = [
        ("000688", "科创50", True),     # 50 只，Sina API
        ("000300", "沪深300", True),     # 300 只，Sina API
        ("000510", "A500", False),       # 500 只，中证 API
    ]

    # 先回填两个使用 Sina API 的
    for index_code, index_name, use_sina in indices:
        try:
            backfill_index(index_code, index_name, use_sina)
        except Exception as e:
            print(f"  !! {index_name} 回填失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
