"""回到过去：如果当时有工具，避免致命买卖点，收益会怎样"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data import load_data as _load_data
from indicators import rsi as _calc_rsi

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "普通账户电子对账单.xlsx")

# ETF 代码映射
SYMBOL_MAP = {"563360": "563360", "510300": "510300", "518880": "518880", "588000": "588000"}

def load_all_trades():
    """从 Excel 读取所有买卖记录，返回 DataFrame"""
    path = EXCEL_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_excel(path, sheet_name="Sheet1", header=None)
    header_row = None
    for i in range(len(df)):
        row_vals = [str(x) for x in df.iloc[i] if str(x) != "nan"]
        if "日期" in row_vals and "摘要" in row_vals and "成交数量" in row_vals:
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()

    cols = ["日期","币种","股东账号","证券代码","证券名称","摘要",
            "成交数量","成交均价","佣金","印花税","其他费","发生金额","资金余额"]
    tx = df.iloc[header_row + 1:].copy()
    tx.columns = cols
    tx = tx[tx["日期"].notna() & (tx["日期"].astype(str).str.match(r"^\d{8}$"))].copy()
    for c in ["成交数量","成交均价","佣金","印花税","其他费","发生金额"]:
        tx[c] = pd.to_numeric(tx[c], errors="coerce")
    tx["日期"] = pd.to_datetime(tx["日期"], format="%Y%m%d")
    tx = tx[tx["摘要"].isin(["证券买入","证券卖出"])].copy()
    tx["成交金额"] = tx["成交数量"] * tx["成交均价"]
    tx["手续费"] = tx["佣金"].abs() + tx["印花税"].abs() + tx["其他费"].abs()
    tx = tx.sort_values("日期").reset_index(drop=True)
    return tx


def classify_trades():
    """给每笔买卖打标签：致命 / 中性 / 合理"""
    trades = load_all_trades()
    if trades.empty:
        print("无交易数据")
        return

    # 加载各标的历史数据
    symbol_data = {}
    for sym in trades["证券代码"].unique():
        if sym in SYMBOL_MAP:
            try:
                df = _load_data(symbol=sym)
                df["rsi"] = _calc_rsi(df["close"], 14)
                df["ma20"] = df["close"].rolling(20).mean()
                df["ma60"] = df["close"].rolling(60).mean()
                symbol_data[sym] = df
            except Exception as e:
                print(f"  {sym} 数据加载失败: {e}")

    results = []
    for _, t in trades.iterrows():
        code = t["证券代码"]
        name = t["证券名称"]
        action = t["摘要"]
        date = t["日期"]
        price = t["成交均价"]
        qty = t["成交数量"]
        amount = t["成交金额"]

        df_sym = symbol_data.get(code)
        rsi_val = ma20_val = ma60_val = price_vs_ma20 = price_vs_ma60 = None

        if df_sym is not None and date in df_sym.index:
            row = df_sym.loc[date]
            rsi_val = row.get("rsi", None)
            ma20_val = row.get("ma20", None)
            ma60_val = row.get("ma60", None)
            if ma20_val and not pd.isna(ma20_val):
                price_vs_ma20 = (price / ma20_val - 1) * 100
            if ma60_val and not pd.isna(ma60_val):
                price_vs_ma60 = (price / ma60_val - 1) * 100
        elif df_sym is not None:
            # 找最近交易日
            avail = df_sym[df_sym.index <= date]
            if not avail.empty:
                row = avail.iloc[-1]
                rsi_val = row.get("rsi", None)
                ma20_val = row.get("ma20", None)
                ma60_val = row.get("ma60", None)
                if ma20_val and not pd.isna(ma20_val):
                    price_vs_ma20 = (price / ma20_val - 1) * 100
                if ma60_val and not pd.isna(ma60_val):
                    price_vs_ma60 = (price / ma60_val - 1) * 100

        # ── 分类逻辑 ──
        tag = "中性"
        reason = ""
        if action == "证券买入":
            if pd.isna(rsi_val):
                tag = "未知"
            elif rsi_val >= 65:
                tag = "致命"
                reason = f"RSI={rsi_val:.0f} 高位追涨"
            elif rsi_val >= 55 and price_vs_ma20 and price_vs_ma20 > 5:
                tag = "警告"
                reason = f"RSI={rsi_val:.0f} 偏强 + 价格高于MA20 {price_vs_ma20:.0f}%"
            elif rsi_val < 35:
                tag = "合理"
                reason = f"RSI={rsi_val:.0f} 低位买入，符合策略"
            else:
                tag = "中性"
                reason = f"RSI={rsi_val:.0f} 正常区间"
        else:  # 卖出
            if pd.isna(rsi_val):
                tag = "未知"
            elif rsi_val < 30:
                tag = "致命"
                reason = f"RSI={rsi_val:.0f} 恐慌卖出：在低位割肉"
            elif rsi_val < 40:
                tag = "警告"
                reason = f"RSI={rsi_val:.0f} 偏低位卖出"
            else:
                tag = "中性"

        results.append({
            "日期": date, "代码": code, "名称": name, "操作": "买" if action == "证券买入" else "卖",
            "价格": price, "数量": int(qty), "金额": amount,
            "RSI": round(rsi_val, 1) if not pd.isna(rsi_val) else None,
            "vs_MA20%": round(price_vs_ma20, 1) if price_vs_ma20 else None,
            "vs_MA60%": round(price_vs_ma60, 1) if price_vs_ma60 else None,
            "标签": tag, "原因": reason,
        })

    rdf = pd.DataFrame(results)
    rdf["手续费"] = trades["手续费"]

    # ── 统计 ──
    fatal = rdf[rdf["标签"] == "致命"]
    warn = rdf[rdf["标签"] == "警告"]
    good = rdf[rdf["标签"] == "合理"]

    print("=" * 80)
    print("【回到过去：当年如果我有这个工具...】")
    print()
    print(f"总交易 {len(rdf)} 笔 | 致命 {len(fatal)} 笔 | 警告 {len(warn)} 笔 | 合理 {len(good)} 笔")
    print()

    print("── 致命买卖（工具会强烈警告）──")
    for _, t in fatal.iterrows():
        sym = "RSI?" if pd.isna(t["RSI"]) else f"RSI={t['RSI']:.0f}"
        print(f"  {t['日期'].strftime('%Y-%m-%d')} {t['操作']} {t['名称']} {t['价格']:.3f} x{t['数量']}股 ¥{t['金额']:,.0f} | {sym} | {t['原因']}")

    print()
    print("── 警告级操作（工具会提示谨慎）──")
    for _, t in warn.iterrows():
        sym = "RSI?" if pd.isna(t["RSI"]) else f"RSI={t['RSI']:.0f}"
        print(f"  {t['日期'].strftime('%Y-%m-%d')} {t['操作']} {t['名称']} {t['价格']:.3f} x{t['数量']}股 ¥{t['金额']:,.0f} | {sym} | {t['原因']}")

    # ── 模拟：去掉致命操作 ──
    print()
    print("=" * 80)
    print("【模拟：如果避开致命操作的收益变化】")
    print()

    # 实际 P&L：用 FIFO 计算
    from collections import deque
    all_trades = []
    for sym in rdf["代码"].unique():
        st = rdf[rdf["代码"] == sym].sort_values("日期")
        queue = deque()
        for _, t in st.iterrows():
            is_buy = t["操作"] == "买"
            if is_buy:
                queue.append({"date": t["日期"], "qty": t["数量"], "price": t["价格"], "fee": t["手续费"],
                               "tag": t["标签"]})
            else:
                sell_qty = t["数量"]
                sell_price = t["价格"]
                sell_fee = t["手续费"]
                sell_tag = t["标签"]
                while sell_qty > 0 and queue:
                    buy = queue[0]
                    match_qty = min(sell_qty, buy["qty"])
                    buy_cost = match_qty * buy["price"] + buy["fee"] * (match_qty / max(1, buy["qty"]))
                    sell_proceeds = match_qty * sell_price - sell_fee * (match_qty / max(1, t["数量"]))
                    pnl = sell_proceeds - buy_cost
                    all_trades.append({
                        "sym": sym,
                        "buy_date": buy["date"], "sell_date": t["日期"],
                        "buy_price": buy["price"], "sell_price": sell_price,
                        "qty": match_qty, "pnl": pnl,
                        "buy_tag": buy["tag"], "sell_tag": sell_tag,
                        "is_fatal": (buy["tag"] == "致命" or sell_tag == "致命"),
                    })
                    buy["qty"] -= match_qty
                    if buy["qty"] <= 0:
                        queue.popleft()
                    sell_qty -= match_qty

    ap = pd.DataFrame(all_trades)
    actual_pnl = ap["pnl"].sum()
    fatal_pnl = ap[ap["is_fatal"]]["pnl"].sum()
    non_fatal_pnl = ap[~ap["is_fatal"]]["pnl"].sum()

    fatal_buys = ap[(ap["buy_tag"] == "致命")]["pnl"].sum()
    fatal_sells = ap[(ap["sell_tag"] == "致命")]["pnl"].sum()

    print(f"  实际净盈亏:       {actual_pnl:>+10,.0f} 元")
    print(f"  致命买入造成的亏损: {fatal_buys:>+10,.0f} 元")
    print(f"  致命卖出造成的亏损: {fatal_sells:>+10,.0f} 元")
    print(f"  致命操作合计影响:   {fatal_pnl:>+10,.0f} 元")
    print(f"  避开致命后净盈亏:   {non_fatal_pnl:>+10,.0f} 元")
    if actual_pnl != 0:
        print(f"  改善幅度:          {abs(fatal_pnl/actual_pnl)*100 if actual_pnl != 0 else 0:.0f}%")

    # ── 按标的拆分 ──
    print()
    print("── 按标的拆分 ──")
    for sym in sorted(ap["sym"].unique()):
        sap = ap[ap["sym"] == sym]
        pnl = sap["pnl"].sum()
        fpnl = sap[sap["is_fatal"]]["pnl"].sum()
        print(f"  {sym}: 实际 {pnl:+,.0f} | 致命操作 {fpnl:+,.0f} | 修正后 {pnl-fpnl:+,.0f}")

    print()
    print("=" * 80)
    print("【致命操作清单 TOP 10】")
    fatal_ap = ap[ap["is_fatal"]].copy()
    fatal_ap["abs_pnl"] = fatal_ap["pnl"].abs()
    fatal_ap = fatal_ap.sort_values("pnl")
    for i, (_, t) in enumerate(fatal_ap.head(10).iterrows()):
        tags = []
        if t["buy_tag"] == "致命": tags.append("买点致命")
        if t["sell_tag"] == "致命": tags.append("卖点致命")
        print(f"  {i+1}. {t['sym']} {t['buy_date'].strftime('%Y-%m-%d')}买→{t['sell_date'].strftime('%Y-%m-%d')}卖 "
              f"{t['buy_price']:.2f}→{t['sell_price']:.2f} {t['pnl']:+,.0f}元 | {'+'.join(tags)}")


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8-sig')
    classify_trades()
