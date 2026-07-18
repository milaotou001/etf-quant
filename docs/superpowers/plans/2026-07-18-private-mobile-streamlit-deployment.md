# Private Mobile Streamlit Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a private, phone-friendly Streamlit view that shows live daily RSI, charts, and the current purchase plan without exposing or mutating local brokerage data.

**Architecture:** Keep the existing local Streamlit application as the only source of indicator and plan presentation logic. Add an explicit environment-driven cloud read-only mode, load a version-checked purchase-plan snapshot from Streamlit Secrets, and remove every private write path from the cloud navigation and render flow. Deploy the same `app.py` from a private GitHub repository to Streamlit Community Cloud; use Aliyun only as a later fallback if domestic market-data access proves unreliable.

**Tech Stack:** Python 3.11, Streamlit 1.58.0, pandas 3.0.3, AKShare 1.18.64, `unittest`, Streamlit Community Cloud, GitHub CLI.

## Global Constraints

- Cloud mode is private and view-only: no statement upload, purchase marking, journal writes, trade-cache writes, or plan writes.
- Local mode retains all current features and remains the default when `MOBILE_READ_ONLY` is absent.
- RSI continues to use `data.py`, `indicators.py`, and the current instrument catalog; do not introduce a second calculation path.
- The cloud plan comes only from `PURCHASE_PLAN_B64` in Streamlit Secrets and never silently falls back to `default_purchase_plan()`.
- The plan snapshot is manually refreshed; do not add a database, object store, broker API, or automatic synchronization.
- Do not deploy to Vercel, add a custom domain, or build additional CI/CD in this version.
- Do not stage or deploy `private_data/`, `journal/`, `cache/`, statements, trade CSV files, photos, logs, `tmp/`, or secrets.
- Preserve all unknown workspace changes and never use destructive Git commands.

---

### Task 0: Capture the verified application baseline

**Files:**
- Modify: none
- Verify and commit only the already-completed application files listed below

**Interfaces:**
- Consumes: the current dirty workspace documented in `STATUS.md`
- Produces: a deployable Git baseline in which every module imported by `app.py` is tracked

- [ ] **Step 1: Audit the existing workspace without staging anything**

Run:

```powershell
git status --short --branch
git diff --stat
git ls-files --error-unmatch financial_report_check.py portfolio_review.py
```

Expected: the first two commands show the completed financial-check, portfolio-review, and ETF-catalog work; the last command currently fails because the two runtime modules are still untracked. Confirm that none of the untracked research scripts, photos, statements, `tmp/`, or private data belongs in the baseline commit.

- [ ] **Step 2: Verify the current baseline before preserving it**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py financial_report_check.py portfolio_review.py instruments.py purchase_plan.py trades.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
```

Expected: compilation succeeds, the existing 106 tests pass, and `git diff --check` reports no whitespace errors.

- [ ] **Step 3: Stage only the completed runtime, test, and project-state files**

Run:

```powershell
git add -- PROJECT_CONTEXT.md STATUS.md app.py financial_report_check.py portfolio_review.py instruments.py purchase_plan.py trades.py tests/test_financial_report_check.py tests/test_portfolio_review.py tests/test_instruments.py tests/test_policy_page.py tests/test_purchase_plan.py tests/test_trades.py docs/superpowers/specs/2026-07-18-financial-report-check-card-design.md docs/superpowers/plans/2026-07-18-financial-report-check-card.md docs/superpowers/plans/2026-07-18-portfolio-review-clarity.md
git diff --cached --name-status
```

Expected: the staged list contains only the named source, tests, documentation, and project-state files. It must not contain `.superpowers/`, `scripts/`, `tmp/`, `恒生/`, `科技/`, `.xlsx`, `.csv`, logs, or private data.

- [ ] **Step 4: Commit the baseline**

Run:

```powershell
git commit -m "feat: complete decision dashboard updates"
```

Expected: one commit containing the already-verified dashboard work; unrelated untracked files remain untouched.

---

### Task 1: Add explicit mobile read-only configuration and snapshot codec

**Files:**
- Create: `mobile_view.py`
- Create: `tests/test_mobile_view.py`

**Interfaces:**
- Consumes: `purchase_plan.CURRENT_PLAN_VERSION`
- Produces: `MobileViewConfigError`, `is_mobile_read_only(env)`, `mobile_page_options(read_only)`, `primary_metric_order(read_only)`, `encode_plan_snapshot(plan)`, and `load_mobile_plan(env)`

- [ ] **Step 1: Write the failing configuration and snapshot tests**

Create `tests/test_mobile_view.py`:

```python
import copy
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from mobile_view import (
    MobileViewConfigError,
    encode_plan_snapshot,
    is_mobile_read_only,
    load_mobile_plan,
    mobile_page_options,
    primary_metric_order,
)
from purchase_plan import CURRENT_PLAN_VERSION, default_purchase_plan


class MobileViewTests(unittest.TestCase):
    def test_local_mode_is_default_and_keeps_full_navigation(self):
        self.assertFalse(is_mobile_read_only({}))
        self.assertEqual(
            mobile_page_options(False),
            ["状态与图表", "复盘日志", "策略回测", "策略规则", "半年买入计划", "组合复盘", "战略方向"],
        )
        self.assertEqual(primary_metric_order(False), ["price", "rsi", "macd", "rvol"])

    def test_cloud_mode_has_only_market_and_plan_and_prioritizes_rsi(self):
        self.assertTrue(is_mobile_read_only({"MOBILE_READ_ONLY": "true"}))
        self.assertEqual(mobile_page_options(True), ["状态与图表", "半年买入计划"])
        self.assertEqual(primary_metric_order(True), ["rsi", "price", "macd", "rvol"])

    def test_invalid_mode_value_fails_closed(self):
        with self.assertRaisesRegex(MobileViewConfigError, "MOBILE_READ_ONLY"):
            is_mobile_read_only({"MOBILE_READ_ONLY": "sometimes"})

    def test_plan_snapshot_round_trip_preserves_current_plan(self):
        plan = default_purchase_plan()
        encoded = encode_plan_snapshot(plan)
        self.assertEqual(
            load_mobile_plan({"PURCHASE_PLAN_B64": encoded}),
            plan,
        )

    def test_missing_or_invalid_snapshot_never_uses_default_plan(self):
        with self.assertRaisesRegex(MobileViewConfigError, "PURCHASE_PLAN_B64"):
            load_mobile_plan({})
        with self.assertRaisesRegex(MobileViewConfigError, "解码"):
            load_mobile_plan({"PURCHASE_PLAN_B64": "not-base64"})

    def test_wrong_plan_version_is_rejected(self):
        plan = copy.deepcopy(default_purchase_plan())
        plan["version"] = CURRENT_PLAN_VERSION + 1
        with self.assertRaisesRegex(MobileViewConfigError, "版本"):
            encode_plan_snapshot(plan)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_view -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mobile_view'`.

- [ ] **Step 3: Implement the minimal configuration and codec module**

Create `mobile_view.py`:

```python
"""Pure configuration helpers for the private mobile Streamlit view."""
from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping

from purchase_plan import CURRENT_PLAN_VERSION


FULL_PAGE_OPTIONS = [
    "状态与图表",
    "复盘日志",
    "策略回测",
    "策略规则",
    "半年买入计划",
    "组合复盘",
    "战略方向",
]
READ_ONLY_PAGE_OPTIONS = ["状态与图表", "半年买入计划"]


class MobileViewConfigError(ValueError):
    """Raised when cloud read-only configuration is absent or unsafe."""


def is_mobile_read_only(env: Mapping[str, object]) -> bool:
    raw = env.get("MOBILE_READ_ONLY")
    if raw is None:
        return False
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise MobileViewConfigError("MOBILE_READ_ONLY 必须是 true 或 false")


def mobile_page_options(read_only: bool) -> list[str]:
    return list(READ_ONLY_PAGE_OPTIONS if read_only else FULL_PAGE_OPTIONS)


def primary_metric_order(read_only: bool) -> list[str]:
    return ["rsi", "price", "macd", "rvol"] if read_only else ["price", "rsi", "macd", "rvol"]


def _validate_plan(plan: object) -> dict:
    if not isinstance(plan, dict) or not isinstance(plan.get("assets"), dict):
        raise MobileViewConfigError("计划快照缺少 assets")
    if plan.get("version") != CURRENT_PLAN_VERSION:
        raise MobileViewConfigError(
            f"计划快照版本不兼容：需要 {CURRENT_PLAN_VERSION}，实际 {plan.get('version')}"
        )
    return plan


def encode_plan_snapshot(plan: dict) -> str:
    validated = _validate_plan(plan)
    payload = json.dumps(validated, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


def load_mobile_plan(env: Mapping[str, object]) -> dict:
    encoded = env.get("PURCHASE_PLAN_B64")
    if not encoded:
        raise MobileViewConfigError("云端缺少 PURCHASE_PLAN_B64 计划快照")
    try:
        payload = base64.b64decode(str(encoded).encode("ascii"), validate=True)
        plan = json.loads(payload.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise MobileViewConfigError("PURCHASE_PLAN_B64 解码失败") from exc
    return _validate_plan(plan)
```

- [ ] **Step 4: Run the new tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_view -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit the configuration boundary**

Run:

```powershell
git add -- mobile_view.py tests/test_mobile_view.py
git commit -m "feat: add private mobile runtime config"
```

---

### Task 2: Export the private plan snapshot without exposing it to Git

**Files:**
- Create: `scripts/export_mobile_plan_secret.py`
- Create: `tests/test_mobile_plan_export.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `mobile_view.encode_plan_snapshot(plan)` and `purchase_plan.load_purchase_plan(path)`
- Produces: `build_secrets_toml(plan) -> str` and a local ignored `private_data/mobile_streamlit_secrets.toml`

- [ ] **Step 1: Write the failing exporter tests**

Create `tests/test_mobile_plan_export.py`:

```python
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from mobile_view import load_mobile_plan
from purchase_plan import default_purchase_plan, save_purchase_plan
from scripts.export_mobile_plan_secret import build_secrets_toml, export_secret_file


class MobilePlanExportTests(unittest.TestCase):
    def test_generated_toml_round_trips_the_plan(self):
        plan = default_purchase_plan()
        parsed = tomllib.loads(build_secrets_toml(plan))
        self.assertEqual(parsed["MOBILE_READ_ONLY"], "true")
        self.assertEqual(load_mobile_plan(parsed), plan)

    def test_export_refuses_a_missing_private_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "purchase_plan"):
                export_secret_file(
                    Path(directory, "missing-purchase_plan.json"),
                    Path(directory, "secrets.toml"),
                )

    def test_export_writes_only_the_secret_file(self):
        plan = default_purchase_plan()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "purchase_plan.json")
            target = Path(directory, "mobile_streamlit_secrets.toml")
            save_purchase_plan(plan, str(source))
            export_secret_file(source, target)
            self.assertEqual(load_mobile_plan(tomllib.loads(target.read_text(encoding="utf-8"))), plan)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm the exporter is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_plan_export -v
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.export_mobile_plan_secret`.

- [ ] **Step 3: Implement the exporter**

Create `scripts/export_mobile_plan_secret.py`:

```python
"""Create an ignored Streamlit Secrets payload from the current private plan."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mobile_view import encode_plan_snapshot
from purchase_plan import PURCHASE_PLAN_PATH, load_purchase_plan

DEFAULT_TARGET = PROJECT_ROOT / "private_data" / "mobile_streamlit_secrets.toml"


def build_secrets_toml(plan: dict) -> str:
    encoded = encode_plan_snapshot(plan)
    return f'MOBILE_READ_ONLY = "true"\nPURCHASE_PLAN_B64 = "{encoded}"\n'


def export_secret_file(source: Path, target: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"purchase_plan not found: {source}")
    plan = load_purchase_plan(str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(build_secrets_toml(plan), encoding="utf-8")
    os.replace(temporary, target)
    return target


def main() -> None:
    target = export_secret_file(Path(PURCHASE_PLAN_PATH), DEFAULT_TARGET)
    print(f"Streamlit Secret 已生成：{target}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Harden ignore rules for every known private deployment artifact**

Append these exact entries to `.gitignore`:

```gitignore
.streamlit/secrets.toml
tmp/
恒生/
科技/
scripts/_jiaogedan_raw.csv
普通账户电子对账单*.xlsx
```

Keep the existing `private_data/`, `journal/`, `cache/`, and log exclusions.

- [ ] **Step 5: Run exporter and privacy tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_plan_export -v
.\.venv\Scripts\python.exe scripts/export_mobile_plan_secret.py
git check-ignore -- private_data/mobile_streamlit_secrets.toml "普通账户电子对账单_20260713161919.xlsx" "科技/IMG_4547.JPG" "恒生/IMG_4540.PNG" scripts/_jiaogedan_raw.csv
git status --short
```

Expected: 3 tests pass; the exporter prints only the ignored target path; `git check-ignore` prints all five paths; neither the generated secret nor the private files appears as a staged change.

- [ ] **Step 6: Commit the exporter and ignore rules**

Run:

```powershell
git add -- .gitignore scripts/export_mobile_plan_secret.py tests/test_mobile_plan_export.py
git commit -m "feat: export private mobile plan snapshot"
```

---

### Task 3: Gate the Streamlit application into local-full and cloud-read-only flows

**Files:**
- Modify: `app.py:1-80`
- Modify: `app.py:403-520`
- Modify: `app.py:723-800`
- Create: `tests/test_mobile_app_mode.py`
- Modify: `tests/test_policy_page.py:78-89`

**Interfaces:**
- Consumes: `is_mobile_read_only(os.environ)`, `mobile_page_options(read_only)`, and `load_mobile_plan(os.environ)` from Task 1
- Produces: `_render_asset_plan_row(..., read_only=False)` and `_render_purchase_plan(..., read_only=False)`; cloud execution never calls private loaders or writers

- [ ] **Step 1: Write failing source-boundary tests**

Create `tests/test_mobile_app_mode.py`:

```python
import os
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MobileAppModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(PROJECT_ROOT, "app.py").read_text(encoding="utf-8")

    def test_navigation_comes_from_runtime_mode(self):
        self.assertIn("MOBILE_READ_ONLY = is_mobile_read_only(os.environ)", self.source)
        self.assertIn("mobile_page_options(MOBILE_READ_ONLY)", self.source)

    def test_private_controls_are_inside_local_only_branch(self):
        branch = self.source.index("if not MOBILE_READ_ONLY:")
        uploader = self.source.index("st.file_uploader", branch)
        cloud_plan = self.source.index("load_mobile_plan(os.environ)", uploader)
        self.assertLess(branch, uploader)
        self.assertLess(uploader, cloud_plan)

    def test_cloud_plan_render_is_explicitly_read_only(self):
        self.assertIn("read_only=MOBILE_READ_ONLY", self.source)
        self.assertIn("if read_only:", self.source)
        self.assertIn("手机只读快照", self.source)

    def test_cloud_branch_does_not_reconcile_or_save(self):
        start = self.source.index("if MOBILE_READ_ONLY:", self.source.index('if page == "半年买入计划"'))
        end = self.source.index("else:", start)
        branch = self.source[start:end]
        self.assertNotIn("reconcile_purchase_plan", branch)
        self.assertNotIn("save_purchase_plan", branch)
        self.assertNotIn("load_trade_cache", branch)


if __name__ == "__main__":
    unittest.main()
```

Update `tests/test_policy_page.py` so the navigation test imports and checks the shared constant instead of searching for an inline list:

```python
from mobile_view import FULL_PAGE_OPTIONS

# Inside test_main_app_lists_review_before_strategy_and_routes_strategy_before_market_data:
self.assertEqual(
    FULL_PAGE_OPTIONS,
    ["状态与图表", "复盘日志", "策略回测", "策略规则", "半年买入计划", "组合复盘", "战略方向"],
)
self.assertIn("mobile_page_options(MOBILE_READ_ONLY)", source)
```

- [ ] **Step 2: Run the new boundary tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_app_mode tests.test_policy_page -v
```

Expected: the new mobile tests fail because `app.py` still exposes the full local flow unconditionally.

- [ ] **Step 3: Add runtime imports and select navigation from the explicit mode**

Add imports near the top of `app.py`:

```python
import html
import os

from mobile_view import (
    MobileViewConfigError,
    is_mobile_read_only,
    load_mobile_plan,
    mobile_page_options,
)
```

After the CSS block, initialize the mode and fail closed on invalid configuration:

```python
try:
    MOBILE_READ_ONLY = is_mobile_read_only(os.environ)
except MobileViewConfigError as exc:
    st.error(f"手机只读配置错误：{exc}")
    st.stop()
```

Replace the inline radio list with:

```python
page = st.radio("页面", mobile_page_options(MOBILE_READ_ONLY))
```

- [ ] **Step 4: Put every private sidebar control and trade-cache action behind the local-only branch**

Use this exact flow in the sidebar and immediately after it:

```python
show_trades = False
uploaded_statement = None
if not MOBILE_READ_ONLY:
    show_trades = st.checkbox("显示个人交易记录")
    uploaded_statement = st.file_uploader(
        "更新电子对账单（可选）",
        type=["xlsx"],
        disabled=page == "战略方向" or (not show_trades and page not in {"半年买入计划", "组合复盘"}),
    )
    st.caption("解析后的记录会跨页面和重启保留；新对账单更新交易与现金，不会覆盖买入计划。")
else:
    st.caption("手机只读模式 · 不上传对账单，不修改计划")

trade_cache = {}
if not MOBILE_READ_ONLY:
    trade_cache = load_trade_cache()
    if uploaded_statement is not None:
        upload_hash = hashlib.sha256(uploaded_statement.getvalue()).hexdigest()
        if st.session_state.get("trade_upload_hash") != upload_hash:
            try:
                trade_cache = update_trade_cache(uploaded_statement)
                st.session_state.trade_upload_hash = upload_hash
                st.session_state.trade_cache_notice = "对账单已更新，已替换本机缓存。"
            except Exception as exc:
                st.warning(f"未能更新对账单：{exc}")
        else:
            trade_cache = load_trade_cache()
```

Do not change the current `if show_trades:` caption block; it remains unreachable in cloud mode because `show_trades` is initialized to `False` and the checkbox is not rendered.

- [ ] **Step 5: Render plan cells as non-interactive content in cloud mode**

Change the plan-row signature, then insert the read-only branch immediately after `items = asset.get("items", [])` and before the existing six-column loop:

```python
def _render_asset_plan_row(symbol: str, asset: dict, read_only: bool = False) -> None:
    with st.container(border=True):
        color = asset["color"]
        target_text = f"理想仓位 {_money(asset['target'])}"
        if asset.get("reserved_amount"):
            target_text += f" · 后续预留 {_money(asset['reserved_amount'])}"
        st.markdown(
            f"<div class='asset-head'><div class='asset-chip'>"
            f"<span class='asset-dot' style='background:{color}'></span>{asset['name']}"
            f"</div><div class='asset-target'>{target_text}</div></div>",
            unsafe_allow_html=True,
        )
        if asset.get("plan_note"):
            st.caption(asset["plan_note"])
        items = asset.get("items", [])
        if read_only:
            for item in items:
                label = html.escape(_plan_cell_label(symbol, item)).replace("\n", "<br>")
                st.markdown(
                    f"<div class='plan-cell-readonly'>{label}</div>",
                    unsafe_allow_html=True,
                )
            return

        for start in range(0, len(items), 6):
            batch = items[start:start + 6]
            columns = st.columns(len(batch), gap="small")
            for column, item in zip(columns, batch):
                with column:
                    clicked = st.button(
                        _plan_cell_label(symbol, item),
                        key=f"plan-cell-{item['id']}",
                        disabled=item.get("status") == STATUS_RECONCILED,
                        width="stretch",
                        help=(
                            "点击标记或撤销"
                            if item.get("status") != STATUS_RECONCILED
                            else "已由对账单补全"
                        ),
                    )
                    if clicked:
                        st.session_state.purchase_plan_item_id = item["id"]
```

Replace the complete `_render_purchase_plan` function with:

```python
def _render_purchase_plan(
    plan: dict,
    trade_cache: dict,
    latest_prices: dict,
    snapshot: dict,
    read_only: bool = False,
) -> None:
    st.title("半年买入计划")
    st.markdown(
        "<div class='plan-intro'><b>固定计划，逐笔确认</b><br>"
        "<span class='muted'>宽基目标已重分配；行业仓只列当前一轮，后续预留不计入待买金额。</span></div>",
        unsafe_allow_html=True,
    )
    summary = summarize_plan(plan)
    total, confirmed, remaining, count = st.columns(4)
    total.metric("半年计划", _money(summary["planned_total"]))
    confirmed.metric("已确认", _money(summary["confirmed_amount"]))
    remaining.metric("计划剩余", _money(summary["remaining_amount"]))
    count.metric("已完成笔数", f"{summary['confirmed_count']} / {summary['total_count']}")

    _render_financial_report_check()

    st.subheader("计划与实际成交")
    if read_only:
        st.caption("手机只读快照 · ◇ 计划中　◐ 已买入·待对账　✓ 已对账")
    else:
        st.caption("◇ 计划中　◐ 已买入·待对账　✓ 已对账。每个格子本身就是操作入口。")
    for symbol in TARGETS:
        _render_asset_plan_row(symbol, plan["assets"][symbol], read_only=read_only)

    if read_only:
        st.caption("计划变化后需重新同步只读快照；手机端不会修改本机计划。")
        return

    selected_item_id = st.session_state.get("purchase_plan_item_id")
    if selected_item_id:
        _purchase_item_dialog(plan, selected_item_id)

    progress = build_position_progress(plan, trade_cache, latest_prices)
    _render_position_progress(progress)

    cash_balance = snapshot.get("cash_balance")
    cash_date = snapshot.get("cash_date") or "暂无对账单日期"
    st.markdown(
        f"<div class='cash-card'><div class='asset-head'><div class='asset-chip'>现金 / 其他</div>"
        f"<div class='asset-target'>理想 30%</div></div><div class='cash-grid'>"
        f"<div><div class='cash-label'>理想金额</div><div class='cash-value'>{_money(plan.get('cash_target', 85_500.0))}</div></div>"
        f"<div><div class='cash-label'>最近对账单资金余额 · {cash_date}</div>"
        f"<div class='cash-value'>{_money(cash_balance)}</div></div></div></div>",
        unsafe_allow_html=True,
    )
```

- [ ] **Step 6: Split cloud and local plan loading before any reconcile/save call**

Replace the combined plan route with:

```python
if page == "半年买入计划":
    if MOBILE_READ_ONLY:
        try:
            display_plan = load_mobile_plan(os.environ)
        except MobileViewConfigError as exc:
            st.error(f"手机计划快照不可用：{exc}")
            st.stop()
        display_trade_cache = {}
        account_snapshot = {}
    else:
        plan = load_purchase_plan()
        display_plan = reconcile_purchase_plan(plan, trade_cache)
        if display_plan != plan:
            save_purchase_plan(display_plan)
        display_trade_cache = trade_cache
        account_snapshot = load_account_snapshot()

    latest_prices = {}
    unavailable = []
    for core_symbol in TARGETS:
        try:
            core_df = load_prepared_data(core_symbol, st.session_state.refresh_token)
            latest_prices[core_symbol] = float(core_df.iloc[-1]["close"])
        except Exception:
            latest_prices[core_symbol] = None
            unavailable.append(TARGETS[core_symbol]["name"])
    if unavailable:
        st.caption(f"暂未读取行情：{'、'.join(unavailable)}；计划快照仍可查看。")
    _render_purchase_plan(
        display_plan,
        display_trade_cache,
        latest_prices,
        account_snapshot,
        read_only=MOBILE_READ_ONLY,
    )
elif page == "组合复盘":
    plan = load_purchase_plan()
    reconciled_plan = reconcile_purchase_plan(plan, trade_cache)
    if reconciled_plan != plan:
        save_purchase_plan(reconciled_plan)
    _render_portfolio_review(reconciled_plan, trade_cache, st.session_state.refresh_token)
else:
    try:
        df = load_prepared_data(symbol, st.session_state.refresh_token)
    except Exception as exc:
        st.error(f"数据加载失败：{exc}")
        st.stop()

    if page == "状态与图表":
        _render_main(df, spec, trades, st.session_state.refresh_token)
    elif page == "复盘日志":
        _render_journal(df, spec)
    elif page == "策略回测":
        _render_backtest(df, spec)
    else:
        _render_rules(spec)
```

Because `mobile_page_options(True)` excludes `组合复盘`, that route is reachable only in local mode.

- [ ] **Step 7: Run targeted and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_app_mode tests.test_mobile_view tests.test_policy_page tests.test_purchase_plan -v
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m py_compile app.py mobile_view.py
```

Expected: targeted tests pass, the expanded full suite passes, and compilation succeeds.

- [ ] **Step 8: Commit the read-only application boundary**

Run:

```powershell
git add -- app.py tests/test_mobile_app_mode.py tests/test_policy_page.py
git commit -m "feat: gate private mobile read-only view"
```

---

### Task 4: Prioritize RSI and make the read-only plan legible on a phone

**Files:**
- Modify: `app.py:50-80`
- Modify: `app.py:118-143`
- Modify: `app.py:787-800`
- Modify: `tests/test_mobile_app_mode.py`

**Interfaces:**
- Consumes: `primary_metric_order(read_only)` from Task 1
- Produces: cloud-first RSI ordering, narrow-screen CSS, and the exact cloud data error heading `本次未取得行情数据`

- [ ] **Step 1: Extend tests for RSI order, narrow-screen styles, and data failure copy**

Add to `tests/test_mobile_app_mode.py`:

```python
    def test_cloud_main_view_prioritizes_rsi(self):
        self.assertIn("primary_metric_order(read_only)", self.source)
        self.assertIn('metric_columns["rsi"]', self.source)

    def test_mobile_css_and_read_only_plan_card_exist(self):
        self.assertIn("@media (max-width: 700px)", self.source)
        self.assertIn(".plan-cell-readonly", self.source)
        self.assertIn("grid-template-columns: 1fr", self.source)

    def test_cloud_data_failure_is_explicit(self):
        self.assertIn("本次未取得行情数据", self.source)
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_app_mode -v
```

Expected: the three new tests fail before the layout changes.

- [ ] **Step 3: Add the mobile CSS rules**

Add to the existing CSS block in `app.py`:

```css
.plan-cell-readonly {
  border: 1px solid #e4e7ec;
  border-left: 4px solid #1b6b5c;
  border-radius: .55rem;
  padding: .75rem .85rem;
  margin: .45rem 0;
  background: #fff;
  line-height: 1.45;
}
@media (max-width: 700px) {
  .block-container { max-width: 100%; padding: 1rem .75rem 3rem; }
  .asset-head, .progress-meta, .progress-foot { display: grid; grid-template-columns: 1fr; gap: .25rem; }
  .asset-target, .progress-number { text-align: left; }
  [data-testid="stMetric"] { padding: .55rem .65rem; }
  .plan-intro { padding: .8rem .9rem; }
  .cash-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Render cloud metrics with RSI first while preserving local order**

Import `primary_metric_order` from `mobile_view`, change the signature, and replace the fixed column assignment:

```python
def _render_main(
    df: pd.DataFrame,
    spec,
    trades: list[dict] | None,
    refresh_token: int = 0,
    read_only: bool = False,
) -> None:
    latest = df.iloc[-1]
    analysis = build_market_analysis(df)
    campaign = build_campaign_observation(df, spec)
    st.title(spec.name)
    st.caption(_data_caption(df))

    metric_columns = dict(zip(primary_metric_order(read_only), st.columns(4)))
    with metric_columns["rsi"]:
        st.metric("RSI (14)", _fmt_number(latest.get("rsi"), 0))
    with metric_columns["price"]:
        st.metric("收盘", _fmt_number(latest["close"], 4), _fmt_number(latest.get("chg"), 1, "—") + "%")
    with metric_columns["macd"]:
        hist_col = next((c for c in df.columns if c.startswith("MACDh_")), "")
        st.metric("MACD HIST", _fmt_number(latest.get(hist_col), 4))
    with metric_columns["rvol"]:
        st.metric("成交额 RVOL", _fmt_number(latest.get("rvol"), 2, "不可用"))
```

Replace only the original fixed metric block at `app.py:124-143`; the status card remains the next statement after this replacement. Call the function with:

```python
_render_main(df, spec, trades, st.session_state.refresh_token, read_only=MOBILE_READ_ONLY)
```

- [ ] **Step 5: Make a cloud cold-start failure unmistakable**

Replace the market-data exception rendering with:

```python
except Exception as exc:
    heading = "本次未取得行情数据" if MOBILE_READ_ONLY else "数据加载失败"
    st.error(f"{heading}：{exc}")
    st.stop()
```

- [ ] **Step 6: Run tests and commit the responsive view**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mobile_app_mode tests.test_mobile_view -v
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m py_compile app.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and no whitespace error is reported.

Run:

```powershell
git add -- app.py tests/test_mobile_app_mode.py
git commit -m "feat: optimize RSI and plan for phones"
```

---

### Task 5: Pin the cloud runtime and verify both application modes locally

**Files:**
- Modify: `requirements.txt`
- Modify: `PROJECT_CONTEXT.md`
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: Tasks 1-4 and local `private_data/purchase_plan.json`
- Produces: reproducible cloud dependencies and evidence that local-full behavior remains intact

- [ ] **Step 1: Pin the currently verified dependency set**

Replace `requirements.txt` with:

```text
streamlit==1.58.0
pandas==3.0.3
numpy==2.2.6
matplotlib==3.11.0
mplfinance==0.12.10b0
akshare==1.18.64
yfinance==1.5.1
openpyxl==3.1.5
```

Keep `runtime.txt` at `3.11`; choose Python 3.11 explicitly in Streamlit Cloud Advanced settings during deployment.

- [ ] **Step 2: Run the complete local verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py mobile_view.py scripts/export_mobile_plan_secret.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
powershell -ExecutionPolicy Bypass -File .\start_app.ps1
```

Expected: compilation succeeds, the full expanded suite passes, `git diff --check` is clean, and `http://127.0.0.1:8501` returns HTTP 200 in local-full mode.

- [ ] **Step 3: Verify the generated cloud snapshot without exposing it in output**

Run:

```powershell
.\.venv\Scripts\python.exe scripts/export_mobile_plan_secret.py
.\.venv\Scripts\python.exe -c "import tomllib; from mobile_view import load_mobile_plan; p=tomllib.load(open('private_data/mobile_streamlit_secrets.toml','rb')); plan=load_mobile_plan(p); assert plan['assets']; print('mobile secret valid')"
git check-ignore -- private_data/mobile_streamlit_secrets.toml
```

Expected: `mobile secret valid`; Git reports that the generated file is ignored. Do not print `PURCHASE_PLAN_B64` or the decoded plan.

- [ ] **Step 4: Record the verified pre-deployment state**

Append to `STATUS.md` that the private mobile read-only code, privacy checks, pinned environment, full tests, and local HTTP check pass, but do not add a production URL yet. Add to `PROJECT_CONTEXT.md` that the chosen deployment architecture is private Streamlit Community Cloud with local-full and cloud-read-only modes.

- [ ] **Step 5: Commit the verified deployment-ready code**

Run:

```powershell
git add -- requirements.txt PROJECT_CONTEXT.md STATUS.md
git commit -m "chore: prepare private Streamlit deployment"
```

Expected: ignored secrets and private files remain unstaged.

---

### Task 6: Make the repository private and deploy to Streamlit Community Cloud

**Files:**
- External state: GitHub repository visibility
- External state: Streamlit Community Cloud application and Secrets

**Interfaces:**
- Consumes: the committed branch, `private_data/mobile_streamlit_secrets.toml`, and the user's existing GitHub/Streamlit login
- Produces: one private `https://<subdomain>.streamlit.app` deployment

- [ ] **Step 1: Run the final deployment-input audit**

Run:

```powershell
git status --short --branch
git ls-files | rg "(^|/)(private_data|journal|cache|tmp|恒生|科技)/|\.xlsx$|scripts/_jiaogedan_raw\.csv$|secrets\.toml$|streamlit.*\.log$"
git ls-files --error-unmatch app.py mobile_view.py financial_report_check.py portfolio_review.py requirements.txt runtime.txt
```

Expected: the privacy search returns no tracked files; every required runtime file is tracked. Unrelated ignored/untracked local research files may remain but must not be staged.

- [ ] **Step 2: Change the GitHub repository from public to private**

Run:

```powershell
gh repo edit milaotou001/etf-quant --visibility private --accept-visibility-change-consequences
gh repo view milaotou001/etf-quant --json visibility,url,defaultBranchRef
```

Expected: visibility is `PRIVATE`. This is intentionally done before uploading the plan secret or deploying the application.

- [ ] **Step 3: Push the verified implementation branch**

Run:

```powershell
git push -u origin codex/credible-decision-core
```

Expected: the branch is available in the private repository and no private local artifact is transferred.

- [ ] **Step 4: Create the Streamlit Community Cloud application**

In `https://share.streamlit.io`:

1. Sign in with the GitHub account that owns `milaotou001/etf-quant`.
2. Create an app from repository `milaotou001/etf-quant`.
3. Select branch `codex/credible-decision-core` and entrypoint `app.py`.
4. In Advanced settings, select Python `3.11`.
5. Paste the complete contents of the ignored local file `private_data/mobile_streamlit_secrets.toml` into Secrets without echoing it into chat or terminal logs.
6. Deploy and wait for the app status to become running.

If GitHub or Streamlit requests OAuth/MFA, pause only for the user to complete that login step, then continue.

- [ ] **Step 5: Restrict the application to the owner**

Open App settings → Sharing and select `Only specific people can view this app`. Keep only the owner's email/Google account as an authorized viewer. Do not make the app public or searchable.

---

### Task 7: Verify the private cloud app on mobile and finalize project state

**Files:**
- Modify: `PROJECT_CONTEXT.md`
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: the private Streamlit URL from Task 6
- Produces: verified production URL, privacy evidence, mobile evidence, and documented fallback criteria

- [ ] **Step 1: Verify access control before checking content**

Open the deployment URL in an unauthenticated browser session.

Expected: only a Streamlit sign-in/no-access screen is visible; no ETF name, RSI, plan amount, or chart is present before authentication.

Then open the same URL in the owner's authenticated session.

Expected: the application loads and the sidebar shows only `状态与图表` and `半年买入计划`.

- [ ] **Step 2: Verify RSI and market data for every required ETF**

Check A500 `563360`, 沪深300 `510300`, 黄金 `518880`, 科创50 `588000`, 电网设备 `561380`, 稀土 `516150`, 港股创新药 `159570`, and电池 `159755`.

For each symbol record:

```text
symbol | cloud data date | cloud RSI | local data date | local RSI | result
```

Expected: cloud and local use the same data date and RSI rounding. If a source is unavailable, the cloud page must say `本次未取得行情数据` or list the unavailable plan symbols instead of showing an unexplained stale value.

- [ ] **Step 3: Verify the phone layout at approximately 390 × 844**

Use a mobile browser or responsive viewport and check both pages.

Expected on `状态与图表`:

- RSI is the first metric after the title and data date.
- The chart fits the viewport without page-level horizontal scrolling.
- Refresh remains available.

Expected on `半年买入计划`:

- Summary metrics, plan amounts, statuses, and batches are legible without horizontal scrolling.
- Plan cells are plain read-only cards, not clickable action buttons.
- No statement uploader, trade-record checkbox, buy confirmation, undo action, journal form, portfolio review, strategy backtest, or policy page is visible.

- [ ] **Step 4: Check cloud logs and cold start**

Restart/reboot the Streamlit app once from its management console and open it again after the process restarts.

Expected: startup completes without import or dependency errors; the first market load either succeeds or shows the explicit data-unavailable message. Review cloud logs and confirm there is no repeating traceback.

- [ ] **Step 5: Document the production result**

Update `PROJECT_CONTEXT.md` with:

```text
- Deployment: private Streamlit Community Cloud
- Production URL: <verified streamlit.app URL>
- Entrypoint: app.py
- Runtime: Python 3.11 / Streamlit 1.58.0
- Access: owner-only Streamlit authentication
- Cloud mode: RSI, charts, and read-only purchase-plan snapshot
- Plan sync: manual Secret refresh
- Fallback: migrate the same read-only mode to Aliyun only if domestic market-data access remains unreliable
```

Append to `STATUS.md` the deployment date, URL, access-control result, tested mobile viewport, ETF data verification summary, cold-start/log result, and any remaining limitation.

- [ ] **Step 6: Commit and push the deployment record**

Run:

```powershell
git add -- PROJECT_CONTEXT.md STATUS.md
git commit -m "docs: record private mobile deployment"
git push
```

Expected: the private repository contains the verified deployment record; no plan secret or private file is included.

- [ ] **Step 7: Final completion check**

Run:

```powershell
git status --short --branch
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all intended deployment work is committed and pushed, unrelated local research files remain untouched, and the full test suite passes.
