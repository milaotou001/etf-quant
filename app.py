"""Streamlit 图形化面板 — 交互式切换标的/日期"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data import load_data
from dashboard import compute_indicators, _market_state, _reminders
from chart import build_figure
from backtest import run_backtest

ETF_NAMES = {"563360": "563360 A500 ETF",
             "510300": "510300 沪深300 ETF",
             "518880": "518880 黄金ETF",
             "588000": "588000 科创50 ETF"}
# 股票ETF RSI<35，黄金 RSI<30
RSI_THRESHOLDS = {"563360": 35, "510300": 35, "518880": 30, "588000": 30}

st.set_page_config(page_title="ETF 决策辅助", page_icon="📊", layout="wide")

symbol_cache = st.session_state.get("symbol", "563360")
force_cache = st.session_state.get("force", False)

df = load_data(symbol=symbol_cache, force_refresh=force_cache)
df = compute_indicators(df)
st.session_state["force"] = False

rsi_buy = RSI_THRESHOLDS.get(symbol_cache, 35)

# ── 侧边栏 ──
with st.sidebar:
    st.title("ETF 决策辅助")

    symbol = st.selectbox(
        "标的", ["563360", "510300", "518880", "588000"],
        index=({"563360": 0, "510300": 1, "518880": 2, "588000": 3}).get(symbol_cache, 0),
        format_func=lambda x: ETF_NAMES.get(x, x),
        key="symbol")

    data_years = sorted(set(df.index.year))
    min_year, max_year = data_years[0], data_years[-1]
    year_range = st.select_slider(
        "图表区间",
        options=data_years,
        value=(max(max_year - 1, min_year), max_year))
    start_date = pd.Timestamp(f'{year_range[0]}-01-01')
    end_date = pd.Timestamp(f'{year_range[1]}-12-31')

    if st.button("强制刷新数据"):
        st.session_state["force"] = True
        st.rerun()

    st.divider()
    st.caption("市场模式")
    market_mode = st.radio(
        "当前判断",
        ["bull", "bear"],
        format_func=lambda x: "牛市/震荡 → 投 1/3" if x == "bull" else "熊市 → 投 1/5",
        key="market_mode")
    buy_fraction = "1/3" if market_mode == "bull" else "1/5"

    st.divider()
    with st.expander("📋 策略规则", expanded=False):
        st.markdown("**买 入**")
        st.markdown(f"RSI(14) &lt; {rsi_buy} · 距上次信号 &gt; 30 天 · 投现金池 **{buy_fraction}**")
        st.markdown("**卖 出**")
        st.markdown("从买入后最高点回落 **15%** → 止损离场")
        st.markdown("**不 卖**")
        st.markdown("RSI &gt; 70 不是卖出理由（动量效应）")
        st.markdown("**现金池**")
        st.markdown(f"30 万 + 每年 3 万 · 只在 RSI &lt; {rsi_buy} 时出手")

# ── 当前数据 ──
latest = df.iloc[-1]
today_str = df.index[-1].strftime("%Y-%m-%d")

# ═══ 两个 Tab ═══
tab1, tab2 = st.tabs(["📊 决策面板", "📈 策略回溯"])

# ──────────── Tab 1: 决策面板 ────────────
with tab1:
    verdict, summary = _market_state(latest, df, rsi_buy_threshold=rsi_buy)

    st.divider()
    if verdict == "便宜":
        st.success(f"**{summary}**")
        st.info(f">>> 黄金坑 — 投现金池的 {buy_fraction} <<<")
    elif verdict == "贵":
        st.warning(f"**{summary}**")
        st.info(">>> 偏贵 — 持有不动，不加仓（RSI>70后动量强，卖=踏空）<<<")
    else:
        st.info(f"**{summary}**  — 正常，不动")

    reminders = _reminders(latest, df, has_position=False, buy_fraction=buy_fraction, rsi_buy_threshold=rsi_buy)
    if reminders:
        st.divider()
        st.subheader("纪律提醒")
        for r in reminders:
            st.warning(r)

    st.divider()
    plot_df = df.loc[start_date:end_date]
    plot_dates = plot_df.index.strftime("%Y-%m-%d")
    n_pts = len(plot_df)

    col_slider, _ = st.columns([5, 1])
    with col_slider:
        opts = list(range(n_pts))
        slider_val = st.select_slider(
            "拖动竖线", options=opts, value=n_pts - 1,
            format_func=lambda i: plot_dates[i] if i < len(plot_dates) else "",
            label_visibility="collapsed")

    fig = build_figure(df, symbol=symbol, start_date=start_date, end_date=end_date)
    for ax in fig.get_axes():
        ax.axvline(x=slider_val, color="#e74c3c", linewidth=1.2, alpha=0.8)

    st.pyplot(fig)

    selected_date = plot_dates[slider_val] if n_pts > 0 else today_str
    st.caption(f"{selected_date} | 区间: {year_range[0]}~{year_range[1]} | 代码: {symbol} | >>> 你怎么看？")

# ──────────── Tab 2: 策略回溯 ────────────
with tab2:
    st.subheader("止盈策略回测")
    st.caption("测试 RSI 超卖买入后，不同止盈方式的历史表现")

    buy_cond = st.radio("买入条件", ["rsi35", "rsi30", "rsi25"],
                        format_func=lambda x: "RSI < 35（黄金坑）" if x == "rsi35" else ("RSI < 30（超卖）" if x == "rsi30" else "RSI < 25（极端超卖）"),
                        horizontal=True)

    rdf, cond_label, signal_count = run_backtest(df, buy_condition=buy_cond)
    date_range = f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}"

    st.caption(f"数据: {date_range} | 买入条件: {cond_label} | 共 {signal_count} 次信号")

    st.dataframe(rdf, use_container_width=True, hide_index=True)

    st.divider()
    st.caption("策略解读：定投为底 + RSI黄金坑投现金池1/3 + RSI>70不卖。不回测已证明：单纯择时跑不赢定投，但有大笔现金时RSI低位分批买入提升资金效率。")
