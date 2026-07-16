"""政策候选产业目录。

旧项目的 34 个候选全部保留；同时依据十五五原文补入“高端仪器”，
并把旧“制造业”的展示名称收窄为“工业母机/高端制造”。
"""


POLICY_CANDIDATES = (
    {"id": "semiconductor", "name": "半导体/芯片", "group": "硬科技攻坚", "origin": "旧项目"},
    {"id": "manufacturing", "name": "工业母机/高端制造", "group": "硬科技攻坚", "origin": "旧项目名称修正"},
    {"id": "high-end-instruments", "name": "高端仪器", "group": "硬科技攻坚", "origin": "十五五原文修正"},
    {"id": "industrial-software", "name": "基础软件/工业软件", "group": "硬科技攻坚", "origin": "旧项目"},
    {"id": "new-materials", "name": "先进材料", "group": "硬科技攻坚", "origin": "旧项目"},
    {"id": "biomanufacturing", "name": "生物制造", "group": "硬科技攻坚", "origin": "旧项目"},
    {"id": "ai", "name": "人工智能", "group": "跨行业总引擎", "origin": "旧项目分组修正"},
    {"id": "robotics", "name": "机器人/具身智能", "group": "未来增长点", "origin": "旧项目"},
    {"id": "quantum-tech", "name": "量子科技", "group": "未来增长点", "origin": "旧项目"},
    {"id": "brain-computer", "name": "脑机接口", "group": "未来增长点", "origin": "旧项目"},
    {"id": "six-g", "name": "6G通信", "group": "未来增长点", "origin": "旧项目"},
    {"id": "hydrogen-fusion", "name": "氢能与核聚变", "group": "未来增长点", "origin": "旧项目"},
    {"id": "new-energy", "name": "新能源", "group": "能源与资源安全", "origin": "旧项目"},
    {"id": "nuclear-energy", "name": "核能", "group": "能源与资源安全", "origin": "旧项目"},
    {"id": "energy-storage", "name": "储能", "group": "能源与资源安全", "origin": "旧项目"},
    {"id": "critical-minerals", "name": "关键矿产", "group": "能源与资源安全", "origin": "旧项目"},
    {"id": "power-grid", "name": "电力设备与电网", "group": "能源与资源安全", "origin": "旧项目"},
    {"id": "low-altitude-economy", "name": "低空经济", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "digital-economy", "name": "数字经济", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "commercial-space", "name": "商业航天", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "biomedicine", "name": "生物医药", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "autonomous-driving", "name": "智能驾驶", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "medical-devices", "name": "医疗器械", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "domestic-aircraft", "name": "大飞机", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "nev", "name": "新能源车", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "deep-sea", "name": "深海经济", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "data-elements", "name": "数据要素", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "agritech", "name": "农业科技", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "traditional-chinese-medicine", "name": "中医药", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "seed-industry", "name": "种业", "group": "战略性新兴产业", "origin": "旧项目"},
    {"id": "green-finance", "name": "绿色金融与耐心资本", "group": "制度民生", "origin": "旧项目"},
    {"id": "silver-economy", "name": "银发经济", "group": "制度民生", "origin": "旧项目"},
    {"id": "ice-snow-economy", "name": "冰雪经济", "group": "制度民生", "origin": "旧项目"},
    {"id": "carbon-market", "name": "碳市场", "group": "监管与制度", "origin": "旧项目"},
    {"id": "platform-economy", "name": "平台经济", "group": "监管与制度", "origin": "旧项目"},
)

CANDIDATE_BY_ID = {item["id"]: item for item in POLICY_CANDIDATES}
