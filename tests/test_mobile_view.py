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
    is_mobile_read_only,
    load_mobile_plan,
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


if __name__ == "__main__":
    unittest.main()
