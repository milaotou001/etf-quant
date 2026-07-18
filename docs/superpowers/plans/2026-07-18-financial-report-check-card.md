# 财报检查卡实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在“半年买入计划”顶部显示电网、稀土与港股创新药的三个固定财报检查点和当前提醒。

**Architecture:** 新建独立纯函数模块，根据传入日期返回下一检查点、状态和固定披露窗口；`app.py` 只负责把结果渲染成一张卡。日期逻辑不联网、不读写买入计划数据，可以独立测试。

**Tech Stack:** Python、Streamlit、unittest。

## Global Constraints

- 不联网抓取公告，不创建后台任务，不引入新依赖。
- 不自动统计已披露公司数量，不保存完成状态。
- 不修改买入计划金额、交易状态或对账数据。
- 检查日期不是买入日期，不生成买卖信号。

---

### Task 1: 日期提醒模型

**Files:**
- Create: `financial_report_check.py`
- Create: `tests/test_financial_report_check.py`

**Interfaces:**
- Consumes: `datetime.date`。
- Produces: `build_financial_report_check(as_of: date) -> dict`，返回 `status`、`headline`、`next_date`、`checkpoints` 和 `disclosure_notes`。

- [ ] **Step 1: 写失败测试**

覆盖2026-07-18、2026-07-20、2026-08-16和2026-09-01，分别断言“下一检查点”“今天检查”“8月后的下一检查点”和“本轮统一复盘已到期”；同时断言电网贯穿检查点和披露窗口。

- [ ] **Step 2: 运行测试确认因模块缺失而失败**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_financial_report_check`

Expected: FAIL with `ModuleNotFoundError: No module named 'financial_report_check'`。

- [ ] **Step 3: 实现最小纯函数**

定义三个固定检查点，按日期返回第一个未到检查点；当天返回 `today`；超过检查点但尚未进入下一节点时返回下一节点；9月1日起返回 `due`。

- [ ] **Step 4: 运行测试确认通过**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_financial_report_check`

Expected: PASS。

### Task 2: Streamlit检查卡

**Files:**
- Modify: `app.py`
- Modify: `tests/test_policy_page.py`

**Interfaces:**
- Consumes: `build_financial_report_check(date.today()) -> dict`。
- Produces: `_render_financial_report_check()`，在半年买入计划汇总指标后渲染卡片。

- [ ] **Step 1: 写失败展示契约测试**

断言 `app.py` 包含“财报检查”“检查日期不是买入日期”和 `_render_financial_report_check()` 调用。

- [ ] **Step 2: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_policy_page.PolicyPageTests.test_purchase_plan_contains_financial_report_check_card`

Expected: FAIL，因为页面尚未包含检查卡。

- [ ] **Step 3: 实现最小渲染函数并接入页面**

使用现有 `st.container(border=True)`、`st.info`/`st.warning` 和两列布局展示当前检查点、三条时间线及两类披露窗口；不增加按钮和持久化。

- [ ] **Step 4: 运行局部及全量测试**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_policy_page.PolicyPageTests.test_purchase_plan_contains_financial_report_check_card`

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests`

Expected: PASS。

### Task 3: 页面验证与状态交接

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: 运行语法检查**

Run: `.\.venv\Scripts\python.exe -m py_compile financial_report_check.py app.py`

Expected: exit 0。

- [ ] **Step 2: 验证本地页面**

启动或刷新 `http://127.0.0.1:8501`，进入“半年买入计划”，确认检查卡可见且无异常。

- [ ] **Step 3: 更新STATUS**

记录财报检查卡范围、验证结果和“不联网、不产生买卖信号”的边界。
