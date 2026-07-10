"""从华泰证券电子对账单提取买卖记录，供图表叠加使用"""
import os
import json
import pandas as pd
import numpy as np


PRIVATE_DATA_DIR = os.path.join(os.path.dirname(__file__), "private_data")
TRADE_CACHE_PATH = os.path.join(PRIVATE_DATA_DIR, "trades.json")

# Excel 中的证券代码 → 项目 ETF 代码映射
_SYMBOL_MAP = {
    "563360": "563360",
    "510300": "510300",
    "518880": "518880",
    "588000": "588000",
    "513180": "513180",
    "159920": "159920",
}


def parse_trade_dataframe(df: pd.DataFrame) -> dict:
    """解析已上传到内存的电子对账单，不保存原始文件。"""
    header_row = None
    for i in range(len(df)):
        row_vals = [str(x) for x in df.iloc[i] if str(x) != "nan"]
        if "日期" in row_vals and "摘要" in row_vals and "成交数量" in row_vals:
            header_row = i
            break

    if header_row is None:
        return {}

    cols = ["日期", "币种", "股东账号", "证券代码", "证券名称", "摘要",
            "成交数量", "成交均价", "佣金", "印花税", "其他费", "发生金额", "资金余额"]
    tx = df.iloc[header_row + 1:].copy()
    tx.columns = cols
    tx = tx[tx["日期"].notna() & (tx["日期"].astype(str).str.match(r"^\d{8}$"))].copy()

    for c in ["成交数量", "成交均价"]:
        tx[c] = pd.to_numeric(tx[c], errors="coerce")
    tx["日期"] = pd.to_datetime(tx["日期"], format="%Y%m%d")

    trades = tx[tx["摘要"].isin(["证券买入", "证券卖出"])].copy()
    trades["成交金额"] = trades["成交数量"] * trades["成交均价"]
    trades = trades.sort_values("日期")
    trades = trades[trades["证券代码"].astype(str).isin(_SYMBOL_MAP.keys())].copy()

    if trades.empty:
        return {}

    result: dict[str, list[dict]] = {}
    for code in trades["证券代码"].astype(str).unique():
        code_trades = trades[trades["证券代码"].astype(str) == code]
        queue = []
        entries: list[dict] = []
        for _, t in code_trades.iterrows():
            if t["摘要"] == "证券买入":
                queue.append({"qty": t["成交数量"], "price": t["成交均价"]})
                entries.append({"date": t["日期"], "type": "buy", "price": t["成交均价"], "qty": int(t["成交数量"]), "amount": t["成交金额"]})
                continue

            remaining = t["成交数量"]
            total_cost = 0
            matched_qty = 0
            for buy in queue[:]:
                if remaining <= 0:
                    break
                matched = min(remaining, buy["qty"])
                total_cost += matched * buy["price"]
                matched_qty += matched
                buy["qty"] -= matched
                remaining -= matched
                if buy["qty"] <= 0:
                    queue.remove(buy)
            is_profit = matched_qty == 0 or t["成交均价"] > total_cost / matched_qty
            entries.append({"date": t["日期"], "type": "sell_profit" if is_profit else "sell_loss", "price": t["成交均价"], "qty": int(t["成交数量"]), "amount": t["成交金额"]})
        result[_SYMBOL_MAP[code]] = entries
    return result


def parse_statement(uploaded_file) -> dict:
    """读取 Streamlit 临时上传对象；调用方负责不将文件持久化。"""
    return parse_trade_dataframe(pd.read_excel(uploaded_file, sheet_name="Sheet1", header=None))


def _json_safe_entry(entry: dict) -> dict:
    """Convert parsed pandas/numpy values into stable JSON primitives."""
    result = dict(entry)
    date = result.get("date")
    if date is not None:
        result["date"] = pd.Timestamp(date).strftime("%Y-%m-%d")
    for key in ("price", "qty", "amount"):
        value = result.get(key)
        if value is not None and not pd.isna(value):
            result[key] = value.item() if hasattr(value, "item") else value
    return result


def save_trade_cache(trades: dict, path: str = TRADE_CACHE_PATH) -> None:
    """Persist parsed trade records only; the original statement is never stored."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    payload = {
        str(symbol): [_json_safe_entry(entry) for entry in entries]
        for symbol, entries in (trades or {}).items()
    }
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def load_trade_cache(path: str = TRADE_CACHE_PATH) -> dict:
    """Load the private parsed-trade cache, returning an empty mapping if absent."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    result = {}
    for symbol, entries in payload.items():
        result[str(symbol)] = []
        for entry in entries or []:
            item = dict(entry)
            if item.get("date") is not None:
                item["date"] = pd.Timestamp(item["date"])
            result[str(symbol)].append(item)
    return result


def update_trade_cache(uploaded_file, path: str = TRADE_CACHE_PATH) -> dict:
    """Parse a newly uploaded statement and replace the cached parsed records."""
    parsed = parse_statement(uploaded_file)
    if not parsed:
        raise ValueError("未识别到受支持的交易记录，原缓存未改变")
    save_trade_cache(parsed, path)
    return parsed


def load_trades(excel_path: str | None = None) -> dict:
    """读取交割单，返回 {symbol: [{date, type, price, qty, amount}]}。

    type: 'buy' | 'sell_profit' | 'sell_loss'
    盈亏按 FIFO 匹配，无法匹配的卖出视为平仓。
    """
    if not excel_path or not os.path.exists(excel_path):
        return {}
    return parse_trade_dataframe(pd.read_excel(excel_path, sheet_name="Sheet1", header=None))
