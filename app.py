"""Streamlit 图形化面板 — 交互式切换标的/日期"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data import load_data
from dashboard import compute_indicators, get_indicator_row, _market_state, _reminders, _col
from chart import build_figure
from backtest import run_backtest

st.set_page_config(page_title="ETF 决策辅助", page_icon="📊", layout="wide")

symbol_cache = st.session_state.get("symbol", "563360")
force_cache = st.session_state.get("force", False)

df = load_data(symbol=symbol_cache, force_refresh=force_cache)
df = compute_indicators(df)
st.session_state["force"] = False

# ── 侧边栏 ──
with st.sidebar:
    st.title("ETF 决策辅助")

    symbol = st.selectbox(
        "标的", ["563360", "510300"],
        index=0 if symbol_cache == "563360" else 1,
        format_func=lambda x: {"563360": "563360 A500 ETF",
                               "510300": "510300 沪深300 ETF"}.get(x, x),
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
        st.markdown(f"""
        **买入**：RSI(14) < 35，距上次信号 > 30天 → 投现金池的 **{buy_fraction}**
        **卖出**：从买入后最高点回落 **15%** → 止损卖出
        **不卖**：RSI > 70 不是卖出理由（动量效应）
        **现金池**：30万 + 每年注入 3万，只在 RSI<35 时出手
        """)

    st.divider()
    st.caption("持仓信息（可选）")
    has_position = st.checkbox("我有持仓")
    entry_price = None
    entry_date = None
    if has_position:
        entry_price = st.number_input("买入价", value=1.40, step=0.001, format="%.4f")
        entry_date = st.date_input("买入日期", value=datetime.now() - timedelta(days=7),
                                   max_value=datetime.now())

# ── 当前数据 ──
indicators = get_indicator_row(df)
latest = df.iloc[-1]
today_str = df.index[-1].strftime("%Y-%m-%d")

# ═══ 两个 Tab ═══
tab1, tab2 = st.tabs(["📊 决策面板", "📈 策略回溯"])

# ──────────── Tab 1: 决策面板 ────────────
with tab1:
    col1, col2, col3, col4, col5 = st.columns(5)
    verdict, summary = _market_state(latest, df)

    col1.metric("收盘价", f"{latest['close']:.4f}")
    col2.metric("涨跌幅", f"{latest['chg']:+.1f}%")
    col3.metric("RSI (14)", f"{latest['rsi']:.0f}",
                delta="黄金坑" if latest['rsi'] < 35 else ("超买" if latest['rsi'] > 70 else None),
                delta_color="off" if latest['rsi'] >= 35 and latest['rsi'] <= 70 else "normal")
    adx_col = _col(df, "ADX")
    adx_val = latest[adx_col] if adx_col else 0
    col4.metric("ADX (14)", f"{adx_val:.0f}",
                delta="趋势" if adx_val >= 25 else ("方向形成中" if adx_val >= 20 else None),
                delta_color="off")
    col5.metric("MA20", f"{latest['ma20']:.4f}")

    st.divider()
    if verdict == "便宜":
        st.success(f"**{summary}**")
        st.info(f">>> 黄金坑 — 投现金池的 {buy_fraction} <<<")
    elif verdict == "贵":
        st.warning(f"**{summary}**")
        st.info(">>> 偏贵 — 持有不动，不加仓（RSI>70后动量强，卖=踏空）<<<")
    else:
        st.info(f"**{summary}**  — 正常，不动")

    if has_position and entry_price and entry_date:
        pnl_pct = (latest["close"] / entry_price - 1) * 100
        stop_price = entry_price * 0.95
        dist_to_stop = (latest["close"] / stop_price - 1) * 100
        hold_days = (df.index[-1] - pd.to_datetime(entry_date)).days
        time_left = max(0, 7 - hold_days)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前盈亏", f"{pnl_pct:+.1f}%")
        c2.metric("止损线", f"{stop_price:.4f}", f"距当前 {dist_to_stop:+.1f}%")
        if time_left > 0:
            c3.metric("时间止损", f"剩余 {time_left} 天")
        else:
            c3.metric("时间止损", "已到期 ⚠")
        c4.metric("持有天数", str(hold_days))

    reminders = _reminders(latest, df, has_position=(has_position and entry_price is not None), buy_fraction=buy_fraction)
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
    st.caption("策略解读：定投为底 + RSI<35黄金坑投现金池1/3 + RSI>70不卖。不回测已证明：单纯择时跑不赢定投，但有大笔现金时RSI<35分批买入提升资金效率。")
