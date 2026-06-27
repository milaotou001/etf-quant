"""K线图绘制 — 标注关键位置，不标注买卖箭头"""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

import matplotlib.font_manager as fm
for fname in ["Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei", "Noto Sans CJK SC", "DejaVu Sans"]:
    try:
        fm.findfont(fname, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [fname, "DejaVu Sans"]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False


def build_figure(df, symbol="563360", name=None, days=90, start_date=None, end_date=None):
    label = name or symbol

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

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)

    ohlc = plot_df[["open", "high", "low", "close"]].copy()
    ohlc["date_num"] = np.arange(len(ohlc))
    candlestick_ohlc(ax1, ohlc[["date_num", "open", "high", "low", "close"]].values,
                     width=0.6, colorup="red", colordown="green")

    for ma, color, style in [("ma5", "blue", "-"), ("ma20", "orange", "-"), ("ma60", "purple", "--")]:
        if ma in plot_df.columns:
            ax1.plot(ohlc["date_num"], plot_df[ma].values, color=color,
                     linestyle=style, linewidth=1.0, label=ma.upper())

    if bb_upper_col and bb_lower_col:
        ax1.plot(ohlc["date_num"], plot_df[bb_upper_col].values, color="gray",
                 linestyle="--", linewidth=0.8, alpha=0.7, label="Bollinger")
        ax1.plot(ohlc["date_num"], plot_df[bb_lower_col].values, color="gray",
                 linestyle="--", linewidth=0.8, alpha=0.7)
        ax1.fill_between(ohlc["date_num"],
                         plot_df[bb_upper_col].values,
                         plot_df[bb_lower_col].values, alpha=0.05, color="gray")

    latest_close = plot_df["close"].iloc[-1]
    ax1.axhline(y=latest_close, color="black", linestyle=":", linewidth=0.8, alpha=0.6)
    ax1.text(len(ohlc) - 1, latest_close, f" {latest_close:.4f}",
             fontsize=8, va="center", ha="left", alpha=0.8)

    ax1.legend(loc="upper left", fontsize=7, ncol=4)
    ax1.set_ylabel("Price", fontsize=9)
    ax1.grid(True, alpha=0.3)

    colors = ["red" if plot_df["close"].iloc[i] >= plot_df["open"].iloc[i] else "green"
              for i in range(len(plot_df))]
    ax2.bar(ohlc["date_num"], plot_df["volume"].values / 10000, color=colors,
            alpha=0.6, width=0.6)
    if "vol_ma20" in plot_df.columns:
        ax2.plot(ohlc["date_num"], plot_df["vol_ma20"].values / 10000,
                 color="blue", linewidth=0.8, alpha=0.6, label="VOL MA20")
    ax2.set_ylabel("万手", fontsize=8)
    ax2.legend(loc="upper left", fontsize=7)
    ax2.grid(True, alpha=0.3)

    if "rsi" in plot_df.columns:
        ax3.plot(ohlc["date_num"], plot_df["rsi"].values, color="blue", linewidth=1.0)
        ax3.axhline(y=70, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
        ax3.axhline(y=30, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
        ax3.fill_between(ohlc["date_num"], 70, 100, alpha=0.08, color="red")
        ax3.fill_between(ohlc["date_num"], 0, 30, alpha=0.08, color="green")
        ax3.text(len(ohlc) - 1, 70, " OB 70", fontsize=7, va="bottom", ha="left", color="red", alpha=0.6)
        ax3.text(len(ohlc) - 1, 30, " OS 30", fontsize=7, va="top", ha="left", color="green", alpha=0.6)
        ax3.set_ylim(0, 100)
        ax3.set_ylabel("RSI", fontsize=8)
        ax3.grid(True, alpha=0.3)

    tick_positions = ohlc["date_num"].iloc[::max(1, len(ohlc) // 10)]
    tick_labels = [plot_df.index[int(i)].strftime("%m-%d") if isinstance(plot_df.index[int(i)], (pd.Timestamp, datetime)) else str(plot_df.index[int(i)])[:10]
                   for i in tick_positions]
    ax3.set_xticks(tick_positions)
    ax3.set_xticklabels(tick_labels, rotation=0, fontsize=8)
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)

    today_str = plot_df.index[-1].strftime("%Y-%m-%d") if isinstance(plot_df.index[-1], (pd.Timestamp, datetime)) else str(plot_df.index[-1])[:10]
    fig.suptitle(f"{label} — K-line ({today_str})", fontsize=15, fontweight="normal", y=0.96)

    return fig


def draw(df, indicators, symbol="563360", name=None, days=90, output_name=None):
    fig = build_figure(df, symbol=symbol, name=name, days=days)

    today_str = df.index[-1].strftime("%Y-%m-%d") if isinstance(df.index[-1], (datetime,)) else str(df.index[-1])[:10]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = output_name or f"chart_{today_str}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  K线图已保存: {filepath}")
    return filepath
