"""产业 RS 排名页面：国家政策支持的产业 ETF 按相对强度排序。

来源：docs/2026省级政府工作报告细读/第五批收官与全国初筛总结.md
      docs/产业兑现报告/2026-八方向横向总评与第一版战略方向建议.md
"""
from __future__ import annotations

import streamlit as st

from dashboard import build_relative_strength_for_symbol


# === 报告推荐：通过 ETF 纯度+利润+定价三重审核 ===
_RECOMMENDED: list[tuple[str, str, str]] = [
    ("561380", "电网设备", "第一梯队"),
    ("159663", "高端装备/机床", "第一梯队"),
    ("516150", "稀土", "第一梯队"),
    ("560860", "工业有色", "第一梯队"),
    ("512400", "有色金属", "第一梯队"),
    ("159995", "芯片/集成电路", "第二梯队"),
    ("159819", "AI 算力", "第二梯队"),
    ("159755", "动力电池", "第二梯队"),
    ("512630", "卫星互联网", "特色候选"),
    ("159570", "港股创新药", "特色候选"),
]

# === 主题观察：报告判定 ETF 成分不纯/利润未过/定价偏高，但政策方向真实 ===
_WATCH: list[tuple[str, str, str]] = [
    ("562500", "机器人", "ETF不纯"),
    ("159665", "半导体设备", "已含在芯片内"),
    ("515250", "智能汽车", "成分混杂"),
    ("516090", "储能", "无纯ETF"),
    ("159883", "医疗器械", "利润未过"),
]

# 合并后统一排序
_ALL = _RECOMMENDED + _WATCH


def render_sector_rs():
    st.title("产业RS排名")
    st.caption(
        "按 RS 趋势方向排序（上升 > 走平 > 下降），同趋势内按 52 周涨幅排。"
        "RS 趋势基于 30 周均线方向，RS 变动基于 52 周比较——Weinstein 体系。"
        "仅作产业动量参考，不构成买卖建议。"
    )

    results_rec = []
    results_watch = []
    missing = []

    for symbol, name, tier in _RECOMMENDED:
        rs = build_relative_strength_for_symbol(symbol)
        if rs is None:
            missing.append((symbol, name, tier))
            continue
        results_rec.append({
            "name": name, "symbol": symbol, "tier": tier,
            "rs_trend": rs["rs_trend"], "rs_change_pct": rs["rs_change_pct"],
            "benchmark_name": rs["benchmark_name"], "note": rs["note"],
            "recommended": True,
        })

    for symbol, name, reason in _WATCH:
        rs = build_relative_strength_for_symbol(symbol)
        if rs is None:
            missing.append((symbol, name, reason))
            continue
        results_watch.append({
            "name": name, "symbol": symbol, "tier": f"主题观察 · {reason}",
            "rs_trend": rs["rs_trend"], "rs_change_pct": rs["rs_change_pct"],
            "benchmark_name": rs["benchmark_name"], "note": rs["note"],
            "recommended": False,
        })

    all_results = results_rec + results_watch
    _trend_order = {"上升": 0, "走平": 1, "下降": 2}
    all_results.sort(key=lambda x: (_trend_order.get(x["rs_trend"], 9), -x["rs_change_pct"]))

    if not all_results:
        st.info("所有产业 ETF 暂无足够价格数据，请先更新缓存。")
        return

    for item in all_results:
        trend = item["rs_trend"]
        trend_color = {"上升": "#27ae60", "下降": "#e74c3c", "走平": "#95a5a6"}.get(trend, "#95a5a6")
        trend_label = {"上升": "↗ 上升", "下降": "↘ 下降", "走平": "→ 走平"}.get(trend, "")
        with st.container(border=True):
            watch_mark = " `[观察]`" if not item["recommended"] else ""
            st.markdown(
                f"### {watch_mark}"
                f"<span style='color:{trend_color};font-weight:bold;font-size:1.1em'>{trend_label}</span> "
                f"{item['name']}（{item['symbol']}） `{item['tier']}`",
                unsafe_allow_html=True,
            )
            st.caption(item["note"])
            st.caption(f"基准：{item['benchmark_name']}")

    if results_watch:
        st.caption(
            "`[观察]` 标注项为报告判定 ETF 成分不纯/利润未过/定价偏高的方向。"
            "RS 仅反映主题热度，不构成买入建议。详见产业兑现报告。"
        )

    if missing:
        with st.expander(f"数据不足（{len(missing)} 个）", expanded=False):
            for symbol, name, _ in missing:
                st.caption(f"{name}（{symbol}）：cache 无数据")
