# 手机端“全部图表浏览”实施计划

> **给执行者：** 本计划按测试先行执行；每个任务完成后运行所列验证并提交。

## 目标

在手机只读模式增加“全部图表”页面，按标的目录顺序纵向浏览所有已有标的。临时搜索代码只能单独查看，不能进入该页面。

## 全局约束

- 仅手机只读模式显示新页面；电脑完整模式导航不变。
- 必须以 `list_instruments(include_experimental=True)` 为唯一标的来源，不能硬编码数量或代码。当前目录为 14 项，包含恒生指数和原油。
- 默认图表区间为近 6 个月；单个标的数据失败不得中断其余图表。
- 全量页不显示个人交易圆点、单标的复盘入口或长篇观察说明。
- 保留现有单标的搜索、选择和查看流程。

### Task 1: 增加手机导航常量和覆盖测试

**Files:**
- Modify: `mobile_view.py`
- Modify: `tests/test_mobile_view.py`
- Modify: `tests/test_policy_page.py`
- Add: `docs/superpowers/plans/2026-08-20-mobile-all-charts.md`（本计划文件一并提交）

1. 先更新或新增测试，断言只读导航包含“全部图表”，完整模式保持原有导航，页面排序符合当前产品结构。
2. 在 `mobile_view.py` 定义可复用的“全部图表”页面常量，并仅加入只读页面选项。
3. 调整已有页面顺序断言以反映现有“产业RS排名”页面，避免继续保留失效预期。
4. 运行：`python -W ignore -m unittest tests.test_mobile_view tests.test_policy_page`
5. 提交本任务代码、测试与计划文件。

### Task 2: 实现全量图表浏览页面和容错/刷新语义测试

**Files:**
- Modify: `app.py`
- Modify: `tests/test_mobile_app_mode.py`（或最贴切的既有应用测试文件）
- Modify: `STATUS.md`

1. 先添加覆盖全量目录顺序、临时代码排除、单标的异常继续、刷新文案/令牌语义的测试。
2. 在手机只读侧栏增加“浏览全部已有标的”按钮并跳转到新页面；单标的流程保持不变。
3. 新页面以 `list_instruments(include_experimental=True)` 的结果顺序渲染，提供全局区间切换（默认近 6 个月）、进度提示、每标的层级/名称/数据日期/RSI/收盘价/MACD/RVOL/完整 K 线图。
4. 重用现有 `load_prepared_data` 缓存和刷新令牌：普通页文案为“刷新当前数据”，全量页文案为“刷新全部图表数据”。
5. 每标的加载放入独立异常处理，失败展示简短说明后继续；全量页传递 `trades=None`。
6. 更新 `STATUS.md` 的当前完成状态和验证记录。
7. 运行相关定向测试，并提交。

## 最终验证

1. `python -m compileall app.py mobile_view.py`
2. `python -W ignore -m unittest discover -s tests -p 'test_*.py'`
3. 明确记录与本功能无关的既有买入计划断言失败；本功能涉及测试必须通过。
