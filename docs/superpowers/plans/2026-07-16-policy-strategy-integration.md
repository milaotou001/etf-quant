# 政府资金战略方向层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Streamlit ETF 工具中新增独立第六页“战略方向”，迁入政策候选目录和首批官方证据，并实现只有经过 Codex 核验与达达确认后才生效的本地审核流程。

**Architecture:** 在项目中建立独立 `policy/` Python 包：`catalog.py` 保存候选产业，`evidence.py` 保存首批官方证据，`reviews.py` 负责双确认持久化，`strategy.py` 计算只读战略快照，`page.py` 负责 Streamlit 展示。`app.py` 只增加导航和页面路由，不让战略页面触发 ETF 行情加载；用户审核结果保存在已被 `.gitignore` 排除的 `private_data/policy_reviews.json`。旧 React 项目只作迁移校对来源，新应用运行时不依赖它。

**Tech Stack:** Python 3、标准库 JSON/dataclasses、Streamlit、unittest、`streamlit.testing.v1.AppTest`。

## Global Constraints

- 只有 `Codex已核验 + 达达已确认` 的证据状态为“正式生效”。
- 第一版不自动生成正式年度白名单；正式 3—5 个方向必须在证据双确认完成后单独确认。
- 旧项目 34 个候选全部建档，另加十五五原文遗漏修正“高端仪器”，页面明确显示“旧34项 + 1项修正”。
- 原始 Word/PDF 留在 G 盘；代码只保存结构化索引、官方 URL、本地路径、页码和短原文摘录。
- 政府资金战略层不输出买入、卖出、仓位或止损指令，不把 ETF 涨跌幅解释为政府资金流入。
- 不修改、删除或覆盖现有私人对账单、交易缓存、买入计划和用户未提交改动。
- 不新增第三方依赖，不提交或推送 Git。

---

### Task 1: 独立政策包、候选目录与证据审核模型

**Files:**
- Create: `policy/__init__.py`
- Create: `policy/catalog.py`
- Create: `policy/evidence.py`
- Create: `policy/reviews.py`
- Create: `policy/strategy.py`
- Create: `tests/test_policy_strategy.py`

**Interfaces:**
- `POLICY_CANDIDATES: tuple[dict, ...]`：35 个候选产业，每项包含 `id/name/group/origin`。
- `INITIAL_EVIDENCE: tuple[dict, ...]`：六条首批官方证据，每项包含 `id/title/industries/evidence_type/quote/source_name/source_url/local_path/locator/codex_verified`。
- `load_policy_reviews(path: str | Path = REVIEW_PATH) -> dict`
- `save_policy_reviews(state: dict, path: str | Path = REVIEW_PATH) -> None`
- `review_evidence(evidence_id: str, decision: str, reviewed_on: str, note: str = "", path: str | Path = REVIEW_PATH) -> dict`
- `resolve_evidence_status(evidence: dict, reviews: dict) -> str`
- `build_policy_snapshot(reviews: dict | None = None) -> dict`

- [ ] **Step 1: Write the failing domain tests**

```python
class PolicyCatalogTests(unittest.TestCase):
    def test_catalog_contains_legacy_34_plus_high_end_instruments(self):
        self.assertEqual(len(POLICY_CANDIDATES), 35)
        corrected = next(item for item in POLICY_CANDIDATES if item["id"] == "high-end-instruments")
        self.assertEqual(corrected["origin"], "十五五原文修正")

class PolicyReviewTests(unittest.TestCase):
    def test_codex_verified_evidence_is_not_effective_before_user_confirmation(self):
        evidence = INITIAL_EVIDENCE[0]
        self.assertEqual(resolve_evidence_status(evidence, {"reviews": {}}), "Codex已核验")

    def test_confirmed_evidence_becomes_effective_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reviews.json")
            review_evidence(INITIAL_EVIDENCE[0]["id"], "confirmed", "2026-07-16", path=path)
            state = load_policy_reviews(path)
        self.assertEqual(resolve_evidence_status(INITIAL_EVIDENCE[0], state), "正式生效")

    def test_rejected_evidence_never_counts_as_effective(self):
        reviews = {"reviews": {INITIAL_EVIDENCE[0]["id"]: {"decision": "rejected"}}}
        self.assertEqual(resolve_evidence_status(INITIAL_EVIDENCE[0], reviews), "已驳回")

    def test_snapshot_keeps_formal_whitelist_empty(self):
        snapshot = build_policy_snapshot({"reviews": {}})
        self.assertEqual(snapshot["formal_directions"], [])
        self.assertGreater(snapshot["pending_confirmation_count"], 0)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_strategy -v`  
Expected: FAIL because the `policy` package does not exist.

- [ ] **Step 3: Implement the catalog and review model**

Create `policy/catalog.py` with the exact 35-item catalog below. `manufacturing` keeps the legacy ID for migration compatibility, but its display name is corrected to the narrower national wording; `high-end-instruments` is the one newly added item.

```python
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
```

Create `policy/evidence.py` with six records and the shared source paths below. The national plan records use the verified PDF page; government-report records use the named paragraph locator because the local PDF is image-based.

```python
NATIONAL_PLAN_URL = "https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2026/2026_zt03/yw/202603/t20260314_1430877.html"
NATIONAL_REPORT_URL = "https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2026/2026_zt03/baogao/202603/t20260314_1430876.html"
NATIONAL_PLAN_PATH = r"G:\达达项目资料库\03_AI软件项目\政府资金分析仪\政府报告资料\政府报告\十五五规划纲要 PDF.pdf"
NATIONAL_REPORT_PATH = r"G:\达达项目资料库\03_AI软件项目\政府资金分析仪\政府报告资料\政府报告\2026《政府工作报告》PDF.pdf"

INITIAL_EVIDENCE = (
    {
        "id": "national-15-hard-tech",
        "title": "十五五关键核心技术攻坚硬名单",
        "industries": ["semiconductor", "manufacturing", "high-end-instruments", "industrial-software", "new-materials", "biomanufacturing"],
        "evidence_type": "政策表态",
        "quote": "全链条推动集成电路、工业母机、高端仪器、基础软件、先进材料、生物制造等重点领域关键核心技术攻关取得决定性突破。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL, "local_path": NATIONAL_PLAN_PATH, "locator": "PDF第31页",
        "codex_verified": True,
    },
    {
        "id": "national-15-ai-strategy", "title": "人工智能国家科技战略部署",
        "industries": ["ai"], "evidence_type": "政策表态",
        "quote": "实施人工智能、量子科技、生物科技、新能源等科技战略部署。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL, "local_path": NATIONAL_PLAN_PATH, "locator": "PDF第31页",
        "codex_verified": True,
    },
    {
        "id": "national-15-future-growth", "title": "十五五未来产业增长点",
        "industries": ["quantum-tech", "biomanufacturing", "hydrogen-fusion", "brain-computer", "robotics", "six-g"],
        "evidence_type": "政策表态",
        "quote": "推动量子科技、生物制造、氢能和核聚变能、脑机接口、具身智能、第六代移动通信等成为新的经济增长点。",
        "source_name": "中华人民共和国国民经济和社会发展第十五个五年规划纲要",
        "source_url": NATIONAL_PLAN_URL, "local_path": NATIONAL_PLAN_PATH, "locator": "PDF第19页",
        "codex_verified": True,
    },
    {
        "id": "report-2026-pillars", "title": "2026新兴支柱产业",
        "industries": ["semiconductor", "commercial-space", "domestic-aircraft", "biomedicine", "low-altitude-economy"],
        "evidence_type": "年度执行",
        "quote": "打造集成电路、航空航天、生物医药、低空经济等新兴支柱产业。",
        "source_name": "2026年政府工作报告", "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH, "locator": "培育壮大新兴产业和未来产业段",
        "codex_verified": True,
    },
    {
        "id": "report-2026-ai-plus", "title": "2026人工智能规模化应用",
        "industries": ["ai"], "evidence_type": "年度执行",
        "quote": "推动重点行业领域人工智能商业化规模化应用，培育智能原生新业态新模式。",
        "source_name": "2026年政府工作报告", "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH, "locator": "深化拓展‘人工智能+’段",
        "codex_verified": True,
    },
    {
        "id": "report-2026-patient-capital", "title": "政府投资基金与耐心资本",
        "industries": ["green-finance"], "evidence_type": "资金承诺",
        "quote": "政府投资基金要带头做耐心资本，推动更多初创企业加快成长为科技领军企业。",
        "source_name": "2026年政府工作报告", "source_url": NATIONAL_REPORT_URL,
        "local_path": NATIONAL_REPORT_PATH, "locator": "培育壮大新兴产业和未来产业段",
        "codex_verified": True,
    },
)
```

Create `policy/reviews.py` for JSON round-trip with temp-file replacement. Validate `decision in {"confirmed", "rejected"}`, reject unknown evidence IDs, and let `resolve_evidence_status()` return exactly `Codex已核验 / 正式生效 / 已驳回 / 待整理`. Create `policy/strategy.py` so `build_policy_snapshot()` returns candidate counts, evidence-status counts and an empty `formal_directions` list; it must not rank or publish directions yet.

- [ ] **Step 4: Run the domain tests and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_strategy -v`  
Expected: all policy domain tests PASS.

---

### Task 2: 原生 Streamlit 战略研究页面

**Files:**
- Create: `policy/page.py`
- Create: `tests/test_policy_page.py`

**Interfaces:**
- `render_policy_strategy(review_path: str | Path = REVIEW_PATH) -> None`
- Consumes `build_policy_snapshot()`, `load_policy_reviews()` and `review_evidence()` from Task 1.
- Produces five tabs: `战略总览 / 产业档案 / 证据审核 / 历次变化 / 方法与来源`。

- [ ] **Step 1: Write the failing Streamlit component test**

```python
class PolicyPageTests(unittest.TestCase):
    def test_page_renders_empty_formal_whitelist_and_review_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "policy_reviews.json")
            script = f'''from policy.page import render_policy_strategy\nrender_policy_strategy(r"{review_path}")'''
            app = AppTest.from_string(script).run()
        self.assertEqual(app.exception, [])
        markdown = " ".join(item.value for item in app.markdown)
        self.assertIn("年度战略白名单尚未发布", markdown)
        self.assertIn("旧34项 + 1项原文修正", markdown)
        self.assertGreaterEqual(len(app.tabs), 5)
```

- [ ] **Step 2: Run the page test and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_page -v`  
Expected: FAIL because `policy.page` does not exist.

- [ ] **Step 3: Implement the research page**

Build a light top-level page with:

```python
def render_policy_strategy(review_path=REVIEW_PATH):
    reviews = load_policy_reviews(review_path)
    snapshot = build_policy_snapshot(reviews)
    st.title("战略方向")
    st.caption("政府资金分析仪 · 五年定方向，年度做复核，季度查资金，事件触发修正")
    st.info("年度战略白名单尚未发布。首批证据已由 Codex 核验，等待达达逐条确认。")
    overview, dossiers, review, history, method = st.tabs(
        ["战略总览", "产业档案", "证据审核", "历次变化", "方法与来源"]
    )
```

Requirements:

- 总览显示正式方向数、待确认数、候选数和更新制度，不显示买入建议。
- 产业档案按国家硬科技攻坚、跨行业总引擎、新兴支柱、未来增长点等分组显示，明确“候选不等于入选”。
- 审核页逐条显示短原文、来源、页码、对应产业、证据类型与 Codex 状态；确认和驳回按钮写入 `review_path`。
- 历次变化第一版显示“尚无正式版本”，不伪造历史。
- 方法页完整说明四道硬门槛、双确认和战略/战术边界。

- [ ] **Step 4: Run the page test and verify GREEN**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_page -v`  
Expected: PASS with no Streamlit exception.

---

### Task 3: 接入 ETF 工具第六页

**Files:**
- Modify: `app.py`
- Modify: `tests/test_policy_page.py`

**Interfaces:**
- `app.py` imports `render_policy_strategy` from `policy.page`.
- Sidebar page order becomes `状态与图表 / 复盘日志 / 策略回测 / 策略规则 / 半年买入计划 / 战略方向`.
- Selecting `战略方向` renders without calling `load_prepared_data()`.

- [ ] **Step 1: Extend the test with navigation assertions**

```python
def test_main_app_lists_strategy_as_sixth_page(self):
    source = Path(PROJECT_ROOT, "app.py").read_text(encoding="utf-8")
    navigation = '["状态与图表", "复盘日志", "策略回测", "策略规则", "半年买入计划", "战略方向"]'
    self.assertIn(navigation, source)
    self.assertIn('if page == "战略方向":', source)
```

- [ ] **Step 2: Run the navigation test and verify RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_page.PolicyPageTests.test_main_app_lists_strategy_as_sixth_page -v`  
Expected: FAIL because `app.py` has only five pages.

- [ ] **Step 3: Add import, navigation and early route**

Add:

```python
from policy.page import render_policy_strategy

page = st.radio(
    "页面",
    ["状态与图表", "复盘日志", "策略回测", "策略规则", "半年买入计划", "战略方向"],
)

if page == "战略方向":
    render_policy_strategy()
elif page == "半年买入计划":
    plan = load_purchase_plan()
    reconciled_plan = reconcile_purchase_plan(plan, trade_cache)
else:
    df = load_prepared_data(symbol, st.session_state.refresh_token)
```

Use the shown first statements as the start of the existing purchase-plan and market-data branches, then retain the rest of each existing branch unchanged. Keep statement upload enabled only where it already applies; the strategy page must not read or modify statement data.

- [ ] **Step 4: Run page and navigation tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_policy_strategy tests.test_policy_page -v`  
Expected: all policy tests PASS.

---

### Task 4: Full verification and project status

**Files:**
- Modify: `STATUS.md`
- Modify: `PROJECT_CONTEXT.md` only if implementation changes a long-term fact not already recorded.

**Interfaces:**
- Verification commands are read-only except Streamlit's normal local cache/review behavior.

- [ ] **Step 1: Run syntax verification**

Run: `.venv\Scripts\python.exe -m py_compile app.py policy\catalog.py policy\evidence.py policy\reviews.py policy\strategy.py policy\page.py`  
Expected: exit code 0.

- [ ] **Step 2: Run the complete test suite**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`  
Expected: all existing and new tests PASS.

- [ ] **Step 3: Run a Streamlit smoke test**

Run: `powershell -ExecutionPolicy Bypass -File .\start_app.ps1` and request the configured local health endpoint.  
Expected: `/_stcore/health` returns HTTP 200 and the server log has no import exception.

- [ ] **Step 4: Inspect the intentional diff**

Run: `git diff --check` and `git status --short`.  
Expected: no whitespace errors; existing unrelated dirty files remain untouched; no G-drive PDF or private review JSON appears as a tracked file.

- [ ] **Step 5: Update STATUS.md**

Record created files, page behavior, evidence count, review-state path, exact test totals and smoke-test result. Do not claim a formal annual whitelist exists.
