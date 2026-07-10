import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from journal import compute_review_metrics, upsert_review_section


class JournalReviewTests(unittest.TestCase):
    def test_review_metrics_uses_peak_to_trough_drawdown(self):
        prices = pd.Series([100.0, 90.0, 110.0, 80.0])

        metrics = compute_review_metrics(prices)

        self.assertAlmostEqual(metrics["total_change"], -20.0)
        self.assertAlmostEqual(metrics["max_drawdown"], -27.2727, places=3)
        self.assertAlmostEqual(metrics["max_gain"], 10.0)

    def test_review_section_is_replaced_instead_of_appended(self):
        initial = "# 日志\n\n<!-- REVIEW_PLACEHOLDER -->\n"
        first = upsert_review_section(initial, "第一版复盘")
        second = upsert_review_section(first, "第二版复盘")

        self.assertEqual(second.count("## 事后回顾"), 1)
        self.assertNotIn("第一版复盘", second)
        self.assertIn("第二版复盘", second)


if __name__ == "__main__":
    unittest.main()
