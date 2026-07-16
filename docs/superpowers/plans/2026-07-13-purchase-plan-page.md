# 半年买入计划第五页实施计划

> 面向达达：在现有 Streamlit 应用中新增独立的第五页“半年买入计划”，保留原有四页结构与行为。

## 目标

把已经确认的半年分批买入方案做成一个轻量、可点击、可持久化的页面。计划账本与交割单缓存分开保存；手动确认只代表“已买入·待对账”，上传新交割单后再用真实成交补全同一格。实时仓位只用于观察，不反向修改固定计划。

## 约束

- 不自动下单，不增加卖出策略，不接分钟级行情。
- 不覆盖现有 `private_data/trades.json` 的用途，也不让上传交割单覆盖计划账本。
- 原有四个页面与现有 ETF 份额观察改动保持不变。
- 本次不提交 Git；只修改并验证工作区，最终更新 `STATUS.md`。

---

### 任务 1：建立计划账本领域模型和本地持久化

**文件：**

- 新建：`purchase_plan.py`
- 新建：`tests/test_purchase_plan.py`

1. 先写失败测试，覆盖默认计划：A500 6 笔 × 3750 元、沪深300 6 笔 × 3750 元、黄金 12 笔 × 2500 元（2026-07-10 至 2026-09-25 每周五）、科创50 6 笔 × 2552.50 元；黄金首笔默认为“已买入·待对账”。
2. 写失败测试，覆盖计划中 → 已买入·待对账、撤销回计划中、已对账不可再手动标记等状态转换。
3. 实现固定常量与默认账本：

```python
PLAN_BASE_AMOUNT = 285_000.0
STATUS_PLANNED = "planned"
STATUS_PENDING = "pending_reconciliation"
STATUS_RECONCILED = "reconciled"

TARGETS = {
    "563360": {"name": "A500", "target": 57_000.0, "color": "#2f855a"},
    "510300": {"name": "沪深300", "target": 57_000.0, "color": "#2563eb"},
    "518880": {"name": "黄金", "target": 57_000.0, "color": "#d69e2e"},
    "588000": {"name": "科创50", "target": 28_500.0, "color": "#7c3aed"},
}
```

4. 实现 `default_purchase_plan()`、`load_purchase_plan()`、`save_purchase_plan()`、`mark_item_bought()`、`undo_item_mark()`；采用临时文件 + `os.replace` 原子写入 `private_data/purchase_plan.json`。
5. 运行：`.venv\Scripts\python.exe -m unittest tests.test_purchase_plan -v`。

### 任务 2：从交割单保留现金快照，并计算真实剩余持仓

**文件：**

- 修改：`trades.py`
- 修改：`tests/test_trades.py`

1. 先写失败测试，覆盖从同一张交割单读取最后一条有效“资金余额”和日期。
2. 先写失败测试，覆盖买卖后剩余数量按交易方向净额计算，且四个标的分别计算，不平均拆分宽基金额。
3. 新增 `ACCOUNT_SNAPSHOT_PATH = private_data/account_snapshot.json`，实现 `extract_account_snapshot(df)`、`save_account_snapshot()`、`load_account_snapshot()`。
4. 调整 `update_trade_cache()`：Excel 只读取一次，同时更新真实交易缓存和现金快照；若交易解析失败，原缓存仍不改变。
5. 保持 `parse_statement()`、`load_trade_cache()` 等现有接口兼容。
6. 运行：`.venv\Scripts\python.exe -m unittest tests.test_trades -v`。

### 任务 3：加入轻量对账和仓位观察计算

**文件：**

- 修改：`purchase_plan.py`
- 修改：`tests/test_purchase_plan.py`

1. 先写失败测试：同标的、同确认日期只有一笔买入时，自动补全实际日期、数量、价格、金额并改成已对账。
2. 先写失败测试：同日存在多笔可能成交或无法明确对应时，不静默归类，格子显示 `needs_confirmation=True`。
3. 实现 `reconcile_purchase_plan(plan, trades)`，只采用“标的 + 日期 + 唯一候选”的保守规则；不做复杂队列。
4. 实现 `calculate_open_quantity(entries)` 与 `build_position_progress(plan, trades, latest_prices)`：

```python
display_value = open_quantity * latest_price + pending_plan_amount
gap = max(target_amount - display_value, 0.0)
is_overweight = display_value > target_amount
```

5. 测试固定目标长度、待对账暂估计入、黄金超配只提示不报错、实时缺口不改变计划金额。
6. 运行：`.venv\Scripts\python.exe -m unittest tests.test_purchase_plan -v`。

### 任务 4：实现第五页 Streamlit 界面

**文件：**

- 修改：`app.py`

1. 在侧边栏页面列表末尾加入“半年买入计划”，不调整原四页顺序。
2. 新增 `_render_purchase_plan(...)`：顶部显示计划总额、已确认金额、计划剩余和对账提示。
3. 每个标的独立成行，行头用固定颜色；每个计划格直接使用整格 `st.button`，标签按状态显示计划金额、日期/轮次、待对账或真实成交摘要。黄金 12 笔为保证可读性分两排展示，但仍属于同一标的一行区域。
4. 点击格子后使用 `st.dialog` 显示标的、笔数、计划金额和确认日期；确认后写入计划账本并 `st.rerun()`。待对账格提供简单撤销入口；已对账格不再触发买入确认。
5. 使用只读 HTML 进度条分别展示 A500（绿）、沪深300（蓝）、黄金（黄）、科创50（紫）；条长固定为理想金额，深色为已拥有/待对账暂估，浅色为缺口。黄金超目标显示“超配”。
6. 现金/其他卡片展示理想 30%（85,500 元）、最近交割单资金余额及数据日期；无快照时显示“待读取”。
7. 页面进入时加载四只核心 ETF 的最新价格。任一行情暂不可用时，只让对应进度条显示价格不可用，不阻断计划表的手动操作。
8. 上传新交割单后自动运行轻量对账并保存计划账本；计划文件不被替换。

### 任务 5：整体回归、视觉检查和状态交接

**文件：**

- 修改：`STATUS.md`
- 按需要修改：`PROJECT_CONTEXT.md`（只记录长期事实）

1. 运行完整单元测试：`.venv\Scripts\python.exe -m unittest discover -s tests -v`。
2. 运行语法验证：`.venv\Scripts\python.exe -m py_compile app.py trades.py purchase_plan.py`。
3. 启动 Streamlit，在浏览器中检查：第五页可进入、四行不混淆、沪深300为蓝色、格子可点击、确认框可用、刷新后状态保留、原四页可进入。
4. 用临时路径测试持久化，避免验证过程污染达达的真实 `private_data/purchase_plan.json`；不上传或保存原始交割单。
5. 在 `STATUS.md` 记录完成项、验证命令、尚存限制和下一步；若页面规则成为长期项目事实，再同步到 `PROJECT_CONTEXT.md`。

