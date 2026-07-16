"""首批经 Codex 对照官方原文核验、等待达达确认的证据。"""


NATIONAL_PLAN_URL = (
    "https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2026/"
    "2026_zt03/yw/202603/t20260314_1430877.html"
)
NATIONAL_REPORT_URL = (
    "https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2026/"
    "2026_zt03/baogao/202603/t20260314_1430876.html"
)
NATIONAL_PLAN_PATH = (
    r"G:\达达项目资料库\03_AI软件项目\政府资金分析仪\政府报告资料\政府报告"
    r"\十五五规划纲要 PDF.pdf"
)
NATIONAL_REPORT_PATH = (
    r"G:\达达项目资料库\03_AI软件项目\政府资金分析仪\政府报告资料\政府报告"
    r"\2026《政府工作报告》PDF.pdf"
)


INITIAL_EVIDENCE = (
    {
        "id": "national-15-hard-tech",
        "title": "十五五关键核心技术攻坚硬名单",
        "industries": [
            "semiconductor",
            "manufacturing",
            "high-end-instruments",
            "industrial-software",
            "new-materials",
            "biomanufacturing",
        ],
        "evidence_type": "政策表态",
        "quote": "全链条推动集成电路、工业母机、高端仪器、基础软件、先进材料、生物制造等重点领域关键核心技术攻关取得决定性突破。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL,
        "local_path": NATIONAL_PLAN_PATH,
        "locator": "PDF第31页",
        "codex_verified": True,
    },
    {
        "id": "national-15-ai-strategy",
        "title": "人工智能国家科技战略部署",
        "industries": ["ai"],
        "evidence_type": "政策表态",
        "quote": "实施人工智能、量子科技、生物科技、新能源等科技战略部署。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL,
        "local_path": NATIONAL_PLAN_PATH,
        "locator": "PDF第31页",
        "codex_verified": True,
    },
    {
        "id": "national-15-future-growth",
        "title": "十五五未来产业增长点",
        "industries": [
            "quantum-tech",
            "biomanufacturing",
            "hydrogen-fusion",
            "brain-computer",
            "robotics",
            "six-g",
        ],
        "evidence_type": "政策表态",
        "quote": "推动量子科技、生物制造、氢能和核聚变能、脑机接口、具身智能、第六代移动通信等成为新的经济增长点。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL,
        "local_path": NATIONAL_PLAN_PATH,
        "locator": "PDF第19页",
        "codex_verified": True,
    },
    {
        "id": "report-2026-pillars",
        "title": "2026新兴支柱产业",
        "industries": [
            "semiconductor",
            "commercial-space",
            "domestic-aircraft",
            "biomedicine",
            "low-altitude-economy",
        ],
        "evidence_type": "年度执行",
        "quote": "打造集成电路、航空航天、生物医药、低空经济等新兴支柱产业。",
        "source_name": "2026年政府工作报告",
        "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH,
        "locator": "培育壮大新兴产业和未来产业段",
        "codex_verified": True,
    },
    {
        "id": "report-2026-ai-plus",
        "title": "2026人工智能规模化应用",
        "industries": ["ai"],
        "evidence_type": "年度执行",
        "quote": "推动重点行业领域人工智能商业化规模化应用，培育智能原生新业态新模式。",
        "source_name": "2026年政府工作报告",
        "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH,
        "locator": "深化拓展‘人工智能+’段",
        "codex_verified": True,
    },
    {
        "id": "report-2026-patient-capital",
        "title": "政府投资基金与耐心资本",
        "industries": ["green-finance"],
        "evidence_type": "资金承诺",
        "quote": "政府投资基金要带头做耐心资本，推动更多初创企业加快成长为科技领军企业。",
        "source_name": "2026年政府工作报告",
        "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH,
        "locator": "培育壮大新兴产业和未来产业段",
        "codex_verified": True,
    },
)

EVIDENCE_BY_ID = {item["id"]: item for item in INITIAL_EVIDENCE}
