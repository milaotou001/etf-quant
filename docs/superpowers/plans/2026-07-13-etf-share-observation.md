# ETF Share Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cached, official SSE ETF-share observation to the four core ETFs without changing campaign or backtest behavior.

**Architecture:** Create `etf_shares.py` as an isolated data and calculation unit. It fetches missing SSE dates into one shared cache and returns a presentation-ready observation dictionary consumed by both `app.py` and `dashboard.py`.

**Tech Stack:** Python 3, pandas, AKShare, unittest, Streamlit

## Global Constraints

- Only 563360, 510300, 518880, and 588000 receive the observation.
- Use SSE official daily ETF shares through `ak.fund_etf_scale_sse(date=...)`.
- Do not change RSI thresholds, campaign rules, market-state rules, or backtests.
- Do not emit buy/sell instructions, “主力流入”, “机构抢筹”, or an estimated multiplier.
- Empty or failed refreshes must not overwrite valid cached observations.
- The ±0.5% neutral band is display-only.

---

### Task 1: Pure share-observation calculation

**Files:**
- Create: `etf_shares.py`
- Create: `tests/test_etf_shares.py`

**Interfaces:**
- Consumes: a DataFrame indexed by date with columns `symbol` and `shares`.
- Produces: `build_share_observation(history: pd.DataFrame, symbol: str, market_date: pd.Timestamp | None = None) -> dict | None`.

- [ ] **Step 1: Write failing calculation and classification tests**

```python
class ShareObservationTests(unittest.TestCase):
    def test_calculates_daily_five_and_twenty_period_changes(self):
        history = make_history("563360", [100 + i for i in range(21)])
        result = build_share_observation(history, "563360", history.index[-1])
        self.assertAlmostEqual(result["daily_change_pct"], 100 / 120)
        self.assertAlmostEqual(result["change_5d_pct"], 500 / 115)
        self.assertAlmostEqual(result["change_20d_pct"], 20.0)

    def test_classifies_stable_before_direction(self):
        history = make_history("563360", [100.0] * 19 + [100.2, 100.4])
        result = build_share_observation(history, "563360", history.index[-1])
        self.assertEqual(result["state"], "基本平稳")

    def test_reports_insufficient_twenty_day_history(self):
        history = make_history("563360", [100, 101, 102, 103, 104, 105])
        result = build_share_observation(history, "563360", history.index[-1])
        self.assertIsNone(result["change_20d_pct"])
        self.assertEqual(result["state"], "数据不足")
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_etf_shares -v`

Expected: FAIL because `etf_shares` does not exist.

- [ ] **Step 3: Implement the pure calculation**

```python
CORE_SSE_ETFS = {"563360", "510300", "518880", "588000"}
NEUTRAL_BAND_PCT = 0.5

def _period_change(values: pd.Series, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    base = values.iloc[-1 - periods]
    if pd.isna(base) or base == 0:
        return None
    return (values.iloc[-1] / base - 1) * 100

def _classify(change_5d: float | None, change_20d: float | None) -> str:
    if change_5d is None or change_20d is None:
        return "数据不足"
    if abs(change_5d) <= NEUTRAL_BAND_PCT and abs(change_20d) <= NEUTRAL_BAND_PCT:
        return "基本平稳"
    if change_5d > 0 and change_20d > 0:
        return "中短期均增加"
    if change_5d < 0 and change_20d < 0:
        return "中短期均减少"
    return "方向分化"
```

`build_share_observation` filters the symbol, sorts and deduplicates dates, returns latest shares in raw units, the three percentage changes, state, SSE source, latest date, lag days, and a non-predictive explanation.

- [ ] **Step 4: Run the focused tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_etf_shares -v`

Expected: all calculation tests PASS.

---

### Task 2: Shared SSE cache with safe fallback

**Files:**
- Modify: `etf_shares.py`
- Modify: `tests/test_etf_shares.py`

**Interfaces:**
- Produces: `load_share_observation(symbol: str, trading_dates: pd.Index, force_refresh: bool = False, cache_path: str | None = None, fetcher: Callable | None = None) -> dict | None`.
- Cache schema: `date,symbol,name,etf_type,shares` stored at `cache/sse_etf_shares.csv`.

- [ ] **Step 1: Write failing cache tests**

```python
def test_fetches_each_missing_date_once_and_reuses_all_symbols(self):
    calls = []
    def fake_fetcher(date):
        calls.append(date)
        return sse_day(date, {"563360": 100, "510300": 200})
    first = load_share_observation("563360", dates, cache_path=path, fetcher=fake_fetcher)
    second = load_share_observation("510300", dates, cache_path=path, fetcher=fake_fetcher)
    self.assertEqual(calls, [d.strftime("%Y%m%d") for d in dates])
    self.assertIsNotNone(first)
    self.assertIsNotNone(second)

def test_empty_refresh_does_not_overwrite_cache(self):
    seed_cache(path)
    result = load_share_observation("563360", dates, True, path, lambda date: pd.DataFrame())
    self.assertEqual(result["latest_shares"], 120.0)
    self.assertEqual(result["freshness"], "cached")
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv\Scripts\python.exe -m unittest tests.test_etf_shares -v`

Expected: FAIL because the loader is missing.

- [ ] **Step 3: Implement normalization, merge, and metadata**

```python
def fetch_sse_share_date(date: pd.Timestamp) -> pd.DataFrame:
    raw = ak.fund_etf_scale_sse(date=date.strftime("%Y%m%d"))
    if raw.empty:
        return pd.DataFrame(columns=CACHE_COLUMNS)
    result = raw.rename(columns={
        "统计日期": "date", "基金代码": "symbol", "基金简称": "name",
        "ETF类型": "etf_type", "基金份额": "shares",
    })[CACHE_COLUMNS]
    result["date"] = pd.to_datetime(result["date"])
    result["symbol"] = result["symbol"].astype(str).str.zfill(6)
    return result
```

The loader limits input to the latest 25 unique trading dates, reads any existing cache, fetches only missing dates, merges successful non-empty results, writes atomically via a temporary file and `os.replace`, and returns cached data when all refreshes fail. Metadata fields are `freshness`, `refresh_error`, `requested_market_date`, and `lag_days`.

- [ ] **Step 4: Run focused tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_etf_shares -v`

Expected: all cache and fallback tests PASS.

---

### Task 3: Streamlit and CLI integration

**Files:**
- Modify: `app.py`
- Modify: `dashboard.py`
- Modify: `tests/test_etf_shares.py`

**Interfaces:**
- `app._render_share_observation(observation: dict | None) -> None`
- `dashboard.show(..., share_observation: dict | None = None)` remains backward compatible.

- [ ] **Step 1: Add failing presentation-contract tests**

```python
def test_explanation_never_claims_price_prediction(self):
    result = build_share_observation(make_history("563360", range(100, 121)), "563360")
    self.assertIn("不等于价格必然上涨", result["explanation"])
    self.assertNotIn("主力", result["explanation"])

def test_experimental_symbol_returns_none(self):
    self.assertIsNone(load_share_observation("HSI", dates, cache_path=path, fetcher=fake_fetcher))
```

- [ ] **Step 2: Run and confirm the new assertions fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_etf_shares -v`

Expected: FAIL on the missing non-predictive explanation or unsupported-symbol guard.

- [ ] **Step 3: Integrate the observation**

In `app.py`, cache the loader for 300 seconds, call it only when `spec.is_core`, render four neutral metrics and the source/date/freshness caption below campaign status, and show a spinner only during missing-date backfill.

In `dashboard.py`, load or accept the same observation for core ETFs and print:

```text
  ── ETF 份额观察（不参与战役） ──
  中短期均增加
  最新份额 234.08 亿份 | 当日 -0.06% | 近5日 +3.10% | 近20日 +6.45%
  上交所官方日频基金份额 · 数据日 2026-07-10 · 已刷新
  份额增加只表示ETF创建份额上升，不等于价格必然上涨。
```

- [ ] **Step 4: Run integration and regression tests**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all existing and new tests PASS.

---

### Task 4: Verification and project status

**Files:**
- Modify: `STATUS.md`
- Modify: `PROJECT_CONTEXT.md`

- [ ] **Step 1: Run syntax and whitespace checks**

Run: `.venv\Scripts\python.exe -m py_compile etf_shares.py app.py dashboard.py main.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 2: Verify four core CLIs**

Run each core symbol with `.venv\Scripts\python.exe main.py --symbol <symbol> --no-plot`.

Expected: each output includes `ETF 份额观察（不参与战役）`; campaign output remains present and unchanged.

- [ ] **Step 3: Verify the Streamlit page**

Run: `powershell -ExecutionPolicy Bypass -File .\start_app.ps1`

Expected: the local page loads, the four core ETFs show the share observation, experimental instruments do not, and no page error appears.

- [ ] **Step 4: Update project records**

Add the official SSE daily-share source and observation-only decision to `PROJECT_CONTEXT.md`. Record implementation, tests, and current limitations in `STATUS.md` without rewriting unrelated history.

- [ ] **Step 5: Final regression**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all tests PASS after documentation changes.
