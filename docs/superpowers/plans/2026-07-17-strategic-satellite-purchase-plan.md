# Strategic Satellite Purchase Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将账户目标重分配为严格合计 285,000 元，并把电网、稀土、创新药按确认金额加入半年买入计划。

**Architecture:** 继续使用 `purchase_plan.py` 作为唯一计划领域模型，通过 v4 迁移保留已发生记录、移除两只宽基未执行计划，并新增两个战略标的。`app.py` 只负责显示计划提示和沿用现有格子交互；私有 JSON 保存达达当前真实状态。

**Tech Stack:** Python 3、unittest、Streamlit、JSON 本地持久化。

## Global Constraints

- 账户基数固定为 285,000 元，目标金额合计必须严格为 285,000 元。
- 现金目标保持 85,500 元，不自动下单，不根据实时缺口生成新计划。
- A500、沪深300已有第 1、2 笔记录保持不变，只移除尚未执行的第 3—6 笔。
- 电网、稀土、创新药后续预留金额不计入当前半年计划汇总。
- 不修改行情、RSI、战略方向、复盘和回测模块。

---

### Task 1: 计划模型与 v4 迁移

**Files:**
- Modify: `tests/test_purchase_plan.py`
- Modify: `purchase_plan.py`

**Interfaces:**
- Consumes: `default_purchase_plan() -> dict`、`load_purchase_plan(path) -> dict`
- Produces: `CURRENT_PLAN_VERSION = 4`，七个资产目标，三个战略资产的 `reserved_amount`、`plan_note` 和当前三笔计划。

- [ ] **Step 1: 写默认计划与账户总额失败测试**

在 `PurchasePlanDefaultsTests` 中断言目标分别为 42,000、42,000、57,000、28,500、12,000、10,000、8,000，现金为 85,500，总和为 285,000；断言电网三笔为 3,000/1,500/1,500，稀土为 2,500/1,250/1,250，创新药为 2,000/1,000/1,000。

- [ ] **Step 2: 写 v3 迁移失败测试**

构造带有两只宽基前两笔 `pending_reconciliation` 的 v3 计划，加载后断言版本为 4、前两笔状态和日期不变、第 3—6 笔不存在，并断言三个战略资产金额正确。

- [ ] **Step 3: 运行定向测试并确认失败**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan`

Expected: 因版本仍为 3、缺少 516150/159570、目标和金额仍是旧值而失败。

- [ ] **Step 4: 最小实现 v4 模型**

在 `purchase_plan.py` 中：

```python
CURRENT_PLAN_VERSION = 4
TARGETS = {
    "563360": {"name": "A500", "target": 42_000.0, "color": "#2f855a", "soft_color": "#dcefe5"},
    "510300": {"name": "沪深300", "target": 42_000.0, "color": "#2563eb", "soft_color": "#dbeafe"},
    "518880": {"name": "黄金", "target": 57_000.0, "color": "#d69e2e", "soft_color": "#f9edc7"},
    "588000": {"name": "科创50", "target": 28_500.0, "color": "#7c3aed", "soft_color": "#ede9fe"},
    "561380": {"name": "电网设备", "target": 12_000.0, "color": "#0891b2", "soft_color": "#cffafe"},
    "516150": {"name": "稀土", "target": 10_000.0, "color": "#c2410c", "soft_color": "#ffedd5"},
    "159570": {"name": "港股创新药", "target": 8_000.0, "color": "#db2777", "soft_color": "#fce7f3"},
}
```

增加通用战略资产构造器，生成三笔当前计划、预留金额和提示；v3 迁移保留宽基前两笔，只过滤 `number >= 3` 且仍为 `planned` 的项目，然后覆盖所有资产的最新目标元数据并加入稀土、创新药。

- [ ] **Step 5: 运行定向测试并确认通过**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan`

Expected: 全部通过。

### Task 2: 页面显示与汇总口径

**Files:**
- Modify: `app.py`
- Test: `tests/test_purchase_plan.py`

**Interfaces:**
- Consumes: 资产字段 `plan_note: str`、`reserved_amount: float`
- Produces: 每个战略资产标题下的简短执行提示；汇总只统计 `items`，不统计 `reserved_amount`。

- [ ] **Step 1: 在 Task 1 的失败测试中覆盖汇总口径**

断言默认计划的当前待办总额为 75,315 元，只包含三只战略资产的第一轮，不包含 15,000 元后续预留；默认已确认金额仍为黄金首笔 2,500 元。

- [ ] **Step 2: 确认 Task 1 的红绿循环已经覆盖汇总**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan`

Expected: Task 1 实现后汇总断言通过，且 `reserved_amount` 未进入 `summarize_plan()`。

- [ ] **Step 3: 更新页面最小文案**

在 `_render_asset_plan_row()` 中保留“理想仓位 · 后续预留”，并在存在 `plan_note` 时增加一行短提示；不禁用格子，不新增状态机。

- [ ] **Step 4: 运行测试并确认通过**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_purchase_plan`

Expected: 全部通过。

### Task 3: 真实私有计划、状态和完整验证

**Files:**
- Modify: `private_data/purchase_plan.json`
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: v4 计划结构
- Produces: 达达刷新页面即可读取的真实计划状态。

- [ ] **Step 1: 用迁移结果核对真实计划**

读取当前私有 JSON 并通过 `load_purchase_plan()` 生成 v4 结果，确认A500、沪深300前两笔状态和日期保持不变，三个战略资产均为计划中。

- [ ] **Step 2: 更新私有 JSON**

使用 `apply_patch` 将版本、目标、宽基项目和三个战略资产写入 `private_data/purchase_plan.json`；不得覆盖黄金、科创50及已有实际成交字段。

- [ ] **Step 3: 更新项目状态**

在 `STATUS.md` 顶部记录账户新目标、计划金额、迁移边界和验证结果。

- [ ] **Step 4: 运行完整验证**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile purchase_plan.py app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501
```

Expected: 语法检查退出码 0，全部测试通过，`git diff --check` 无错误，网页返回 HTTP 200。
