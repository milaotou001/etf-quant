"""地方政策材料覆盖台账：区分未检索、未发现、落地与明确收缩。"""

from __future__ import annotations

import math


COVERAGE_STATUS_UNSEARCHED = "未检索"
COVERAGE_STATUS_NOT_FOUND = "已检索未发现"
COVERAGE_STATUS_LANDED = "发现落地"
COVERAGE_STATUS_CONTRACTED = "明确收缩"

VALID_COVERAGE_STATUSES = {
    COVERAGE_STATUS_UNSEARCHED,
    COVERAGE_STATUS_NOT_FOUND,
    COVERAGE_STATUS_LANDED,
    COVERAGE_STATUS_CONTRACTED,
}

TARGET_REGIONS = (
    "北京市",
    "上海市",
    "南京市",
    "合肥市",
    "广州市",
    "杭州市",
    "武汉市",
    "浙江省",
    "深圳市",
    "苏州市",
)

REGION_JURISDICTION = {
    "北京市": "北京市",
    "上海市": "上海市",
    "南京市": "江苏省",
    "合肥市": "安徽省",
    "广州市": "广东省",
    "杭州市": "浙江省",
    "武汉市": "湖北省",
    "浙江省": "浙江省",
    "深圳市": "广东省",
    "苏州市": "江苏省",
}

REPORT_ROOT = (
    r"G:\达达项目资料库\03_AI软件项目\政府资金分析仪\政府报告资料\政府报告"
)

CHECKED_ON = "2026-07-16"
COVERAGE_VERSION = "2026-07-16-v2"

OFFICIAL_SOURCES = {
    "北京市": {
        "source": "2026年北京市政府工作报告",
        "source_url": "https://www.beijing.gov.cn/gongkai/jihua/zfgzbg/202602/t20260202_4483941.html",
    },
    "上海市": {
        "source": "上海市促进重点产业高质量发展行动方案",
        "source_url": "https://www.shanghai.gov.cn/tszczq-qtqj1/20260320/af611c9a8afb49f8ba1e7d0031bbde6b.html",
    },
    "南京市": {
        "source": "2026年南京市政府工作报告",
        "source_url": "https://www.nanjing.gov.cn/zt/jj2026njslh/xwjj/202602/t20260202_5785481.html",
    },
    "合肥市": {
        "source": "2026合肥市《政府工作报告》PDF.pdf",
        "source_path": REPORT_ROOT + r"\2026合肥市《政府工作报告》PDF.pdf",
    },
    "广州市": {
        "source": "2026年广州市政府工作报告",
        "source_url": "https://www.gz.gov.cn/zwgk/gzsrmzfgbn/2026/5/content/post_10695525.html",
    },
    "杭州市": {
        "source": "2026年杭州市政府工作报告",
        "source_url": "https://zfgb.hangzhou.gov.cn/148/102220263/t103220263024/530188.shtml",
    },
    "武汉市": {
        "source": "2026武汉市《政府工作报告》PDF.pdf",
        "source_path": REPORT_ROOT + r"\2026武汉市《政府工作报告》PDF.pdf",
    },
    "浙江省": {
        "source": "浙江社保科创基金首批专项基金签约",
        "source_url": "https://zjic.zj.gov.cn/ywdh/cyfz/202601/t20260119_23908962.shtml",
    },
    "深圳市": {
        "source": "2026年深圳市政府工作报告",
        "source_url": "https://www.sz.gov.cn/cn/xxgk/zfxxgj/zwdt/content/post_12650902.html",
    },
    "苏州市": {
        "source": "2026年苏州市政府工作报告",
        "source_url": "https://www.suzhou.gov.cn/szsrmzf/zfgzbg/202602/8c307d6f1a1c471987a9a79eb438ebb9.shtml",
    },
}

# 只记录达到“资金/基金/项目/采购/扩产”强证据标准的结果。
# “已检索未发现”仅表示本轮已核验来源中没有强证据，不代表当地没有该产业。
VERIFIED_RESULTS = {
    "北京市": {
        "integrated-circuits": ("扩产量产段", "明确推动集成电路重点项目扩产量产。"),
        "artificial-intelligence": ("高精尖产业段", "医疗、制造、科学等人工智能应用中试基地已落地，并继续建设国家级中试基地。"),
        "innovative-drugs": ("高精尖产业段", "34款创新药械获批，国际医药创新公园新引入8家跨国药企并继续建设。"),
    },
    "上海市": {
        "integrated-circuits": ("重点产业载体与签约项目", "行动方案明确集成电路产业载体，官方集中签约项目覆盖集成电路。"),
        "artificial-intelligence": ("重点产业载体与签约项目", "行动方案明确人工智能创新载体，官方集中签约项目覆盖人工智能。"),
        "innovative-drugs": ("重点产业载体与签约项目", "行动方案明确张江医药产业载体，官方集中签约项目覆盖生物医药。"),
    },
    "南京市": {
        "integrated-circuits": ("产业项目段", "华天江苏、芯德半导体等项目列入竣工投产安排。"),
        "artificial-intelligence": ("人工智能产业段", "部署人工智能生态街区、国际社区和2.1万P算力建设。"),
        "innovative-drugs": ("生物医药产业段", "已有一类创新药和三类器械成果，并安排年度产业资金与新品目标。"),
    },
    "合肥市": {
        "integrated-circuits": ("PDF第2、19页", "晶合四期加速落地，聚合微电子、晶镁半导体项目当年签约当年开工，并接续建设长鑫、晶合。"),
        "artificial-intelligence": ("PDF第3、21页", "飞星二号算力集群高效运营，国家人工智能应用中试基地（医疗）获批建设，综合算力突破30000P。"),
        "innovative-drugs": ("PDF第3页", "315个药品和二类以上医疗器械获批上市，大健康研究院入选国家首批生物制造中试名单。"),
    },
    "广州市": {
        "integrated-circuits": ("重大项目建设段", "粤芯四期列入重大项目建设，增芯一期安排增产增效。"),
        "artificial-intelligence": ("人工智能+段", "建设国家人工智能应用中试基地，并落地一批智算中心项目。"),
        "innovative-drugs": ("新兴未来产业段", "部署核医疗特色创新产业园和细胞治疗等产业化支撑。"),
    },
    "杭州市": {
        "integrated-circuits": None,
        "artificial-intelligence": ("人工智能创新发展段", "国家人工智能应用中试基地（医疗）已落户，首批6个产业生态创新空间完成布局。"),
        "innovative-drugs": ("2025年产业成果段", "6个品规杭产一类创新药获批上市，中国医药港继续作为产业地标建设。"),
    },
    "武汉市": {
        "integrated-circuits": ("PDF第2、13页", "长江存储三期、奕斯伟大硅片项目已开工，并继续推进武汉新芯三期建设。"),
        "artificial-intelligence": ("PDF第14页", "计划新增高性能算力2500P以上，建设人工智能产业园、示范场景和行业大模型。"),
        "innovative-drugs": ("PDF第2、13页", "已有一类创新药上市，并部署创新药、医疗器械研发制造和国际医疗创新高地。"),
    },
    "浙江省": {
        "integrated-circuits": ("首批专项基金签约段", "总规模500亿元的浙江社保科创基金启动6支专项基金并完成首批项目签约，重点投向集成电路等领域。"),
        "artificial-intelligence": ("首批专项基金签约段", "总规模500亿元的浙江社保科创基金启动6支专项基金并完成首批项目签约，重点投向人工智能等领域。"),
        "innovative-drugs": None,
    },
    "深圳市": {
        "integrated-circuits": ("产业项目段", "华润微电子12英寸集成电路生产线投产，相关制造项目继续爬坡。"),
        "artificial-intelligence": ("人工智能产业段", "已备案大模型并建设重点实验室、算力和产业应用项目。"),
        "innovative-drugs": ("生物医药产业段", "规划建设光明、坪山生物医药制造园和龙华高端医疗器械产业城。"),
    },
    "苏州市": {
        "integrated-circuits": None,
        "artificial-intelligence": ("人工智能产业段", "建设模术空间、智算未来城、具身智谷等载体，并安排3.4万P算力和200个场景。"),
        "innovative-drugs": None,
    },
}


def _initial_records(direction_id: str) -> list[dict]:
    records = []
    for region in TARGET_REGIONS:
        if region in VERIFIED_RESULTS:
            result = VERIFIED_RESULTS[region][direction_id]
            source = OFFICIAL_SOURCES[region]
            if result is None:
                records.append(
                    {
                        "region": region,
                        "province": REGION_JURISDICTION[region],
                        "status": COVERAGE_STATUS_NOT_FOUND,
                        **source,
                        "summary": "本轮已核验来源中未找到符合强证据标准的落地信息；这不是产业不存在或政策收缩的判断。",
                        "checked_on": CHECKED_ON,
                    }
                )
                continue
            locator, summary = result
            records.append(
                {
                    "region": region,
                    "province": REGION_JURISDICTION[region],
                    "status": COVERAGE_STATUS_LANDED,
                    **source,
                    "locator": locator,
                    "summary": summary,
                    "checked_on": CHECKED_ON,
                }
            )
        else:
            records.append(
                {
                    "region": region,
                    "province": REGION_JURISDICTION[region],
                    "status": COVERAGE_STATUS_UNSEARCHED,
                    "source": f"2026{region}《政府工作报告》PDF.pdf",
                    "summary": "现有PDF文本层不可检索，待OCR或改用官方网页原文核验。",
                    "checked_on": None,
                }
            )
    return records


INITIAL_COVERAGE_BY_DIRECTION = {
    direction_id: _initial_records(direction_id)
    for direction_id in (
        "integrated-circuits",
        "artificial-intelligence",
        "innovative-drugs",
    )
}


def build_coverage_summary(
    records: list[dict],
    required_checked_ratio: float = 0.8,
    national_support_confirmed: bool = False,
) -> dict:
    if not 0 < required_checked_ratio <= 1:
        raise ValueError("覆盖比例必须在0到1之间")
    invalid = {item.get("status") for item in records} - VALID_COVERAGE_STATUSES
    if invalid:
        raise ValueError(f"未知覆盖状态：{sorted(invalid)}")

    target_count = len(records)
    unsearched_count = sum(
        item["status"] == COVERAGE_STATUS_UNSEARCHED for item in records
    )
    checked_count = target_count - unsearched_count
    landed_count = sum(item["status"] == COVERAGE_STATUS_LANDED for item in records)
    landed_jurisdiction_count = len(
        {
            item.get("province", item["region"])
            for item in records
            if item["status"] == COVERAGE_STATUS_LANDED
        }
    )
    not_found_count = sum(
        item["status"] == COVERAGE_STATUS_NOT_FOUND for item in records
    )
    contracted_count = sum(
        item["status"] == COVERAGE_STATUS_CONTRACTED for item in records
    )
    required_checked_count = math.ceil(target_count * required_checked_ratio)
    coverage_sufficient = checked_count >= required_checked_count
    summary = {
        "target_count": target_count,
        "checked_count": checked_count,
        "unsearched_count": unsearched_count,
        "not_found_count": not_found_count,
        "landed_count": landed_count,
        "landed_jurisdiction_count": landed_jurisdiction_count,
        "contracted_count": contracted_count,
        "required_checked_count": required_checked_count,
        "coverage_sufficient": coverage_sufficient,
        "coverage_status": "覆盖充分" if coverage_sufficient else "覆盖不足",
        "national_support_confirmed": national_support_confirmed,
    }
    summary["passes_local_execution"] = passes_local_execution_gate(summary)
    summary["display"] = (
        f"地方覆盖：已查{checked_count}/{target_count}个重点地区｜"
        f"{landed_count}地发现落地｜{summary['coverage_status']}"
    )
    return summary


def passes_local_execution_gate(summary: dict) -> bool:
    if not summary.get("coverage_sufficient", False):
        return False
    landed_jurisdictions = summary.get(
        "landed_jurisdiction_count", summary.get("landed_count", 0)
    )
    return landed_jurisdictions >= 2 or (
        landed_jurisdictions >= 1
        and summary.get("national_support_confirmed", False)
    )


def get_direction_coverage(direction_id: str) -> dict:
    records = INITIAL_COVERAGE_BY_DIRECTION.get(direction_id, [])
    return {
        **build_coverage_summary(records),
        "version": COVERAGE_VERSION,
        "records": records,
    }
