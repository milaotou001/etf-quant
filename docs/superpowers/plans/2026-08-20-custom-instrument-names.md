# 自定义标的中文名称与加入反馈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 临时搜索和已加入的自定义标的以中文名称加代码显示，加入后可在边栏明确确认。

**Architecture:** `data.py` 查询 A 股或 ETF 的中文名称，失败时返回代码。共享目录保存名称；`app.py` 在搜索、标题、下拉框和成功提示中统一显示“名称（代码）”。

**Tech Stack:** Python、AKShare、Streamlit、unittest、GitHub Contents API。

## Global Constraints

- 自定义标的仍为“自定义观察”，不进入核心策略、买入计划或回测。
- 不保存令牌、口令、持仓或交易数据。
- 名称查询或目录写入失败不得伪造成功反馈。
- 每项行为先写失败测试，再写最小实现。

---

### Task 1: 解析中文名称

**Files:**
- Modify: `data.py`
- Modify: `tests/test_custom_symbol_search.py`

**Interfaces:** 新增 `lookup_cn_security_name(symbol: str) -> str`。ETF 调用 `ak.fund_etf_spot_em()`，A 股调用 `ak.stock_individual_info_em(symbol=symbol)`；异常返回代码。

- [ ] 写失败测试：ETF 的 `{"代码": ["512880"], "名称": ["证券ETF"]}` 返回“证券ETF”；A 股信息表中“股票简称”返回对应名称；网络异常返回代码。
- [ ] 运行 `..venv\Scripts\python.exe -m unittest tests.test_custom_symbol_search`，确认因缺少函数失败。
- [ ] 用 `functools.lru_cache(maxsize=128)` 实现按市场分流的名称查询和代码兜底。
- [ ] 重跑同一测试，确认通过。
- [ ] 提交：`feat: resolve Chinese names for custom symbols`。

### Task 2: 保存自定义名称

**Files:**
- Modify: `instrument_directory.py`
- Modify: `tests/test_instrument_directory.py`

**Interfaces:** 把 `add_custom_instrument(state, symbol)` 扩展为 `add_custom_instrument(state, symbol, name=None)`，新增记录保存传入名称，空名称回退为代码。

- [ ] 写失败测试：加入 `512880, "证券ETF"` 后，状态内的 `name` 为“证券ETF”。
- [ ] 运行该单测，确认现有双参数函数失败。
- [ ] 最小实现：验证代码、清理名称、保持已存在条目不重复、只新增 `symbol/name/market/category`。
- [ ] 运行 `..venv\Scripts\python.exe -m unittest tests.test_instrument_directory`，确认通过。
- [ ] 提交：`feat: persist names for custom instruments`。

### Task 3: 统一手机与电脑端展示

**Files:**
- Modify: `app.py`
- Modify: `tests/test_mobile_app_mode.py`
- Modify: `STATUS.md`

**Interfaces:** 新增 `_custom_display_name(spec)`，自定义项返回 `名称（代码）`。搜索成功时把名称放入会话状态；加入控件显示可编辑“标的名称”；`_save_directory_change` 接收可选成功提示。

- [ ] 写失败测试：页面源码调用 `lookup_cn_security_name(candidate)`、存在“标的名称”输入、存在“已加入：”提示、展示格式含代码。
- [ ] 运行该测试，确认失败。
- [ ] 搜索临时代码时用解析名创建临时 `InstrumentSpec`；在加入前允许编辑名称；写入成功后仅显示 `已加入：名称（代码）`，下拉框和页面标题使用统一展示函数。
- [ ] 运行 `..venv\Scripts\python.exe -m unittest tests.test_mobile_app_mode tests.test_custom_symbol_search tests.test_instrument_directory` 和 Streamlit `AppTest`，确认通过。
- [ ] 更新状态文件并提交：`feat: show named custom instruments in directory`。
