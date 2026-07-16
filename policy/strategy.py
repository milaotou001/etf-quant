"""从已核验证据和人工 ETF 映射构建年度战略快照。"""

from __future__ import annotations

from datetime import date, datetime

from .catalog import POLICY_CANDIDATES
from .coverage import get_direction_coverage
from .evidence import INITIAL_EVIDENCE
from .reviews import load_policy_reviews, resolve_evidence_status


DRAFT_DIRECTIONS = (
    {
        "id": "integrated-circuits",
        "name": "集成电路",
        "reason": "同时进入十五五关键核心技术攻坚名单和2026年新兴支柱产业。",
        "funding_stage": "国家战略与年度部署已明确；地方扩产与项目证据已形成多地交叉验证。",
        "required_evidence_ids": ["national-15-hard-tech", "report-2026-pillars"],
        "removal_condition": "国家部署降级，或ETF无法继续提供足够纯度和流动性。",
        "selection_version": "2026-07-16-v1",
        "etf_verified_on": "2026-07-16",
        "main_etf": {
            "symbol": "512480",
            "name": "半导体ETF国联安",
            "index": "中证全指半导体产品与设备指数",
            "reason": "覆盖半导体产品与设备，方向匹配直接；2025年末规模约201.65亿元，流动性基础充足。",
            "source_url": "https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-01-22/512480_20260122_IWNM.pdf",
        },
        "backup_etfs": [
            {
                "symbol": "159995",
                "name": "芯片ETF",
                "index": "国证半导体芯片指数",
                "reason": "芯片暴露更集中，规模和交易基础充足；与达达现有持仓一致，作为可用备选。",
                "source_url": "https://www.chinaamc.com/fund/159995/index.shtml",
            }
        ],
    },
    {
        "id": "artificial-intelligence",
        "name": "人工智能",
        "reason": "十五五列入科技战略部署，2026年政府工作报告要求商业化、规模化应用。",
        "funding_stage": "国家战略与年度应用部署已明确；地方算力、中试基地和应用场景已形成多地落地。",
        "required_evidence_ids": ["national-15-ai-strategy", "report-2026-ai-plus"],
        "removal_condition": "年度政策不再加码，或指数成分与人工智能产业链明显偏离。",
        "selection_version": "2026-07-16-v1",
        "etf_verified_on": "2026-07-16",
        "main_etf": {
            "symbol": "159819",
            "name": "人工智能ETF易方达",
            "index": "中证人工智能主题指数",
            "reason": "直接跟踪人工智能主题指数；2026年一季度末规模约221.41亿元，且为现有持仓。",
            "source_url": "https://cdn.efunds.com.cn/owch/data/bulletin/20260422/%E6%98%93%E6%96%B9%E8%BE%BE%E4%B8%AD%E8%AF%81%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD%E4%B8%BB%E9%A2%98%E4%BA%A4%E6%98%93%E5%9E%8B%E5%BC%80%E6%94%BE%E5%BC%8F%E6%8C%87%E6%95%B0%E8%AF%81%E5%88%B8%E6%8A%95%E8%B5%84%E5%9F%BA%E9%87%912026%E5%B9%B4%E7%AC%AC1%E5%AD%A3%E5%BA%A6%E6%8A%A5%E5%91%8A.pdf?from=org",
        },
        "backup_etfs": [
            {
                "symbol": "515070",
                "name": "人工智能ETF华夏",
                "index": "中证人工智能主题指数",
                "reason": "跟踪同一指数，2026年核验时规模约97.56亿元，可在主选流动性异常时替代。",
                "source_url": "https://www.chinaamc.com/fund/515070/index.shtml",
            }
        ],
    },
    {
        "id": "biopharma",
        "name": "生物医药",
        "reason": "十五五提出生物制造攻坚，2026年政府工作报告将生物医药列为新兴支柱产业。",
        "funding_stage": "国家方向与地方创新药、产业园证据已形成呼应；生物制造与生物医药口径仍需持续区分。",
        "required_evidence_ids": ["national-15-hard-tech", "report-2026-pillars"],
        "removal_condition": "后续材料不能证明口径连续，或产业ETF与政策支持环节错配。",
        "selection_version": "2026-07-16-v1",
        "etf_verified_on": "2026-07-16",
        "main_etf": {
            "symbol": "512290",
            "name": "生物医药ETF国泰",
            "index": "中证生物医药指数",
            "reason": "覆盖疫苗、血制品、检测和生物创新药；2026年一季度末规模约36.85亿元。",
            "source_url": "https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-04-22/512290_20260422_KD9A.pdf",
        },
        "backup_etfs": [
            {
                "symbol": "159859",
                "name": "生物医药ETF天弘",
                "index": "国证生物医药指数",
                "reason": "提供另一套生物医药指数口径，规模与成交基础可接受，作为备选而非重复主选。",
                "source_url": "https://cdn-thweb.tianhongjijin.com.cn/fundnotice/%E5%A4%A9%E5%BC%98%E5%9F%BA%E9%87%91%E7%AE%A1%E7%90%86%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8%E5%85%B3%E4%BA%8E%E6%97%97%E4%B8%8B%E9%83%A8%E5%88%86%E6%B7%B1%E4%BA%A4%E6%89%80ETF%E5%8F%98%E6%9B%B4%E5%9C%BA%E5%86%85%E7%AE%80%E7%A7%B0%E7%9A%84%E5%85%AC%E5%91%8A.pdf",
            }
        ],
    },
)


def is_etf_review_stale(verified_on: str, as_of: date | None = None) -> bool:
    review_date = datetime.strptime(verified_on, "%Y-%m-%d").date()
    return ((as_of or date.today()) - review_date).days > 90


def resolve_direction_status(
    direction: dict,
    reviews: dict,
    evidence: list[dict],
    coverage: dict | None = None,
) -> str:
    evidence_status = {item["id"]: item["status"] for item in evidence}
    evidence_ready = all(
        evidence_status.get(evidence_id) == "正式生效"
        for evidence_id in direction["required_evidence_ids"]
    )
    direction_review = reviews.get("direction_reviews", {}).get(direction["id"], {})
    coverage_state = coverage or get_direction_coverage(direction["id"])
    selection_ready = (
        direction_review.get("decision") == "confirmed"
        and direction_review.get("selection_version") == direction["selection_version"]
        and direction_review.get("coverage_version") == coverage_state.get("version")
    )
    local_execution_ready = coverage_state["passes_local_execution"]
    return (
        "正式"
        if evidence_ready and selection_ready and local_execution_ready
        else "草案"
    )


def build_policy_snapshot(reviews: dict | None = None, as_of: date | None = None) -> dict:
    review_state = reviews if reviews is not None else load_policy_reviews()
    evidence = [
        {**item, "status": resolve_evidence_status(item, review_state)}
        for item in INITIAL_EVIDENCE
    ]
    status_counts = {
        status: sum(item["status"] == status for item in evidence)
        for status in ("待整理", "Codex已核验", "正式生效", "已驳回")
    }
    directions = []
    for item in DRAFT_DIRECTIONS:
        direction = {**item}
        direction["coverage"] = get_direction_coverage(direction["id"])
        direction["status"] = resolve_direction_status(
            direction,
            review_state,
            evidence,
            direction["coverage"],
        )
        direction["etf_review_stale"] = is_etf_review_stale(direction["etf_verified_on"], as_of)
        directions.append(direction)
    formal_directions = [item for item in directions if item["status"] == "正式"]
    return {
        "candidate_count": len(POLICY_CANDIDATES),
        "legacy_candidate_count": 34,
        "corrected_candidate_count": 1,
        "evidence": evidence,
        "codex_verified_count": sum(item.get("codex_verified", False) for item in evidence),
        "pending_confirmation_count": status_counts["Codex已核验"],
        "effective_evidence_count": status_counts["正式生效"],
        "rejected_evidence_count": status_counts["已驳回"],
        "directions": directions,
        "formal_directions": formal_directions,
    }
