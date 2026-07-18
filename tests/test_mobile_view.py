import copy
import mobile_view
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from mobile_view import (
    MobileViewConfigError,
    encode_plan_snapshot,
    encode_trade_snapshot,
    is_mobile_read_only,
    load_mobile_plan,
    load_mobile_trades,
    mobile_page_options,
    primary_metric_order,
)
from purchase_plan import CURRENT_PLAN_VERSION, default_purchase_plan


class MobileViewTests(unittest.TestCase):
    def test_read_only_plan_skips_live_price_fetches(self):
        selector = getattr(mobile_view, "plan_price_symbols", None)
        self.assertIsNotNone(selector)
        self.assertEqual(selector(True, ["563360", "510300"]), ())

    def test_local_mode_is_default_and_keeps_full_navigation(self):
        self.assertFalse(is_mobile_read_only({}))
        self.assertEqual(
            mobile_page_options(False),
            [
                "状态与图表",
                "复盘日志",
                "策略回测",
                "策略规则",
                "半年买入计划",
                "组合复盘",
                "战略方向",
            ],
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

    def test_trade_snapshot_round_trip_keeps_only_chart_fields(self):
        trades = {
            "563360": [
                {
                    "date": "2026-07-01",
                    "type": "buy",
                    "price": 1.2345,
                    "qty": 1200,
                    "amount": 1481.4,
                    "account_id": "must-not-leak",
                },
                {
                    "date": "2026-07-10",
                    "type": "sell_profit",
                    "price": 1.3,
                    "qty": 500,
                    "amount": 650.0,
                },
            ]
        }

        encoded = encode_trade_snapshot(trades)
        decoded = load_mobile_trades({"TRADES_B64": encoded})

        self.assertEqual(
            decoded,
            {
                "563360": [
                    {"date": "2026-07-01", "type": "buy", "price": 1.2345, "qty": 1200},
                    {"date": "2026-07-10", "type": "sell_profit", "price": 1.3, "qty": 500},
                ]
            },
        )
        self.assertNotIn("must-not-leak", encoded)
        self.assertNotIn("amount", decoded["563360"][0])

    def test_missing_or_invalid_trade_snapshot_degrades_to_empty(self):
        self.assertEqual(load_mobile_trades({}), {})
        self.assertEqual(load_mobile_trades({"TRADES_B64": "not-base64"}), {})

    def test_invalid_trade_type_is_rejected_when_exporting(self):
        with self.assertRaisesRegex(MobileViewConfigError, "type"):
            encode_trade_snapshot(
                {"563360": [{"date": "2026-07-01", "type": "unknown", "price": 1.0, "qty": 100}]}
            )


if __name__ == "__main__":
    unittest.main()
