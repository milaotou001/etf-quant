"""本地 ETF 决策辅助：主页面只保留状态与图表，其余内容按需查看。"""
import hashlib
import pandas as pd
import streamlit as st

from backtest import run_campaign_backtest, simulate_campaigns
from chart import build_figure, resolve_chart_start
from dashboard import (
    _reminders,
    build_campaign_observation,
    build_market_analysis,
    compute_indicators,
)
from data import load_data
from instruments import get_instrument, list_instruments
from journal import create_entry, list_entries, review
from trades import load_trade_cache, update_trade_cache


st.set_page_config(page_title="ETF 决策辅助", page_icon="◒", layout="wide")
st.markdown(
    """
    <style>
      .block-container { max-width: 1320px; padding-top: 2rem; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      [data-testid="stMetric"] { border-left: 3px solid #1b6b5c; padding-left: 0.8rem; }
      .status-card { border-left: 5px solid #1b6b5c; background: #f4f8f6; padding: 1rem 1.15rem; border-radius: .4rem; }
      .muted { color: #667085; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def load_prepared_data(symbol: str, refresh_token: int) -> pd.DataFrame:
    spec = get_instrument(symbol)
    return compute_indicators(load_data(symbol=symbol, force_refresh=refresh_token > 0), spec)


def _fmt_number(value, digits: int = 2, fallback: str = "—") -> str:
    if value is None or pd.isna(value):
        return fallback
    return f"{value:.{digits}f}"


def _data_caption(df: pd.DataFrame) -> str:
    latest_date = df.index[-1].strftime("%Y-%m-%d")
    source = df.attrs.get("source", "未知")
    origin = df.attrs.get("origin_source")
    origin_note = f"（原始来源：{origin}）" if origin and origin not in {source, "本地缓存"} else ""
    quality = "真实成交额" if df.attrs.get("amount_verified") else "成交额未验证"
    freshness = {"current": "已刷新", "cached": "缓存读取"}.get(df.attrs.get("data_freshness"), "状态未知")
    return f"数据日 {latest_date} · {source}{origin_note} · {freshness} · {quality}"


def _render_main(df: pd.DataFrame, spec, trades: list[dict] | None) -> None:
    latest = df.iloc[-1]
    analysis = build_market_analysis(df)
    campaign = build_campaign_observation(df, spec)
    st.title(spec.name)
    st.caption(_data_caption(df))
    if df.attrs.get("data_note"):
        st.caption(f"数据说明：{df.attrs['data_note']}")

    price, rsi, macd, rvol = st.columns(4)
    with price:
        st.metric("收盘", _fmt_number(latest["close"], 4), _fmt_number(latest.get("chg"), 1, "—") + "%")
    with rsi:
        st.metric("RSI (14)", _fmt_number(latest.get("rsi"), 0))
    with macd:
        hist_col = next((c for c in df.columns if c.startswith("MACDh_")), "")
        st.metric("MACD HIST", _fmt_number(latest.get(hist_col), 4))
    with rvol:
        value = latest.get("rvol")
        st.metric("成交额 RVOL", _fmt_number(value, 2, "不可用"))

    st.markdown(
        f"<div class='status-card'><b>{analysis['state_label']}</b><br>{analysis['one_liner']}</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 2])
    with left:
        st.subheader("下一步观察")
        for item in analysis["next_watch"][:3]:
            st.write(f"• {item}")
    with right:
        st.subheader("战役状态")
        if campaign is None:
            st.caption("实验观察区：不提供策略战役判断。")
        else:
            st.write(f"**{campaign['phase']}**")
            st.caption(campaign["summary"])
            st.caption(" · ".join(f"{'✓' if item['ok'] else '○'} {item['label']}" for item in campaign["conditions"]))

    st.subheader("图表")
    range_label = st.radio("图表区间", ["近 6 个月", "近 1 年", "近 2 年", "从诞生至今"], horizontal=True, label_visibility="collapsed")
    start_date = resolve_chart_start(df.index, range_label)
    fig = build_figure(df, symbol=spec.symbol, name=spec.name, start_date=start_date, end_date=df.index[-1], trades=trades)
    st.pyplot(fig, clear_figure=True)

    with st.expander("查看详细观察与数据说明"):
        for index, (name, state, note) in enumerate(analysis["steps"], start=1):
            st.write(f"**{index}. {name} · {state}** — {note}")
        reminders = _reminders(latest, df, rsi_buy_threshold=spec.rsi_second_entry or 0)
        if reminders:
            st.markdown("**纪律提醒**")
            for item in reminders:
                st.caption(f"• {item}")
        if not spec.is_core:
            st.info("本标的是实验观察区：指标仅供查看，未验证 RSI 战役或回测规则。")


def _render_journal(df: pd.DataFrame, spec) -> None:
    st.title("复盘日志")
    if not spec.is_core:
        st.info("复盘日志当前只服务四只已验证的核心 ETF。")
        return
    create_tab, history_tab = st.tabs(["记录今天", "历史复盘"])
    with create_tab:
        st.caption("工具保存当天事实快照；达达只记录判断、等待条件和计划。")
        with st.form("journal_entry"):
            view = st.selectbox("我的判断", ["偏强", "中性", "偏弱"])
            conditions = st.text_area("我在等什么条件（最多三条）", placeholder="例如：RSI 回到 40 且 MACD 改善")
            plan = st.text_area("我的计划", placeholder="例如：不操作，等待右侧确认后再复核")
            submitted = st.form_submit_button("保存今日复盘")
        if submitted:
            path = create_entry(spec.symbol, df, view, conditions, plan)
            st.success(f"已保存：{path}")
    with history_tab:
        entries = list_entries(spec.symbol)
        if not entries:
            st.caption("还没有可复盘的记录。")
            return
        selected_date, selected_path = st.selectbox("选择记录", entries, format_func=lambda item: item[0])
        with open(selected_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())
        if st.button("更新事后回顾", help="只更新这一篇记录的复盘区块，不会重复追加"):
            with st.spinner("读取后续行情并更新复盘..."):
                review(spec.symbol, selected_date)
            st.success("复盘已更新，请重新选择该日期查看。")
            st.rerun()


def _render_backtest(df: pd.DataFrame, spec) -> None:
    st.title("策略回测")
    if not spec.supports_backtest:
        st.info("实验观察区不提供策略回测，避免借用核心 ETF 的历史结论。")
        return
    st.caption("统计完整战役：第一观察位 → 第二观察位 → RSI 回到确认线且 MACD 改善。等权计算三段成本，不包含卖出策略。")
    summary = run_campaign_backtest(df, spec)
    st.dataframe(summary, hide_index=True, width="stretch")
    campaigns = simulate_campaigns(df, spec)
    rows = []
    for campaign in campaigns:
        entries = {entry["stage"]: entry for entry in campaign["entries"]}
        rows.append({
            "状态": "完整" if campaign["status"] == "complete" else "仍在等待",
            "第一观察位": entries["第一观察位"]["date"].strftime("%Y-%m-%d"),
            "第二观察位": entries.get("第二观察位", {}).get("date", pd.NaT),
            "右侧确认": entries.get("右侧确认", {}).get("date", pd.NaT),
        })
    if rows:
        st.subheader("历史战役")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("回测衡量规则在历史中的表现，不构成收益承诺或自动交易指令。")


def _render_rules(spec) -> None:
    st.title("策略规则")
    st.markdown("### 策略宪法")
    st.write("机器整理事实，人做最终判断；回撤优先于盈利目标；低频、无杠杆、不追涨、不用自动下单。")
    if spec.is_core:
        st.markdown("### 当前标的的三段战役")
        st.write(f"1. 第一观察位：RSI ≤ {spec.rsi_first_entry}")
        st.write(f"2. 第二观察位：RSI ≤ {spec.rsi_second_entry}")
        st.write(f"3. 右侧确认：RSI ≥ {spec.rsi_confirmation} 且 MACD 动能改善")
        st.caption("总预算、批次和条件应在战役开始前锁定；未确认的现金继续等待。")
    else:
        st.info("实验观察区只看数据与图表，不提供可执行策略规则。")


if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = 0

specs = list_instruments(include_experimental=True)
spec_by_symbol = {spec.symbol: spec for spec in specs}
with st.sidebar:
    st.markdown("## 决策辅助")
    symbol = st.selectbox("标的", list(spec_by_symbol), format_func=lambda key: f"{'核心' if spec_by_symbol[key].is_core else '实验'} · {spec_by_symbol[key].name}")
    page = st.radio("页面", ["状态与图表", "复盘日志", "策略回测", "策略规则"])
    if st.button("刷新当前数据"):
        st.session_state.refresh_token += 1
    show_trades = st.checkbox("显示个人交易记录")
    uploaded_statement = st.file_uploader("更新电子对账单（可选）", type=["xlsx"], disabled=not show_trades)
    st.caption("已保存的解析记录会跨页面和重启保留；上传新文件会替换旧缓存。")

spec = spec_by_symbol[symbol]
try:
    df = load_prepared_data(symbol, st.session_state.refresh_token)
except Exception as exc:
    st.error(f"数据加载失败：{exc}")
    st.stop()

trade_cache = load_trade_cache()
if uploaded_statement is not None:
    upload_hash = hashlib.sha256(uploaded_statement.getvalue()).hexdigest()
    if st.session_state.get("trade_upload_hash") != upload_hash:
        try:
            trade_cache = update_trade_cache(uploaded_statement)
            st.session_state.trade_upload_hash = upload_hash
            st.session_state.trade_cache_notice = "对账单已更新，已替换本机缓存。"
        except Exception as exc:
            st.warning(f"未能更新对账单：{exc}")
    else:
        trade_cache = load_trade_cache()

trades = trade_cache.get(symbol) if show_trades else None
if show_trades:
    st.sidebar.caption(f"本机已保存 {len(trade_cache)} 个标的的交易记录。")
    if st.session_state.get("trade_cache_notice"):
        st.sidebar.success(st.session_state.trade_cache_notice)

if page == "状态与图表":
    _render_main(df, spec, trades)
elif page == "复盘日志":
    _render_journal(df, spec)
elif page == "策略回测":
    _render_backtest(df, spec)
else:
    _render_rules(spec)
