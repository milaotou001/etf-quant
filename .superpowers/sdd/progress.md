# Mobile all charts implementation ledger

## 2026-08-20

- Created implementation plan at `docs/superpowers/plans/2026-08-20-mobile-all-charts.md`.
- Baseline full suite: 142 tests, 8 failures. Three stale navigation assertions and five unrelated purchase-plan assertions; see final verification for updated outcome.
- Catalog check: `list_instruments(include_experimental=True)` currently returns 14 items. Feature must remain catalog-driven rather than hard-coding a count.
- Task 1 complete: added `ALL_CHARTS_PAGE` only to the read-only navigation and updated stale full-navigation expectations. Focused navigation tests passed (15 tests).
- Task 2 complete: added the read-only all-chart entry, catalog-driven vertical cards, shared range selection, per-symbol error continuation, no-trade figures, and context-sensitive refresh label. Focused tests passed (34 tests); full suite now has only the five pre-existing purchase-plan failures.
- Review follow-up: expanded the per-symbol boundary to include card rendering and closes each rendered figure; two regression tests now cover both conditions.
