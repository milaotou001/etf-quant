"""K线图绘制 — 标注关键位置，不标注买卖箭头"""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC"]


def resolve_chart_start(index, range_label: str):
    """根据页面区间标签返回图表起始日期。"""
    if len(index) == 0:
        raise ValueError("没有可用于绘图的数据")
    if range_label == "从诞生至今":
        return index[0]
    days_by_label = {"近 6 个月": 183, "近 1 年": 365, "近 2 年": 730}
    try:
        days = days_by_label[range_label]
    except KeyError as exc:
        raise ValueError(f"未知图表区间：{range_label}") from exc
    return index[-1] - pd.Timedelta(days=days)


def build_figure(df, symbol="563360", name=None, days=90, start_date=None, end_date=None, trades=None):
    label = name or symbol
    """trades: list[dict] with keys date, type, price, qty — overlay markers on price subplot."""

    if start_date is not None and end_date is not None:
        plot_df = df.loc[start_date:end_date].copy()
    else:
        plot_df = df.iloc[-days:].copy()

    bb_upper_col = bb_lower_col = None
    for c in df.columns:
        if c.startswith("BBU"):
            bb_upper_col = c
        elif c.startswith("BBL"):
            bb_lower_col = c

    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.06)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)

    ohlc = plot_df[["open", "high", "low", "close"]].copy()
    ohlc["date_num"] = np.arange(len(ohlc))
    up_color = "#bdc3c7" if trades else "red"
    down_color = "#95a5a6" if trades else "green"
    candlestick_ohlc(ax1, ohlc[["date_num", "open", "high", "low", "close"]].values,
                     width=0.6, colorup=up_color, colordown=down_color)

    ma_lines = [("ma5", "blue", "-"), ("ma10", "purple", "-"), ("ma20", "orange", "-")]
    if symbol in ("01810", "HSI"):
        ma_lines.append(("ma60", "#8B0000", "--"))

    for ma, color, style in ma_lines:
        if ma in plot_df.columns:
            ax1.plot(ohlc["date_num"], plot_df[ma].values, color=color,
                     linestyle=style, linewidth=1.0, label=ma.upper())

    if bb_upper_col and bb_lower_col:
        ax1.plot(ohlc["date_num"], plot_df[bb_upper_col].values, color="gray",
                 linestyle="--", linewidth=0.8, alpha=0.7, label="BB")
        ax1.plot(ohlc["date_num"], plot_df[bb_lower_col].values, color="gray",
                 linestyle="--", linewidth=0.8, alpha=0.7)
        ax1.fill_between(ohlc["date_num"],
                         plot_df[bb_upper_col].values,
                         plot_df[bb_lower_col].values, alpha=0.05, color="gray")

    latest_close = plot_df["close"].iloc[-1]
    ax1.axhline(y=latest_close, color="black", linestyle=":", linewidth=0.8, alpha=0.6)
    ax1.text(len(ohlc) - 1, latest_close, f" {latest_close:.4f}",
             fontsize=8, va="center", ha="left", alpha=0.8)

    # ── 交易标记 ──
    if trades:
        plot_dates = pd.DatetimeIndex(plot_df.index)
        mapped = []
        for t in trades:
            t_date = pd.Timestamp(t["date"])
            matches = plot_dates.get_indexer([t_date], method="nearest")
            idx = matches[0]
            if idx < 0 or idx >= len(plot_df):
                continue
            actual_date = plot_dates[idx]
            if abs((actual_date - t_date).days) > 2:
                continue
            mapped.append({"idx": idx, "price": t["price"], "type": t["type"],
                           "qty": t.get("qty", 100)})

        # 小单先画，大单后画 — 同一天大仓位在最上层
        mapped.sort(key=lambda m: m["qty"])
        for m in mapped:
            x = m["idx"]
            y = m["price"]
            t_type = m["type"]
            qty = m["qty"]

            if t_type == "buy":
                color, edge = "#e74c3c", "#c0392b"
            elif t_type == "sell_profit":
                color, edge = "#27ae60", "#1e8449"
            else:
                color, edge = "#5d6d7e", "#2c3e50"

            size = max(30, min(280, qty / 10))
            ax1.scatter(x, y, c=color, marker="o", s=size, edgecolors=edge,
                        linewidth=0.8, zorder=5, alpha=0.9)

    ax1.legend(loc="upper left", fontsize=7, ncol=4)
    ax1.set_ylabel("Price", fontsize=9)
    ax1.grid(True, alpha=0.3)

    if "rvol" in plot_df.columns and not plot_df["rvol"].dropna().empty:
        ax2.plot(ohlc["date_num"], plot_df["rvol"].values, color="#2c7fb8", linewidth=1.0, label="RVOL")
        ax2.axhline(y=1.0, color="black", linestyle=":", linewidth=0.8, alpha=0.5)
        ax2.axhline(y=1.5, color="orange", linestyle="--", linewidth=0.8, alpha=0.6)
        ax2.axhline(y=2.5, color="red", linestyle="--", linewidth=0.8, alpha=0.6)
        ax2.text(len(ohlc) - 1, 1.0, " 1.0", fontsize=7, va="bottom", ha="left", alpha=0.6)
        ax2.text(len(ohlc) - 1, 1.5, " 1.5", fontsize=7, va="bottom", ha="left", color="orange", alpha=0.7)
        ax2.text(len(ohlc) - 1, 2.5, " 2.5", fontsize=7, va="bottom", ha="left", color="red", alpha=0.7)
        max_rvol = np.nanmax(plot_df["rvol"].values) if not plot_df["rvol"].dropna().empty else 3
        ax2.set_ylim(0, max(3, max_rvol * 1.15))
    else:
        ax2.text(0.5, 0.5, "RVOL unavailable: amount missing",
                 transform=ax2.transAxes, ha="center", va="center", fontsize=9, alpha=0.6)
    ax2.set_ylabel("RVOL", fontsize=8)
    ax2.legend(loc="upper left", fontsize=7)
    ax2.grid(True, alpha=0.3)

    macd_col = next((c for c in plot_df.columns if c.startswith("MACD_")), None)
    signal_col = next((c for c in plot_df.columns if c.startswith("MACDs_")), None)
    hist_col = next((c for c in plot_df.columns if c.startswith("MACDh_")), None)
    if macd_col and signal_col and hist_col:
        hist_colors = ["red" if value >= 0 else "green" for value in plot_df[hist_col].values]
        ax3.bar(ohlc["date_num"], plot_df[hist_col].values, color=hist_colors, alpha=0.45, width=0.6, label="HIST")
        ax3.plot(ohlc["date_num"], plot_df[macd_col].values, color="#1f77b4", linewidth=1.0, label="DIF")
        ax3.plot(ohlc["date_num"], plot_df[signal_col].values, color="#ff7f0e", linewidth=1.0, label="DEA")
        ax3.axhline(y=0, color="black", linestyle=":", linewidth=0.8, alpha=0.5)
    ax3.set_ylabel("MACD", fontsize=8)
    ax3.legend(loc="upper left", fontsize=7, ncol=3)
    ax3.grid(True, alpha=0.3)

    if "rsi" in plot_df.columns:
        ax4.plot(ohlc["date_num"], plot_df["rsi"].values, color="blue", linewidth=1.0)
        ax4.axhline(y=70, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
        ax4.axhline(y=30, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
        ax4.fill_between(ohlc["date_num"], 70, 100, alpha=0.08, color="red")
        ax4.fill_between(ohlc["date_num"], 0, 30, alpha=0.08, color="green")
        ax4.text(len(ohlc) - 1, 70, " OB 70", fontsize=7, va="bottom", ha="left", color="red", alpha=0.6)
        ax4.text(len(ohlc) - 1, 30, " OS 30", fontsize=7, va="top", ha="left", color="green", alpha=0.6)
        ax4.set_ylim(0, 100)
        ax4.set_ylabel("RSI", fontsize=8)
        ax4.grid(True, alpha=0.3)

    tick_positions = ohlc["date_num"].iloc[::max(1, len(ohlc) // 10)]
    tick_labels = []
    prev_year = None
    for i in tick_positions:
        dt = plot_df.index[int(i)]
        if isinstance(dt, (pd.Timestamp, datetime)):
            if dt.year != prev_year:
                tick_labels.append(dt.strftime("%Y-%m"))
                prev_year = dt.year
            else:
                tick_labels.append(dt.strftime("%m"))
        else:
            tick_labels.append(str(dt)[:10])

    ax4.set_xticks(tick_positions)
    ax4.set_xticklabels(tick_labels, rotation=0, fontsize=8)
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    plt.setp(ax3.get_xticklabels(), visible=False)

    today_str = plot_df.index[-1].strftime("%Y-%m-%d") if isinstance(plot_df.index[-1], (pd.Timestamp, datetime)) else str(plot_df.index[-1])[:10]
    fig.suptitle(f"{symbol} - {label} ({today_str})", fontsize=13, fontweight="normal", y=0.96)

    return fig


def draw(df, indicators, symbol="563360", name=None, days=90, output_name=None):
    fig = build_figure(df, symbol=symbol, name=name, days=days)

    today_str = df.index[-1].strftime("%Y-%m-%d") if isinstance(df.index[-1], (datetime,)) else str(df.index[-1])[:10]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = output_name or f"chart_{today_str}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  Chart saved: {filepath}")
    return filepath
