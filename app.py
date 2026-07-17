"""本地 ETF 决策辅助：主页面只保留状态与图表，其余内容按需查看。"""
from datetime import date
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
from policy.page import render_policy_strategy
from purchase_plan import (
    STATUS_PENDING,
    STATUS_PLANNED,
    STATUS_RECONCILED,
    TARGETS,
    build_position_progress,
    load_purchase_plan,
    mark_item_bought,
    plan_item_heading,
    reconcile_purchase_plan,
    save_purchase_plan,
    summarize_plan,
    undo_item_mark,
)
from trades import load_account_snapshot, load_trade_cache, update_trade_cache
from etf_shares import SHARE_OBSERVATION_ENABLED, load_share_observation


st.set_page_config(page_title="ETF 决策辅助", page_icon="◒", layout="wide")
st.markdown(
    """
    <style>
      .block-container { max-width: 1320px; padding-top: 2rem; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      [data-testid="stMetric"] { border-left: 3px solid #1b6b5c; padding-left: 0.8rem; }
      .status-card { border-left: 5px solid #1b6b5c; background: #f4f8f6; padding: 1rem 1.15rem; border-radius: .4rem; }
      .muted { color: #667085; font-size: .9rem; }
      .plan-intro { background: linear-gradient(105deg, #f7faf8 0%, #ffffff 75%); border: 1px solid #d9e5df; border-left: 6px solid #1b6b5c; padding: 1rem 1.2rem; border-radius: .65rem; margin: .25rem 0 1.2rem; }
      .plan-intro b { color: #143f37; font-size: 1.03rem; }
      .asset-head { display: flex; align-items: center; justify-content: space-between; gap: .8rem; margin-bottom: .35rem; }
      .asset-chip { display: inline-flex; align-items: center; gap: .55rem; font-weight: 720; font-size: 1.02rem; }
      .asset-dot { width: .7rem; height: .7rem; border-radius: 50%; display: inline-block; }
      .asset-target { color: #667085; font-size: .86rem; }
      .progress-card { border: 1px solid #e4e7ec; border-radius: .7rem; padding: .85rem 1rem; margin-bottom: .7rem; background: #fff; }
      .progress-meta { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: .5rem; }
      .progress-title { font-weight: 700; }
      .progress-number { color: #475467; font-size: .88rem; text-align: right; }
      .progress-track { height: .72rem; width: 100%; border-radius: 999px; overflow: hidden; }
      .progress-fill { height: 100%; border-radius: 999px; }
      .progress-foot { display: flex; justify-content: space-between; color: #667085; font-size: .8rem; margin-top: .4rem; }
      .cash-card { border: 1px solid #e4e7ec; border-left: 5px solid #667085; border-radius: .7rem; padding: .9rem 1rem; background: #fafafa; }
      .cash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      .cash-label { color: #667085; font-size: .82rem; }
      .cash-value { color: #101828; font-weight: 720; font-size: 1.08rem; margin-top: .15rem; }
      @media (max-width: 700px) { .cash-grid { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def load_prepared_data(symbol: str, refresh_token: int) -> pd.DataFrame:
    spec = get_instrument(symbol)
    return compute_indicators(load_data(symbol=symbol, force_refresh=refresh_token > 0), spec)


@st.cache_data(ttl=300, show_spinner=False)
def load_prepared_share_observation(
    symbol: str,
    trading_dates: tuple[str, ...],
    refresh_token: int,
) -> dict | None:
    return load_share_observation(
        symbol,
        pd.DatetimeIndex(trading_dates),
        force_refresh=refresh_token > 0,
    )


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


def _render_main(
    df: pd.DataFrame,
    spec,
    trades: list[dict] | None,
    refresh_token: int = 0,
) -> None:
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

    if SHARE_OBSERVATION_ENABLED and spec.is_core:
        trading_dates = tuple(df.index[-25:].strftime("%Y-%m-%d"))
        try:
            with st.spinner("读取上交所 ETF 份额..."):
                share_observation = load_prepared_share_observation(
                    spec.symbol,
                    trading_dates,
                    refresh_token,
                )
        except Exception as exc:
            share_observation = None
            st.caption(f"ETF 份额观察暂不可用：{exc}")

        if share_observation is not None:
            st.subheader("ETF 份额观察（不参与战役）")

            def _fmt_change(value):
                return "数据不足" if value is None or pd.isna(value) else f"{value:+.2f}%"

            share, daily, five_day, twenty_day = st.columns(4)
            with share:
                st.metric("最新份额", f"{share_observation['latest_shares'] / 1e8:.2f} 亿份")
            with daily:
                st.metric("当日变化", _fmt_change(share_observation.get("daily_change_pct")))
            with five_day:
                st.metric("近 5 日变化", _fmt_change(share_observation.get("change_5d_pct")))
            with twenty_day:
                st.metric("近 20 日变化", _fmt_change(share_observation.get("change_20d_pct")))

            st.write(f"**{share_observation['state']}**")
            st.caption(share_observation["explanation"])
            latest_share_date = pd.Timestamp(share_observation["latest_date"]).strftime("%Y-%m-%d")
            freshness = "已刷新" if share_observation.get("freshness") == "current" else "缓存读取"
            lag_note = (
                f" · 落后行情 {share_observation['lag_days']} 天"
                if share_observation.get("lag_days", 0) > 0
                else ""
            )
            st.caption(
                f"{share_observation['source']} · 数据日 {latest_share_date} · {freshness}{lag_note}"
            )

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


def _money(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "待读取"
    return f"¥{value:,.{digits}f}"


def _find_plan_item(plan: dict, item_id: str) -> tuple[dict, dict]:
    for asset in plan.get("assets", {}).values():
        for item in asset.get("items", []):
            if item.get("id") == item_id:
                return asset, item
    raise ValueError(f"未找到计划项：{item_id}")


def _plan_cell_label(symbol: str, item: dict) -> str:
    heading = plan_item_heading(symbol, item)

    if item.get("status") == STATUS_RECONCILED and item.get("actual"):
        actual = item["actual"]
        actual_dates = actual.get("dates") or [actual.get("date")]
        date_text = "+".join(value[5:] for value in actual_dates if value)
        return (
            f"✓ {heading}\n\n"
            f"{date_text} · {actual['qty']:,}股 @ {actual['price']:.3f}\n\n"
            f"实付 {_money(actual['amount'])}"
        )
    if item.get("status") == STATUS_PENDING:
        split_count = len(item.get("confirmed_dates") or [])
        status = "⚠ 需确认" if item.get("needs_confirmation") else (
            f"已买入 · 分{split_count}次待对账" if split_count > 1 else "已买入 · 待对账"
        )
        return f"◐ {heading}\n\n{_money(item['planned_amount'])}\n\n{status}"
    return f"◇ {heading}\n\n{_money(item['planned_amount'])}\n\n计划中"


def _clear_purchase_dialog() -> None:
    st.session_state.pop("purchase_plan_item_id", None)


@st.dialog("更新买入计划", width="small", on_dismiss=_clear_purchase_dialog)
def _purchase_item_dialog(plan: dict, item_id: str) -> None:
    asset, item = _find_plan_item(plan, item_id)
    st.markdown(f"### {asset['name']} · 第 {item['number']} 笔")
    st.write(f"计划金额：**{_money(item['planned_amount'], 2)}**")

    if item.get("status") == STATUS_PLANNED:
        confirmed_date = st.date_input("实际买入日期", value=date.today(), key=f"confirm-date-{item_id}")
        st.caption("确认后先按计划金额计入进度；上传新对账单后会补全真实成交。")
        confirm, cancel = st.columns(2)
        with confirm:
            if st.button("确认已买入", type="primary", width="stretch"):
                updated = mark_item_bought(plan, item_id, confirmed_date.isoformat())
                save_purchase_plan(updated)
                _clear_purchase_dialog()
                st.rerun()
        with cancel:
            if st.button("取消", width="stretch"):
                _clear_purchase_dialog()
                st.rerun()
        return

    if item.get("status") == STATUS_PENDING:
        dates = item.get("confirmed_dates") or [item.get("confirmed_date")]
        dates = [value for value in dates if value]
        date_text = "、".join(dates) if dates else "未记录日期"
        if len(dates) > 1:
            st.info(f"已标记为分{len(dates)}次买入（{date_text}），上传对账单后会合并到这一笔。")
        else:
            st.info(f"已于 {date_text} 标记买入，目前等待对账单补全。")
        if item.get("needs_confirmation"):
            st.warning("同日存在多笔可能成交，系统没有自动归类。")
        undo, close = st.columns(2)
        with undo:
            if st.button("撤销标记", width="stretch"):
                updated = undo_item_mark(plan, item_id)
                save_purchase_plan(updated)
                _clear_purchase_dialog()
                st.rerun()
        with close:
            if st.button("关闭", width="stretch"):
                _clear_purchase_dialog()
                st.rerun()


def _render_asset_plan_row(symbol: str, asset: dict) -> None:
    with st.container(border=True):
        color = asset["color"]
        target_text = f"理想仓位 {_money(asset['target'])}"
        if asset.get("reserved_amount"):
            target_text += f" · 后续预留 {_money(asset['reserved_amount'])}"
        st.markdown(
            f"<div class='asset-head'><div class='asset-chip'>"
            f"<span class='asset-dot' style='background:{color}'></span>{asset['name']}"
            f"</div><div class='asset-target'>{target_text}</div></div>",
            unsafe_allow_html=True,
        )
        if asset.get("plan_note"):
            st.caption(asset["plan_note"])
        items = asset.get("items", [])
        for start in range(0, len(items), 6):
            batch = items[start:start + 6]
            columns = st.columns(len(batch), gap="small")
            for column, item in zip(columns, batch):
                with column:
                    clicked = st.button(
                        _plan_cell_label(symbol, item),
                        key=f"plan-cell-{item['id']}",
                        disabled=item.get("status") == STATUS_RECONCILED,
                        width="stretch",
                        help="点击标记或撤销" if item.get("status") != STATUS_RECONCILED else "已由对账单补全",
                    )
                    if clicked:
                        st.session_state.purchase_plan_item_id = item["id"]


def _render_position_progress(progress: dict) -> None:
    st.subheader("总进度")
    st.caption("每条长度固定为理想仓位；深色为已拥有（含待对账暂估），浅色为实时缺口。缺口只观察，不改计划。")
    for symbol in TARGETS:
        item = progress[symbol]
        percent = min(max(item["ratio"], 0.0), 1.0) * 100
        market_text = _money(item["market_value"]) if item["price_available"] else "行情暂不可用"
        pending_text = f" · 待对账暂估 {_money(item['pending_estimate'])}" if item["pending_estimate"] else ""
        state_text = f"超配 {_money(item['display_value'] - item['target'])}" if item["is_overweight"] else f"缺口 {_money(item['gap'])}"
        st.markdown(
            f"<div class='progress-card'>"
            f"<div class='progress-meta'><div class='progress-title' style='color:{item['color']}'>{item['name']}</div>"
            f"<div class='progress-number'>当前 {_money(item['display_value'])} / 理想 {_money(item['target'])}</div></div>"
            f"<div class='progress-track' style='background:{item['soft_color']}'>"
            f"<div class='progress-fill' style='width:{percent:.2f}%;background:{item['color']}'></div></div>"
            f"<div class='progress-foot'><span>真实市值 {market_text}{pending_text}</span><span>{state_text}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_purchase_plan(plan: dict, trade_cache: dict, latest_prices: dict, snapshot: dict) -> None:
    st.title("半年买入计划")
    st.markdown(
        "<div class='plan-intro'><b>固定计划，逐笔确认</b><br>"
        "<span class='muted'>宽基目标已重分配；行业仓只列当前一轮，后续预留不计入待买金额。</span></div>",
        unsafe_allow_html=True,
    )
    summary = summarize_plan(plan)
    total, confirmed, remaining, count = st.columns(4)
    total.metric("半年计划", _money(summary["planned_total"]))
    confirmed.metric("已确认", _money(summary["confirmed_amount"]))
    remaining.metric("计划剩余", _money(summary["remaining_amount"]))
    count.metric("已完成笔数", f"{summary['confirmed_count']} / {summary['total_count']}")

    st.subheader("计划与实际成交")
    st.caption("◇ 计划中　◐ 已买入·待对账　✓ 已对账。每个格子本身就是操作入口。")
    for symbol in TARGETS:
        _render_asset_plan_row(symbol, plan["assets"][symbol])

    selected_item_id = st.session_state.get("purchase_plan_item_id")
    if selected_item_id:
        _purchase_item_dialog(plan, selected_item_id)

    progress = build_position_progress(plan, trade_cache, latest_prices)
    _render_position_progress(progress)

    cash_balance = snapshot.get("cash_balance")
    cash_date = snapshot.get("cash_date") or "暂无对账单日期"
    st.markdown(
        f"<div class='cash-card'><div class='asset-head'><div class='asset-chip'>现金 / 其他</div>"
        f"<div class='asset-target'>理想 30%</div></div><div class='cash-grid'>"
        f"<div><div class='cash-label'>理想金额</div><div class='cash-value'>{_money(plan.get('cash_target', 85_500.0))}</div></div>"
        f"<div><div class='cash-label'>最近对账单资金余额 · {cash_date}</div>"
        f"<div class='cash-value'>{_money(cash_balance)}</div></div></div></div>",
        unsafe_allow_html=True,
    )


if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = 0

specs = list_instruments(include_experimental=True)
spec_by_symbol = {spec.symbol: spec for spec in specs}
with st.sidebar:
    st.markdown("## 决策辅助")
    symbol = st.selectbox("标的", list(spec_by_symbol), format_func=lambda key: f"{spec_by_symbol[key].display_tier} · {spec_by_symbol[key].name}")
    page = st.radio("页面", ["状态与图表", "复盘日志", "策略回测", "策略规则", "半年买入计划", "战略方向"])
    if st.button("刷新当前数据"):
        st.session_state.refresh_token += 1
    show_trades = st.checkbox("显示个人交易记录")
    uploaded_statement = st.file_uploader(
        "更新电子对账单（可选）",
        type=["xlsx"],
        disabled=page == "战略方向" or (not show_trades and page != "半年买入计划"),
    )
    st.caption("解析后的记录会跨页面和重启保留；新对账单更新交易与现金，不会覆盖买入计划。")

spec = spec_by_symbol[symbol]
if page == "战略方向":
    render_policy_strategy()
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

if page == "半年买入计划":
    plan = load_purchase_plan()
    reconciled_plan = reconcile_purchase_plan(plan, trade_cache)
    if reconciled_plan != plan:
        save_purchase_plan(reconciled_plan)
    latest_prices = {}
    unavailable = []
    for core_symbol in TARGETS:
        try:
            core_df = load_prepared_data(core_symbol, st.session_state.refresh_token)
            latest_prices[core_symbol] = float(core_df.iloc[-1]["close"])
        except Exception:
            latest_prices[core_symbol] = None
            unavailable.append(TARGETS[core_symbol]["name"])
    if unavailable:
        st.caption(f"暂未读取行情：{'、'.join(unavailable)}；计划格仍可正常标记。")
    _render_purchase_plan(reconciled_plan, trade_cache, latest_prices, load_account_snapshot())
else:
    try:
        df = load_prepared_data(symbol, st.session_state.refresh_token)
    except Exception as exc:
        st.error(f"数据加载失败：{exc}")
        st.stop()

    if page == "状态与图表":
        _render_main(df, spec, trades, st.session_state.refresh_token)
    elif page == "复盘日志":
        _render_journal(df, spec)
    elif page == "策略回测":
        _render_backtest(df, spec)
    else:
        _render_rules(spec)
