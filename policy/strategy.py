"""从已核验证据和人工 ETF 映射构建年度战略快照。"""

from __future__ import annotations

from datetime import date, datetime

from .catalog import POLICY_CANDIDATES
from .coverage import get_direction_coverage
from .evidence import INITIAL_EVIDENCE
from .reviews import load_policy_reviews, resolve_evidence_status


DRAFT_DIRECTIONS = (
    {
        "id": "innovative-drugs",
        "name": "创新药商业化",
        "reason": "2026政府工作报告生物医药新兴支柱产业；H1产业证据四个卫星中最强：龙头利润（恒瑞/百济）+第二梯队放量（信达+50%/康方+51%）+BD出海半年~1,100亿美元+双目录支付体系运转（1,225万人次使用）。",
        "funding_stage": "产业利润已经兑现，支付准入持续改善；RSI 56.3 当前不在介入区间，等待回落。",
        "required_evidence_ids": ["national-15-hard-tech", "report-2026-pillars"],
        "removal_condition": "医保大幅降价导致盈利质量恶化，或 ETF 成分偏离创新药主线。",
        "selection_version": "2026-07-20-v2",
        "etf_verified_on": "2026-07-20",
        "priority": 1,
        "status_note": "第一顺位卫星 · 等RSI回落",
        "main_etf": {
            "symbol": "159570",
            "name": "港股创新药ETF汇添富",
            "index": "国证港股通创新药指数",
            "reason": "剔除CXO，创新药权重~85%，纯度优于A股生物医药ETF；信达、康方为前两大权重，直接承接创新药商业化利润。2025年末规模约242亿元。",
            "source_url": "https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-04-22/159570_20260422_KD9A.pdf",
        },
        "backup_etfs": [
            {
                "symbol": "159567",
                "name": "港股创新药ETF广发",
                "index": "国证港股通创新药指数",
                "reason": "跟踪同一指数，可在主选流动性异常时替代。",
                "source_url": "",
            }
        ],
    },
    {
        "id": "power-grid",
        "name": "电网设备",
        "reason": "十五五关键核心技术攻坚覆盖先进材料与高端仪器；H1全线兑现：亨通+87%~121%、中天+50%~60%、思源营收+27%。特高压+新能源并网+出海三轮驱动。",
        "funding_stage": "国网投资持续高位，H1龙头企业利润加速兑现；RSI 27.0 已介入首笔。",
        "required_evidence_ids": ["national-15-hard-tech"],
        "removal_condition": "电网投资大幅缩减，或龙头企业订单/利润连续两季低于预期。",
        "selection_version": "2026-07-20-v1",
        "etf_verified_on": "2026-07-20",
        "priority": 2,
        "status_note": "已介入首笔 · 两轮结构",
        "main_etf": {
            "symbol": "561380",
            "name": "电网设备ETF富国",
            "index": "中证电网设备主题指数",
            "reason": "直接覆盖电网设备产业链，成分股聚焦特高压、输变电、配网设备；拆分后流动性改善。",
            "source_url": "",
        },
        "backup_etfs": [
            {
                "symbol": "159326",
                "name": "电网设备ETF华夏",
                "index": "中证电网设备主题指数",
                "reason": "跟踪同一指数，流动性备选。",
                "source_url": "",
            }
        ],
    },
    {
        "id": "rare-earth",
        "name": "稀土产业链",
        "reason": "十五五先进材料攻坚方向；H1全面爆发：北方稀土+113%~121%、金力永磁扣非+57%~83%、宁波韵升扣非+137%~216%。供给约束+新能源/风电/机器人需求共振。",
        "funding_stage": "开采指标受国家配额管控，下游永磁材料需求持续增长；RSI 25.7 已介入首笔。",
        "required_evidence_ids": ["national-15-hard-tech"],
        "removal_condition": "国家释放过量开采指标，或新能源/风电需求大幅不及预期。",
        "selection_version": "2026-07-20-v1",
        "etf_verified_on": "2026-07-20",
        "priority": 3,
        "status_note": "已介入首笔 · 单轮结构",
        "main_etf": {
            "symbol": "516150",
            "name": "稀土ETF富国",
            "index": "中证稀土产业指数",
            "reason": "覆盖稀土开采、冶炼和永磁材料全链条；成分股纯度高于综合有色ETF。",
            "source_url": "",
        },
        "backup_etfs": [
            {
                "symbol": "516780",
                "name": "稀土ETF华泰柏瑞",
                "index": "中证稀土产业指数",
                "reason": "跟踪同一指数，可作备选。",
                "source_url": "",
            }
        ],
    },
    {
        "id": "industrial-metals",
        "name": "工业有色",
        "reason": "有色行业利润全市场第一（+117.1%），铜铝供给偏紧叠加新能源/电网金属需求增长；剔除黄金后的工业金属纯度高（铜铝~51%）。",
        "funding_stage": "全球铜矿资本开支不足+新能源金属需求增长；RSI 35.0未到极端低位，等RSI~30。",
        "required_evidence_ids": [],
        "removal_condition": "全球铜铝需求大幅萎缩或供给超预期释放，或行业利润增速连续两季明显放缓。",
        "selection_version": "2026-07-20-v1",
        "etf_verified_on": "2026-07-20",
        "priority": 4,
        "status_note": "等待RSI~30 · 两轮结构",
        "main_etf": {
            "symbol": "560860",
            "name": "工业有色ETF万家中证",
            "index": "中证工业有色金属主题指数",
            "reason": "剔除黄金，聚焦铜铝铅锌等工业金属；铜铝权重~51%，直接受益于供给偏紧和新能源需求。",
            "source_url": "",
        },
        "backup_etfs": [
            {
                "symbol": "512400",
                "name": "有色金属ETF南方",
                "index": "中证申万有色金属指数",
                "reason": "覆盖更广的有色金属指数，含贵金属成分，纯度和弹性略低。",
                "source_url": "",
            }
        ],
    },
    {
        "id": "hang-seng-tech",
        "name": "恒生科技",
        "reason": "离岸成长暴露，与A股持仓不重叠；港股科技龙头盈利修复+AI+平台经济政策改善。",
        "funding_stage": "港股估值受美联储政策和地缘政治双重影响；RSI需到30-35才介入。",
        "required_evidence_ids": [],
        "removal_condition": "港股系统性风险恶化，或科技龙头基本面大幅转弱。",
        "selection_version": "2026-07-20-v1",
        "etf_verified_on": "2026-07-20",
        "priority": 5,
        "status_note": "等待RSI 30-35 · 两轮结构",
        "main_etf": {
            "symbol": "513180",
            "name": "恒生科技ETF华夏",
            "index": "恒生科技指数",
            "reason": "直接跟踪恒生科技指数，覆盖互联网平台+科技硬件+新能源汽车；规模和流动性充足。",
            "source_url": "",
        },
        "backup_etfs": [],
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
