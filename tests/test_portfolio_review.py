import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from portfolio_review import (
    ATTRIBUTION_START,
    build_attribution_rows,
    build_cluster_exposure,
    run_pressure_replay,
)


def _prices(values, start="2026-07-18"):
    return pd.DataFrame(
        {"close": values},
        index=pd.bdate_range(start, periods=len(values)),
    )


class PortfolioAttributionTests(unittest.TestCase):
    def test_only_reconciled_trades_on_or_after_official_start_are_attributed(self):
        plan = {
            "assets": {
                "561380": {
                    "name": "电网设备",
                    "items": [
                        {
                            "id": "old",
                            "status": "reconciled",
                            "execution_type": "on_plan",
                            "actual": {"date": "2026-07-17", "price": 10.0, "amount": 1_000.0},
                        },
                        {
                            "id": "new",
                            "status": "reconciled",
                            "execution_type": "deviation",
                            "deviation_reason": "提前执行",
                            "actual": {"date": "2026-07-21", "price": 10.0, "amount": 1_000.0},
                        },
                    ],
                }
            }
        }
        frames = {
            "561380": _prices([10.0, 10.0, 11.0]),
            "510300": _prices([20.0, 20.0, 21.0]),
            "159326": _prices([5.0, 5.0, 5.25]),
        }

        rows = build_attribution_rows(plan, frames, as_of="2026-07-22")

        self.assertEqual(ATTRIBUTION_START, pd.Timestamp("2026-07-18"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_id"], "new")
        self.assertEqual(rows[0]["execution_type"], "deviation")
        self.assertAlmostEqual(rows[0]["direction_excess_pct"], 5.0)
        self.assertAlmostEqual(rows[0]["etf_selection_pct"], 5.0)

    def test_timing_effect_is_only_calculated_for_an_explicit_planned_date(self):
        plan = {
            "assets": {
                "518880": {
                    "name": "黄金",
                    "items": [
                        {
                            "id": "gold-1",
                            "planned_date": "2026-07-18",
                            "status": "reconciled",
                            "execution_type": "on_plan",
                            "actual": {"date": "2026-07-21", "price": 9.0, "amount": 900.0},
                        }
                    ],
                }
            }
        }
        frames = {
            "518880": _prices([10.0, 9.0, 9.9]),
            "510300": _prices([20.0, 20.0, 20.0]),
        }

        row = build_attribution_rows(plan, frames, as_of="2026-07-22")[0]

        self.assertAlmostEqual(row["timing_effect_amount"], 99.0)


class PortfolioRiskTests(unittest.TestCase):
    def test_cluster_exposure_groups_current_and_pending_values(self):
        progress = {
            "563360": {"display_value": 50_000.0, "pending_estimate": 3_750.0},
            "588000": {"display_value": 20_000.0, "pending_estimate": 0.0},
            "159995": {"display_value": 10_000.0, "pending_estimate": 0.0},
            "518880": {"display_value": 40_000.0, "pending_estimate": 2_500.0},
        }

        exposure = build_cluster_exposure(progress)

        by_name = {row["cluster"]: row for row in exposure}
        self.assertEqual(by_name["A股宽基"]["value"], 50_000.0)
        self.assertEqual(by_name["科技成长"]["value"], 30_000.0)
        self.assertEqual(by_name["黄金"]["pending_estimate"], 2_500.0)

    def test_pressure_replay_reports_loss_concentration_and_budget_usage(self):
        frames = {
            "563360": _prices([100.0, 110.0, 80.0]),
            "588000": _prices([100.0, 100.0, 90.0]),
        }
        position_values = {"563360": 100_000.0, "588000": 100_000.0}

        result = run_pressure_replay(frames, position_values, lookback=250)

        self.assertAlmostEqual(result["pressure_loss"], 48_611.1111111111)
        self.assertTrue(result["over_budget"])
        self.assertTrue(result["concentration_warning"])
        self.assertAlmostEqual(result["cluster_losses"]["A股宽基"], 37_500.0)
        self.assertAlmostEqual(result["cluster_losses"]["科技成长"], 11_111.1111111111)
        self.assertAlmostEqual(result["budget_usage_pct"], 48_611.1111111111 / 42_750 * 100)


if __name__ == "__main__":
    unittest.main()
