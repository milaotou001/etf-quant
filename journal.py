"""交易日志：记录每日看盘分析、预测和操作计划，支持事后回顾对比。"""
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from data import load_data
from dashboard import compute_indicators, build_market_analysis, get_rsi_threshold, _macd_cols

JOURNAL_DIR = os.path.join(os.path.dirname(__file__), "journal")
REVIEW_START = "<!-- REVIEW_START -->"
REVIEW_END = "<!-- REVIEW_END -->"


def _journal_path(symbol: str, date_str: str = None) -> str:
    """返回日志文件路径。date_str 为 YYYY-MM-DD 格式，默认今天。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    dir_path = os.path.join(JOURNAL_DIR, symbol)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"{date_str}.md")


def _fmt_date_cn(date_str: str) -> str:
    """2026-07-04 -> 2026-07-04（周五）"""
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{date_str}（{weekdays[dt.weekday()]}）"


def create_entry(symbol: str, df: pd.DataFrame, analysis: str,
                 prediction: str, plan: str) -> str:
    """创建当日交易日志。返回文件路径。"""
    df = compute_indicators(df)
    latest = df.iloc[-1]
    today_str = df.index[-1].strftime("%Y-%m-%d")
    prev = df.iloc[-2] if len(df) >= 2 else None

    path = _journal_path(symbol, today_str)
    if os.path.exists(path):
        return path  # 当日已有日志，不覆盖

    analysis_result = build_market_analysis(df)
    state_label = analysis_result["state_label"]

    macd_col, signal_col, hist_col = _macd_cols(df)
    macd_state = analysis_result["steps"][2][1] if len(analysis_result["steps"]) > 2 else ""
    macd_val = latest[macd_col] if macd_col else np.nan
    hist_val = latest[hist_col] if hist_col else np.nan

    chg = latest.get("chg", np.nan)
    rvol = latest.get("rvol", np.nan)

    # 格式化数值
    def _v(val, fmt=".4f"):
        return f"{val:{fmt}}" if not pd.isna(val) else "N/A"

    content = f"""# {symbol} ETF — {_fmt_date_cn(today_str)}

## 当日数据

| 指标 | 数值 |
|------|------|
| 收盘价 | {_v(latest['close'])} |
| MA5 | {_v(latest['ma5'])} |
| MA10 | {_v(latest['ma10'])} |
| MA20 | {_v(latest['ma20'])} |
| RSI | {_v(latest['rsi'], '.0f')} |
| DIF/DEA | {_v(macd_val)} / {_v(latest[signal_col] if signal_col else np.nan)} |
| MACD HIST | {_v(hist_val)} |
| MACD 状态 | {macd_state} |
| RVOL | {_v(rvol, '.2f')} |
| 当日涨跌 | {_v(chg, '+.1f')}% |
| 工具判断 | {state_label} |

## 我的分析

{analysis}

## 我的预测

{prediction}

## 操作计划

{plan}

---
<!-- REVIEW_PLACEHOLDER -->
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def list_entries(symbol: str):
    """列出某 ETF 的所有日志文件，按日期排序。返回 [(date_str, path), ...]"""
    dir_path = os.path.join(JOURNAL_DIR, symbol)
    if not os.path.isdir(dir_path):
        return []
    entries = []
    for fname in os.listdir(dir_path):
        if fname.endswith(".md") and re.match(r"\d{4}-\d{2}-\d{2}\.md", fname):
            entries.append((fname[:10], os.path.join(dir_path, fname)))
    entries.sort()
    return entries


def compute_review_metrics(prices: pd.Series) -> dict[str, float]:
    """以入场日为基准计算收益，并以历史峰值计算真实最大回撤。"""
    clean = pd.to_numeric(prices, errors="coerce").dropna()
    if clean.empty:
        raise ValueError("没有可用于复盘的价格数据")
    start_price = clean.iloc[0]
    running_peak = clean.cummax()
    drawdowns = clean / running_peak - 1
    return {
        "total_change": (clean.iloc[-1] / start_price - 1) * 100,
        "max_gain": (clean.max() / start_price - 1) * 100,
        "max_drawdown": drawdowns.min() * 100,
        "max_price": float(clean.max()),
        "min_price": float(clean.min()),
    }


def upsert_review_section(content: str, body: str) -> str:
    """复盘区块幂等更新，避免每次回顾都追加重复内容。"""
    block = f"{REVIEW_START}\n## 事后回顾\n\n{body.strip()}\n{REVIEW_END}"
    pattern = re.escape(REVIEW_START) + r".*?" + re.escape(REVIEW_END)
    if re.search(pattern, content, flags=re.DOTALL):
        return re.sub(pattern, block, content, flags=re.DOTALL)
    if "<!-- REVIEW_PLACEHOLDER -->" in content:
        return content.replace("<!-- REVIEW_PLACEHOLDER -->", block)
    return content.rstrip() + "\n\n" + block + "\n"


def review(symbol: str, entry_date: str) -> str:
    """回顾指定日期的日志。拉取从 entry_date 至今的实际数据，回填回顾区块。返回更新后的内容。"""
    path = _journal_path(symbol, entry_date)
    if not os.path.exists(path):
        raise FileNotFoundError(f"日志不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 获取从日志日期到今天的实际数据
    df = load_data(symbol, force_refresh=True)
    df = compute_indicators(df)
    entry_dt = pd.Timestamp(entry_date)
    actual_df = df.loc[entry_dt:]  # 日志日期及之后的数据

    if len(actual_df) <= 1:
        return content  # 没有后续数据

    # 构建实际走势表
    rows = []
    for i in range(min(len(actual_df), 30)):  # 最多显示30天
        row = actual_df.iloc[i]
        date_str = actual_df.index[i].strftime("%m-%d")
        close_val = row["close"]
        chg_val = row.get("chg", np.nan) if i > 0 else 0
        # 计算相对于日志日期的累计涨跌
        cum_chg = (close_val / actual_df.iloc[0]["close"] - 1) * 100
        rows.append(
            f"| {date_str} | {close_val:.4f} | {row['ma20']:.4f} | "
            f"{row['rsi']:.0f} | {chg_val:+.1f}% | {cum_chg:+.2f}% |"
        )

    table_header = "| 日期 | 收盘 | MA20 | RSI | 单日涨跌 | 累计涨跌 |\n"
    table_header += "|------|------|------|-----|----------|----------|\n"
    table = table_header + "\n".join(rows)

    # 计算统计
    start_price = actual_df.iloc[0]["close"]
    end_price = actual_df.iloc[-1]["close"]
    metrics = compute_review_metrics(actual_df["close"])
    total_chg = metrics["total_change"]
    max_price = metrics["max_price"]
    min_price = metrics["min_price"]
    max_drawdown = metrics["max_drawdown"]
    max_gain = metrics["max_gain"]

    direction = "上涨" if total_chg > 0 else "下跌"

    review_body = f"""**回顾日期：{datetime.now().strftime('%Y-%m-%d')}**

### 实际走势（{entry_date} 至今，共 {len(actual_df) - 1} 个交易日）

{table}

### 统计

| 指标 | 数值 |
|------|------|
| 起始价 | {start_price:.4f} |
| 最新价 | {end_price:.4f} |
| 区间涨跌 | {total_chg:+.2f}% |
| 最高价 | {max_price:.4f}（+{max_gain:.2f}%） |
| 最低价 | {min_price:.4f}（{max_drawdown:.2f}%） |
| 整体方向 | {direction} |

### 预测 vs 实际

> **原始预测**：见上方「我的预测」区块。
>
> **实际走势**：{direction}{abs(total_chg):.1f}%，区间最高+{max_gain:.1f}%，最低{max_drawdown:.1f}%。
>
> **结论**：⬜ 正确 / ⬜ 部分正确 / ⬜ 错误
>
> **按计划操作的话**：⬜ 待评估
"""

    content = upsert_review_section(content, review_body)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return content
