# Strategic Satellite Increasing Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把电网、稀土、港股创新药当前一轮改为 `20% / 30% / 50%` 递增分批，并安全迁移现有私有计划。

**Architecture:** 继续使用 `purchase_plan.py` 的版本化 JSON 迁移，不增加页面组件或新服务。金额、分配比例和提示集中在 `STRATEGIC_PLANS`；v5→v6 迁移只重建尚未执行的格子，已买入或已对账记录保持原计划金额、日期和成交事实。

**Tech Stack:** Python 3、unittest、Streamlit、JSON 本地私有账本。

## Global Constraints

- 电网当前一轮固定为 `1,200 / 1,800 / 3,000` 元，后续预留 6,000 元。
- 稀土当前一轮固定为 `1,000 / 1,500 / 2,500` 元，后续预留 5,000 元。
- 港股创新药当前一轮固定为 `800 / 1,200 / 2,000` 元，后续预留 4,000 元。
- 三阶段提示固定为“第1笔等初步止跌；第2笔等回踩确认；第3笔等右侧修复”。
- 不能因为价格更低自动执行下一笔；页面不自动判定信号、不自动下单。
- A500、沪深300、黄金、科创50不变；半年计划总额保持 82,815 元。
- 不增加数据库、定时任务、行情规则或页面结构。

---

### Task 1: 用 TDD 实现 v6 默认计划和迁移边界

**Files:**
- Modify: `tests/test_purchase_plan.py`
- Modify: `purchase_plan.py`

**Interfaces:**
- Consumes: `default_purchase_plan() -> dict`、`load_purchase_plan(path: str) -> dict`。
- Produces: v6 默认金额、提示、分配比例，以及只更新未执行格子的 v5→v6 迁移。

- [x] **Step 1: 修改默认计划测试，要求 v6 与新金额**

把 `test_strategic_satellites_use_50_25_25_current_rounds` 改名为
`test_strategic_satellites_use_20_30_50_current_rounds`，并将期望值改为：

```python
expected = {
    "561380": ([1_200.0, 1_800.0, 3_000.0], 6_000.0),
    "516150": ([1_000.0, 1_500.0, 2_500.0], 5_000.0),
    "159570": ([800.0, 1_200.0, 2_000.0], 4_000.0),
}
expected_note = "第1笔等初步止跌；第2笔等回踩确认；第3笔等右侧修复"
for symbol, (amounts, reserved_amount) in expected.items():
    asset = plan["assets"][symbol]
    self.assertEqual([item["planned_amount"] for item in asset["items"]], amounts)
    self.assertEqual(asset["reserved_amount"], reserved_amount)
    self.assertEqual(asset["plan_note"], expected_note)

self.assertEqual(
    plan["allocation_scheme"]["strategic_satellite"],
    {"first": 0.2, "second": 0.3, "third": 0.5},
)
self.assertEqual(plan["version"], 6)
```

同时把当前测试中默认计划、v2、v3、v4 迁移后的所有版本断言从 5 改为 6；
金额、状态和日期断言保持原样。

- [x] **Step 2: 新增 v5 迁移保护测试**

在 `PurchasePlanDefaultsTests` 中新增：

```python
def test_version_five_migration_updates_only_unstarted_strategic_items(self):
    plan = default_purchase_plan()
    plan["version"] = 5
    asset = plan["assets"]["561380"]
    asset["items"] = [
        {
            **item,
            "planned_amount": old_amount,
            "status": STATUS_PENDING if item["number"] == 1 else STATUS_PLANNED,
            "confirmed_date": "2026-07-17" if item["number"] == 1 else None,
        }
        for item, old_amount in zip(asset["items"], [3_000.0, 1_500.0, 1_500.0])
    ]

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "purchase_plan.json")
        save_purchase_plan(plan, path)
        loaded = load_purchase_plan(path)

    migrated = loaded["assets"]["561380"]["items"]
    self.assertEqual(loaded["version"], 6)
    self.assertEqual(
        [item["planned_amount"] for item in migrated],
        [3_000.0, 1_800.0, 3_000.0],
    )
    self.assertEqual(migrated[0]["status"], STATUS_PENDING)
    self.assertEqual(migrated[0]["confirmed_date"], "2026-07-17")
```

- [x] **Step 3: 运行测试并确认按预期失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan
```

Expected: FAIL，显示当前版本仍为 5、战略金额仍为旧的 `50% / 25% / 25%`，或 v5 迁移未更新计划中格子。

- [x] **Step 4: 修改战略常量和默认提示**

在 `purchase_plan.py` 中改为：

```python
CURRENT_PLAN_VERSION = 6
STRATEGIC_SATELLITE_ALLOCATION = {"first": 0.2, "second": 0.3, "third": 0.5}
STRATEGIC_PLAN_NOTE = "第1笔等初步止跌；第2笔等回踩确认；第3笔等右侧修复"
STRATEGIC_PLANS = {
    "561380": {
        "current_round": (1_200.0, 1_800.0, 3_000.0),
        "reserved_amount": 6_000.0,
        "plan_note": STRATEGIC_PLAN_NOTE,
    },
    "516150": {
        "current_round": (1_000.0, 1_500.0, 2_500.0),
        "reserved_amount": 5_000.0,
        "plan_note": STRATEGIC_PLAN_NOTE,
    },
    "159570": {
        "current_round": (800.0, 1_200.0, 2_000.0),
        "reserved_amount": 4_000.0,
        "plan_note": STRATEGIC_PLAN_NOTE,
    },
}
```

- [x] **Step 5: 保护已经开始的计划格**

在 `_strategic_asset` 中保留非 `STATUS_PLANNED` 格子的完整旧记录和旧计划金额：

```python
if old_item and old_item.get("status") != STATUS_PLANNED:
    item = copy.deepcopy(old_item)
else:
    item = _new_item(symbol, number, amount)
```

不要对已买入或已对账格执行 `item["planned_amount"] = float(amount)`。

- [x] **Step 6: 新增 v5→v6 迁移**

在 `_migrate_plan` 设置最终版本前加入：

```python
if version < 6:
    assets = updated.setdefault("assets", {})
    for symbol in STRATEGIC_PLANS:
        assets[symbol] = _strategic_asset(symbol, assets.get(symbol))
    updated["allocation_scheme"] = {
        "strategic_satellite": copy.deepcopy(STRATEGIC_SATELLITE_ALLOCATION)
    }
```

- [x] **Step 7: 运行定向测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan
```

Expected: `Ran 16 tests`，`OK`。

---

### Task 2: 更新私有账本、项目事实并验证页面

**Files:**
- Modify: `private_data/purchase_plan.json`
- Modify: `PROJECT_CONTEXT.md`
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: Task 1 产出的 v6 `load_purchase_plan()` 与 `summarize_plan()`。
- Produces: 已迁移的真实本机计划、长期决策记录和页面验收证据。

- [x] **Step 1: 更新私有账本**

使用 `apply_patch` 将 `private_data/purchase_plan.json` 的版本改为 6、分配比例改为
`0.2 / 0.3 / 0.5`，并更新三只重点 ETF 的三笔计划金额和 `plan_note`。
三只重点 ETF 当前均为 `planned`，因此可全部改成新金额；A500 与沪深300第三笔的
`pending_reconciliation` 状态和 `2026-07-17` 日期必须保持不变。

- [x] **Step 2: 更新长期事实和当前状态**

在 `PROJECT_CONTEXT.md` 的“当前战略卫星仓计划”和“账户重分配与战略卫星仓口径”中
写入新金额及三阶段纪律；在 `STATUS.md` 顶部记录 v6 完成情况和验证证据。

- [x] **Step 3: 运行完整验证**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m py_compile purchase_plan.py app.py
git diff --check
```

Expected: 全部测试 `OK`、语法检查退出码 0、`git diff --check` 无错误。

再用 Python 断言私有账本：

```python
from purchase_plan import load_purchase_plan, summarize_plan

plan = load_purchase_plan("private_data/purchase_plan.json")
assert plan["version"] == 6
assert [item["planned_amount"] for item in plan["assets"]["561380"]["items"]] == [1200.0, 1800.0, 3000.0]
assert [item["planned_amount"] for item in plan["assets"]["516150"]["items"]] == [1000.0, 1500.0, 2500.0]
assert [item["planned_amount"] for item in plan["assets"]["159570"]["items"]] == [800.0, 1200.0, 2000.0]
assert summarize_plan(plan)["planned_total"] == 82815.0
```

- [x] **Step 4: 浏览器核验**

打开 `http://127.0.0.1:8501/` 的“半年买入计划”，确认三只重点 ETF 的金额和提示均正确，
宽基三笔仍全部为已买入/待对账，页面汇总总额仍为 82,815 元。

- [x] **Step 5: 提交实现**

只暂存本次确认范围内的计划模型、测试和项目文档；不要暂存既有未知脚本或临时文件：

```powershell
git add -- purchase_plan.py tests/test_purchase_plan.py PROJECT_CONTEXT.md STATUS.md
git commit -m "feat: use increasing strategic ETF entries"
```
