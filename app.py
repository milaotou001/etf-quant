"""本地 ETF 决策辅助：主页面只保留状态与图表，其余内容按需查看。"""
from datetime import date
import hashlib
import html
import os
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
from financial_report_check import build_financial_report_check
from instruments import get_instrument, list_instruments
from journal import create_entry, list_entries, review
from mobile_view import (
    MobileViewConfigError,
    is_mobile_read_only,
    load_mobile_plan,
    mobile_page_options,
    plan_price_symbols,
    primary_metric_order,
)
from policy.page import render_policy_strategy
from portfolio_review import (
    ACCOUNT_BASE_AMOUNT,
    ATTRIBUTION_START,
    COMPARATOR_BY_SYMBOL,
    DRAWDOWN_BUDGET,
    build_attribution_rows,
    build_cluster_exposure,
    run_pressure_replay,
)
from purchase_plan import (
    EXECUTION_DEVIATION,
    EXECUTION_ON_PLAN,
    STATUS_PENDING,
    STATUS_PLANNED,
    STATUS_RECONCILED,
    TARGETS,
    build_position_progress,
    calculate_open_quantity,
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
      .plan-cell-readonly { border: 1px solid #e4e7ec; border-left: 4px solid #1b6b5c; border-radius: .55rem; padding: .75rem .85rem; margin: .45rem 0; background: #fff; line-height: 1.45; }
      @media (max-width: 700px) {
        .block-container { max-width: 100%; padding: 1rem .75rem 3rem; }
        .asset-head, .progress-meta, .progress-foot { display: grid; grid-template-columns: 1fr; gap: .25rem; }
        .asset-target, .progress-number { text-align: left; }
        [data-testid="stMetric"] { padding: .55rem .65rem; }
        .plan-intro { padding: .8rem .9rem; }
        .cash-grid { grid-template-columns: 1fr; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    MOBILE_READ_ONLY = is_mobile_read_only(os.environ)
except MobileViewConfigError as exc:
    st.error(f"手机只读配置错误：{exc}")
    st.stop()


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
    read_only: bool = False,
) -> None:
    latest = df.iloc[-1]
    analysis = build_market_analysis(df)
    campaign = build_campaign_observation(df, spec)
    st.title(spec.name)
    st.caption(_data_caption(df))
    if df.attrs.get("data_note"):
        st.caption(f"数据说明：{df.attrs['data_note']}")

    metric_columns = dict(zip(primary_metric_order(read_only), st.columns(4)))
    with metric_columns["rsi"]:
        st.metric("RSI (14)", _fmt_number(latest.get("rsi"), 0))
    with metric_columns["price"]:
        st.metric("收盘", _fmt_number(latest["close"], 4), _fmt_number(latest.get("chg"), 1, "—") + "%")
    with metric_columns["macd"]:
        hist_col = next((c for c in df.columns if c.startswith("MACDh_")), "")
        st.metric("MACD HIST", _fmt_number(latest.get(hist_col), 4))
    with metric_columns["rvol"]:
        st.metric("成交额 RVOL", _fmt_number(latest.get("rvol"), 2, "不可用"))

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
        execution_label = st.radio(
            "执行方式",
            ["按原计划", "偏离计划"],
            horizontal=True,
            key=f"execution-type-{item_id}",
        )
        deviation_reason = ""
        if execution_label == "偏离计划":
            deviation_reason = st.text_input(
                "偏离原因（可选）",
                key=f"deviation-reason-{item_id}",
            )
        st.caption("确认后先按计划金额计入进度；上传新对账单后会补全真实成交。")
        confirm, cancel = st.columns(2)
        with confirm:
            if st.button("确认已买入", type="primary", width="stretch"):
                updated = mark_item_bought(
                    plan,
                    item_id,
                    confirmed_date.isoformat(),
                    execution_type=(
                        EXECUTION_DEVIATION
                        if execution_label == "偏离计划"
                        else EXECUTION_ON_PLAN
                    ),
                    deviation_reason=deviation_reason or None,
                )
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
        if item.get("execution_type") == EXECUTION_DEVIATION:
            reason = item.get("deviation_reason") or "未填写原因"
            st.caption(f"执行记录：偏离计划 · {reason}")
        elif item.get("execution_type") == EXECUTION_ON_PLAN:
            st.caption("执行记录：按原计划")
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


def _render_asset_plan_row(symbol: str, asset: dict, read_only: bool = False) -> None:
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
        if read_only:
            for item in items:
                label = html.escape(_plan_cell_label(symbol, item)).replace("\n", "<br>")
                st.markdown(
                    f"<div class='plan-cell-readonly'>{label}</div>",
                    unsafe_allow_html=True,
                )
            return

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


def _render_financial_report_check() -> None:
    check = build_financial_report_check(date.today())
    with st.container(border=True):
        st.markdown("### 财报检查")
        if check["status"] in {"today", "due"}:
            st.warning(check["headline"])
        else:
            st.info(check["headline"])

        timeline, windows = st.columns([3, 2])
        with timeline:
            st.markdown("**三个固定检查点**")
            for checkpoint in check["checkpoints"]:
                checkpoint_date = checkpoint["date"]
                marker = "●" if checkpoint_date == check["next_date"] else "○"
                st.caption(
                    f"{marker} {checkpoint_date.month}月{checkpoint_date.day}日 · "
                    f"{checkpoint['label']}：{checkpoint['action']}"
                )
        with windows:
            st.markdown("**最晚披露窗口**")
            for note in check["disclosure_notes"]:
                st.caption(f"• {note}")

        st.info(check["candidate_note"])
        st.caption("检查日期不是买入日期；公告出来后仍要综合利润、现金流、订单或产品收入判断。")


def _render_purchase_plan(
    plan: dict,
    trade_cache: dict,
    latest_prices: dict,
    snapshot: dict,
    read_only: bool = False,
) -> None:
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

    _render_financial_report_check()

    st.subheader("计划与实际成交")
    if read_only:
        st.caption("手机只读快照 · ◇ 计划中　◐ 已买入·待对账　✓ 已对账")
    else:
        st.caption("◇ 计划中　◐ 已买入·待对账　✓ 已对账。每个格子本身就是操作入口。")
    for symbol in TARGETS:
        _render_asset_plan_row(symbol, plan["assets"][symbol], read_only=read_only)

    if read_only:
        st.caption("计划变化后需重新同步只读快照；手机端不会修改本机计划。")
        return

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


def _review_price_frames(symbols: set[str], refresh_token: int) -> tuple[dict, list[str]]:
    frames = {}
    unavailable = []
    for review_symbol in sorted(symbols):
        try:
            frames[review_symbol] = load_data(
                symbol=review_symbol,
                force_refresh=refresh_token > 0,
            )
        except Exception:
            unavailable.append(review_symbol)
    return frames, unavailable


def _render_portfolio_review(plan: dict, trade_cache: dict, refresh_token: int) -> None:
    st.title("组合风险概览")
    st.caption(
        f"正式交易贡献从 {ATTRIBUTION_START.strftime('%Y-%m-%d')} 开始；此前持仓只用于风险模拟。"
    )

    pending_by_symbol = {
        symbol: sum(
            float(item.get("planned_amount") or 0)
            for item in asset.get("items", [])
            if item.get("status") == STATUS_PENDING and not item.get("needs_confirmation")
        )
        for symbol, asset in plan.get("assets", {}).items()
    }
    held_symbols = {
        symbol
        for symbol, entries in trade_cache.items()
        if calculate_open_quantity(entries) > 0
    }
    risk_symbols = held_symbols | {
        symbol for symbol, amount in pending_by_symbol.items() if amount > 0
    }
    attributed_symbols = set()
    for symbol, asset in plan.get("assets", {}).items():
        if any(
            item.get("status") == STATUS_RECONCILED
            and (item.get("actual") or {}).get("date")
            and pd.Timestamp(item["actual"]["date"]) >= ATTRIBUTION_START
            for item in asset.get("items", [])
        ):
            attributed_symbols.add(symbol)
    comparison_symbols = {
        COMPARATOR_BY_SYMBOL[symbol]
        for symbol in attributed_symbols
        if symbol in COMPARATOR_BY_SYMBOL
    }
    frames, unavailable = _review_price_frames(
        risk_symbols | attributed_symbols | comparison_symbols | {"510300"},
        refresh_token,
    )

    position_values = {}
    for review_symbol in risk_symbols:
        frame = frames.get(review_symbol)
        latest_price = float(frame.iloc[-1]["close"]) if frame is not None and not frame.empty else None
        open_quantity = calculate_open_quantity(trade_cache.get(review_symbol, []))
        market_value = open_quantity * latest_price if latest_price is not None else 0.0
        position_values[review_symbol] = market_value + pending_by_symbol.get(review_symbol, 0.0)

    progress = {
        symbol: {
            "display_value": value,
            "pending_estimate": pending_by_symbol.get(symbol, 0.0),
        }
        for symbol, value in position_values.items()
    }
    attribution_tab, risk_tab = st.tabs(["交易贡献", "组合风险"])

    with attribution_tab:
        st.caption(
            "这里复盘计划交易的方向、ETF选择和执行时点，不等于账户总收益；"
            "正式起算日后的数据会随着对账单逐步增加。"
        )
        rows = build_attribution_rows(plan, frames)
        if not rows:
            st.info("正式起算日之后暂时没有已对账的计划交易，先继续积累数据。")
        else:
            table = pd.DataFrame(
                {
                    "日期": [row["actual_date"] for row in rows],
                    "标的": [row["name"] for row in rows],
                    "执行": ["偏离计划" if row["execution_type"] == EXECUTION_DEVIATION else "按计划" for row in rows],
                    "方向超额": [row["direction_excess_pct"] for row in rows],
                    "ETF选择": [row["etf_selection_pct"] for row in rows],
                    "择时金额": [row["timing_effect_amount"] for row in rows],
                }
            )
            st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                column_config={
                    "方向超额": st.column_config.NumberColumn(format="%+.2f%%"),
                    "ETF选择": st.column_config.NumberColumn(format="%+.2f%%"),
                    "择时金额": st.column_config.NumberColumn(format="¥%+.0f"),
                },
            )
            st.caption("四层记分卡彼此独立，不强行相加为账户总收益；暂无可靠对照时显示为空。")

    with risk_tab:
        replay = run_pressure_replay(frames, position_values)
        total_exposure = sum(position_values.values())
        positive_loss = sum(
            max(value, 0.0) for value in replay["cluster_losses"].values()
        )
        main_cluster, main_loss = (None, 0.0)
        if replay["cluster_losses"]:
            main_cluster, main_loss = max(
                replay["cluster_losses"].items(),
                key=lambda item: item[1],
            )
        main_cluster_share = (
            main_loss / positive_loss * 100
            if main_loss > 0 and positive_loss > 0
            else 0.0
        )

        st.subheader("先看结论")
        st.info(
            "这是历史压力模拟，不是实际亏损，也不是预测："
            f"把现在的持仓金额放进过去 {replay['sample_days']} 个共同交易日，"
            "寻找最差的一段走势。"
        )
        exposure, pressure, budget = st.columns(3)
        exposure.metric(
            "现在投入的风险资产",
            _money(total_exposure),
            help=f"约占账户 {total_exposure / ACCOUNT_BASE_AMOUNT * 100:.1f}%；不含现金。",
        )
        pressure.metric("历史最差模拟回撤", _money(replay["pressure_loss"]))
        budget.metric(
            "回撤预警线已用",
            f"{replay['budget_usage_pct']:.0f}%",
            help=f"预警线 {_money(DRAWDOWN_BUDGET)}，约占账户15%。",
        )
        if replay["over_budget"]:
            st.error(f"历史模拟回撤已超过 {_money(DRAWDOWN_BUDGET)} 预警线。")
        elif replay["budget_usage_pct"] >= 80:
            st.caption(
                f"目前还没有超过 {_money(DRAWDOWN_BUDGET)} 预警线，但已经接近。"
            )
        if main_cluster and main_loss > 0:
            st.warning(
                f"主要风险来源：{main_cluster}，约贡献 {_money(main_loss)} 的模拟损失，"
                f"占本次正向损失约 {main_cluster_share:.0f}%。"
            )
        if replay["sample_days"]:
            st.caption(
                f"最差区间：{replay['peak_date']} 至 {replay['trough_date']}。"
            )

        cluster_rows = build_cluster_exposure(progress)
        if cluster_rows:
            st.subheader("各类资产的模拟影响")
            st.caption(
                "“现在约有”包含已持有金额和已标记但尚未对账的买入；"
                "负数表示这类资产在该段行情中起了缓冲作用。"
            )
            cluster_losses = replay["cluster_losses"]
            st.dataframe(
                pd.DataFrame(
                    {
                        "资产篮子": [row["cluster"] for row in cluster_rows],
                        "现在约有": [row["value"] for row in cluster_rows],
                        "占账户": [row["value"] / ACCOUNT_BASE_AMOUNT * 100 for row in cluster_rows],
                        "历史最差模拟影响": [cluster_losses.get(row["cluster"], 0.0) for row in cluster_rows],
                        "备注": [
                            "；".join(
                                part
                                for part in [
                                    f"待对账约 {_money(row['pending_estimate'])}"
                                    if row["pending_estimate"]
                                    else None,
                                    "主要风险来源" if row["cluster"] == main_cluster and main_loss > 0 else None,
                                    "该段行情起缓冲作用"
                                    if cluster_losses.get(row["cluster"], 0.0) < 0
                                    else None,
                                ]
                                if part
                            ) or "—"
                            for row in cluster_rows
                        ],
                    }
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "现在约有": st.column_config.NumberColumn(format="¥%.0f"),
                    "占账户": st.column_config.NumberColumn(format="%.1f%%"),
                    "历史最差模拟影响": st.column_config.NumberColumn(format="¥%+.0f"),
                },
            )
        if unavailable:
            st.caption(f"行情暂不可用：{'、'.join(unavailable)}；相关标的不进入本次压力回放。")


if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = 0

specs = list_instruments(include_experimental=True)
spec_by_symbol = {spec.symbol: spec for spec in specs}
with st.sidebar:
    st.markdown("## 决策辅助")
    symbol = st.selectbox("标的", list(spec_by_symbol), format_func=lambda key: f"{spec_by_symbol[key].display_tier} · {spec_by_symbol[key].name}")
    page = st.radio("页面", mobile_page_options(MOBILE_READ_ONLY))
    if st.button("刷新当前数据"):
        st.session_state.refresh_token += 1
    show_trades = False
    uploaded_statement = None
    if not MOBILE_READ_ONLY:
        show_trades = st.checkbox("显示个人交易记录")
        uploaded_statement = st.file_uploader(
            "更新电子对账单（可选）",
            type=["xlsx"],
            disabled=page == "战略方向" or (not show_trades and page not in {"半年买入计划", "组合复盘"}),
        )
        st.caption("解析后的记录会跨页面和重启保留；新对账单更新交易与现金，不会覆盖买入计划。")
    else:
        st.caption("手机只读模式 · 不上传对账单，不修改计划")

spec = spec_by_symbol[symbol]
if page == "战略方向":
    render_policy_strategy()
    st.stop()

trade_cache = {}
if not MOBILE_READ_ONLY:
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
    if MOBILE_READ_ONLY:
        try:
            display_plan = load_mobile_plan(os.environ)
        except MobileViewConfigError as exc:
            st.error(f"手机计划快照不可用：{exc}")
            st.stop()
        display_trade_cache = {}
        account_snapshot = {}
    else:
        plan = load_purchase_plan()
        display_plan = reconcile_purchase_plan(plan, trade_cache)
        if display_plan != plan:
            save_purchase_plan(display_plan)
        display_trade_cache = trade_cache
        account_snapshot = load_account_snapshot()

    latest_prices = {}
    unavailable = []
    for core_symbol in plan_price_symbols(MOBILE_READ_ONLY, TARGETS):
        try:
            core_df = load_prepared_data(core_symbol, st.session_state.refresh_token)
            latest_prices[core_symbol] = float(core_df.iloc[-1]["close"])
        except Exception:
            latest_prices[core_symbol] = None
            unavailable.append(TARGETS[core_symbol]["name"])
    if unavailable:
        st.caption(f"暂未读取行情：{'、'.join(unavailable)}；计划快照仍可查看。")
    _render_purchase_plan(
        display_plan,
        display_trade_cache,
        latest_prices,
        account_snapshot,
        read_only=MOBILE_READ_ONLY,
    )
elif page == "组合复盘":
    plan = load_purchase_plan()
    reconciled_plan = reconcile_purchase_plan(plan, trade_cache)
    if reconciled_plan != plan:
        save_purchase_plan(reconciled_plan)
    _render_portfolio_review(reconciled_plan, trade_cache, st.session_state.refresh_token)
else:
    try:
        df = load_prepared_data(symbol, st.session_state.refresh_token)
    except Exception as exc:
        heading = "本次未取得行情数据" if MOBILE_READ_ONLY else "数据加载失败"
        st.error(f"{heading}：{exc}")
        st.stop()

    if page == "状态与图表":
        _render_main(
            df,
            spec,
            trades,
            st.session_state.refresh_token,
            read_only=MOBILE_READ_ONLY,
        )
    elif page == "复盘日志":
        _render_journal(df, spec)
    elif page == "策略回测":
        _render_backtest(df, spec)
    else:
        _render_rules(spec)
