"""政府资金战略方向层的 Streamlit 页面。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from .catalog import CANDIDATE_BY_ID
from .reviews import (
    REVIEW_PATH,
    load_policy_reviews,
    review_direction,
    review_evidence,
)
from .strategy import build_policy_snapshot


STATUS_ICON = {
    "待整理": "◇",
    "Codex已核验": "◐",
    "正式生效": "✓",
    "已驳回": "×",
}


def _industry_names(ids: list[str]) -> str:
    return "、".join(CANDIDATE_BY_ID[item]["name"] for item in ids)


def _render_directions(snapshot: dict) -> None:
    st.subheader("年度方向")
    formal, draft, pending = st.columns(3)
    formal.metric("正式方向", len(snapshot["formal_directions"]))
    draft.metric("候选草案", len(snapshot["directions"]) - len(snapshot["formal_directions"]))
    pending.metric("待确认政策证据", snapshot["pending_confirmation_count"])
    st.caption("只保留本轮最接近入选条件的3个方向；后台35项候选目录不在日常页面展开。")

    for direction in snapshot["directions"]:
        with st.container(border=True):
            st.markdown(f"### {direction['name']}　`{direction['status']}`")
            st.write(direction["reason"])
            st.caption(f"资金阶段：{direction['funding_stage']}")
            st.caption(direction["coverage"]["display"])
            st.caption(
                f"落地覆盖{direction['coverage']['landed_jurisdiction_count']}个省级辖区；"
                f"{direction['coverage']['not_found_count']}地本轮未见强证据，"
                f"{direction['coverage']['unsearched_count']}地未检索；"
                "两类情况都不能据此作负面判断。"
            )
            st.caption(f"移出条件：{direction['removal_condition']}")


def _required_evidence_ready(direction: dict, evidence: list[dict]) -> bool:
    statuses = {item["id"]: item["status"] for item in evidence}
    return all(
        statuses.get(evidence_id) == "正式生效"
        for evidence_id in direction["required_evidence_ids"]
    )


def _render_etf_matches(snapshot: dict, review_path: str | Path) -> None:
    st.subheader("ETF匹配")
    st.caption("主选优先看方向纯度和交易基础，备选只在主选异常时替代；这里不构成买入建议。")

    for direction in snapshot["directions"]:
        main = direction["main_etf"]
        backup = direction.get("backup_etfs", [])
        with st.container(border=True):
            st.markdown(f"#### {direction['name']} · {direction['status']}")
            main_column, backup_column = st.columns(2)
            with main_column:
                st.markdown(f"**主选：{main['name']}（{main['symbol']}）**")
                st.write(main["index"])
                st.caption(main["reason"])
                st.markdown(f"[查看基金官方资料]({main['source_url']})")
            with backup_column:
                if backup:
                    item = backup[0]
                    st.markdown(f"**备选：{item['name']}（{item['symbol']}）**")
                    st.write(item["index"])
                    st.caption(item["reason"])
                    st.markdown(f"[查看基金官方资料]({item['source_url']})")
                else:
                    st.markdown("**暂无合格备选**")

            st.caption(
                f"ETF核验日期：{direction['etf_verified_on']} · 版本：{direction['selection_version']}"
            )
            evidence_ready = _required_evidence_ready(direction, snapshot["evidence"])
            local_execution_ready = direction["coverage"]["passes_local_execution"]
            if direction["etf_review_stale"]:
                st.warning("ETF资料已超过90天，重新核验前不能转为正式方向。")
            elif not evidence_ready:
                st.caption("先完成所需政策证据确认，再确认方向与ETF。")
            elif not local_execution_ready:
                st.caption("地方证据覆盖和落地门槛尚未满足，当前ETF映射只能保持草案。")
            else:
                st.caption("确认前请先展开地方覆盖明细；本次确认同时锁定当前地方证据版本和ETF版本。")

            if st.button(
                "确认方向、地方证据与ETF",
                key=f"policy_direction_confirm_{direction['id']}",
                disabled=(
                    (not evidence_ready)
                    or (not local_execution_ready)
                    or direction["etf_review_stale"]
                ),
                use_container_width=True,
            ):
                review_direction(
                    direction["id"],
                    direction["selection_version"],
                    "confirmed",
                    date.today().isoformat(),
                    coverage_version=direction["coverage"]["version"],
                    path=review_path,
                )
                st.rerun()


def _render_review_queue(snapshot: dict, review_path: str | Path) -> None:
    st.subheader("政策证据审核")
    st.caption("只有正式生效的证据能支持年度方向；确认的是原文和归类，不是买入决定。")

    with st.expander("查看地方覆盖明细", expanded=False):
        st.caption(
            "强证据只包括预算拨款、基金正式设立或出资、项目获批/开工/投产、"
            "采购中标或签约、正式重大项目清单。已查未见不等于当地没有产业。"
        )
        for direction in snapshot["directions"]:
            coverage = direction["coverage"]
            st.markdown(f"#### {direction['name']} · {coverage['display']}")
            for record in coverage["records"]:
                source_url = record.get("source_url")
                source = record.get("source", "来源待补")
                source_label = (
                    f"[来源：{source}]({source_url})" if source_url else f"来源：{source}"
                )
                st.markdown(
                    f"- **{record['region']} · {record['status']}**："
                    f"{record['summary']}  {source_label}"
                )

    with st.expander(
        f"展开审核队列 · 待确认{snapshot['pending_confirmation_count']}条",
        expanded=False,
    ):
        for evidence in snapshot["evidence"]:
            status = evidence["status"]
            with st.expander(f"{STATUS_ICON[status]} {evidence['title']} · {status}"):
                st.markdown(f"> {evidence['quote']}")
                st.markdown(
                    f"**对应产业：** {_industry_names(evidence['industries'])}  \n"
                    f"**证据类型：** {evidence['evidence_type']}  \n"
                    f"**原文定位：** {evidence['locator']}"
                )
                st.markdown(f"[打开官方来源]({evidence['source_url']})")
                st.caption(f"本地原件：{evidence['local_path']}")
                note = st.text_input(
                    "审核备注（可选）",
                    key=f"policy_note_{evidence['id']}",
                    placeholder="例如：行业归类需要缩窄",
                )
                confirm, reject = st.columns(2)
                if confirm.button(
                    "确认这条证据",
                    key=f"policy_confirm_{evidence['id']}",
                    use_container_width=True,
                ):
                    review_evidence(
                        evidence["id"],
                        "confirmed",
                        date.today().isoformat(),
                        note=note,
                        path=review_path,
                    )
                    st.rerun()
                if reject.button(
                    "驳回或退回修正",
                    key=f"policy_reject_{evidence['id']}",
                    use_container_width=True,
                ):
                    review_evidence(
                        evidence["id"],
                        "rejected",
                        date.today().isoformat(),
                        note=note,
                        path=review_path,
                    )
                    st.rerun()


def render_policy_strategy(review_path: str | Path = REVIEW_PATH) -> None:
    reviews = load_policy_reviews(review_path)
    snapshot = build_policy_snapshot(reviews)

    st.title("战略方向")
    st.caption("政策定方向，RSI只负责等待合适位置")
    if snapshot["formal_directions"]:
        st.success(f"当前已有{len(snapshot['formal_directions'])}个正式战略方向。")
    else:
        st.info("年度战略白名单尚未发布。当前3个方向均为草案，等待政策证据和ETF映射双确认。")

    _render_directions(snapshot)
    _render_etf_matches(snapshot, review_path)
    _render_review_queue(snapshot, review_path)
