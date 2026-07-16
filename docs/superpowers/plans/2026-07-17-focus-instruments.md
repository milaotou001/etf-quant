# 重点观察标的 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 561380、516150、159570、159819 纳入标的目录，并在选择器中把前三只显示为“重点”。

**Architecture:** 在不可变的 `InstrumentSpec` 上增加独立的 `is_focus` 字段和可测试的 `display_tier` 属性。标的目录负责定义重点状态，Streamlit 选择器只消费 `display_tier`，不把显示优先级与正式策略能力耦合。

**Tech Stack:** Python 3、dataclasses、Streamlit、unittest

## Global Constraints

- 561380、516150、159570 为重点观察，159819 为普通观察。
- 四只标的均保持 `is_core=False`，不得启用正式 RSI 战役、回测或买入计划。
- 不修改战略方向页的双确认状态或正式白名单。
- 不重构无关代码。

---

### Task 1: 标的重点状态与选择器标签

**Files:**
- Modify: `tests/test_instruments.py`
- Modify: `instruments.py`
- Modify: `app.py`
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: `InstrumentSpec`、`get_instrument()`、`list_instruments()`
- Produces: `InstrumentSpec.is_focus: bool`、`InstrumentSpec.display_tier: str`

- [x] **Step 1: 写入失败测试**

在 `tests/test_instruments.py` 增加：

```python
def test_focus_watchlist_symbols_are_labeled_without_strategy_rules(self):
    expected = {
        "561380": "电网设备 ETF",
        "516150": "稀土 ETF",
        "159570": "港股创新药 ETF",
    }
    for symbol, name in expected.items():
        spec = get_instrument(symbol)
        self.assertEqual(spec.name, name)
        self.assertTrue(spec.is_focus)
        self.assertEqual(spec.display_tier, "重点")
        self.assertFalse(spec.is_core)
        self.assertFalse(spec.supports_campaign)
        self.assertFalse(spec.supports_backtest)

    ai = get_instrument("159819")
    self.assertFalse(ai.is_focus)
    self.assertEqual(ai.display_tier, "观察")
    self.assertEqual(get_instrument("510300").display_tier, "核心")
```

- [x] **Step 2: 运行测试并确认按预期失败**

运行：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_instruments.InstrumentRegistryTests.test_focus_watchlist_symbols_are_labeled_without_strategy_rules -v
```

预期：因 561380 尚未注册或 `is_focus` 尚不存在而失败。

- [x] **Step 3: 写入最小实现**

在 `InstrumentSpec` 最后增加字段及属性：

```python
is_focus: bool = False

@property
def display_tier(self) -> str:
    if self.is_core:
        return "核心"
    if self.is_focus:
        return "重点"
    return "观察"
```

在核心标的之后注册：

```python
InstrumentSpec("561380", "电网设备 ETF", "CN", "重点观察", False, is_focus=True),
InstrumentSpec("516150", "稀土 ETF", "CN", "重点观察", False, is_focus=True),
InstrumentSpec("159570", "港股创新药 ETF", "CN", "重点观察", False, is_focus=True),
```

保留 159819 为普通观察。在 `app.py` 中将标的格式化改为：

```python
format_func=lambda key: f"{spec_by_symbol[key].display_tier} · {spec_by_symbol[key].name}"
```

- [x] **Step 4: 运行定向测试确认通过**

运行：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_instruments -v
```

预期：标的目录测试全部通过。

- [x] **Step 5: 运行完整回归与语法检查**

运行：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m py_compile instruments.py app.py
```

预期：完整测试零失败，语法检查退出码为 0。

- [x] **Step 6: 更新项目状态**

在 `STATUS.md` 顶部记录四只新增观察标的、三只重点标记、159819 普通观察及策略边界，并运行 `git diff --check`。

- [ ] **Step 7: 提交本次功能**

只暂存本任务文件：

```powershell
git add -- instruments.py app.py tests/test_instruments.py STATUS.md docs/superpowers/plans/2026-07-17-focus-instruments.md
git commit -m "feat: add focus watchlist instruments"
```
