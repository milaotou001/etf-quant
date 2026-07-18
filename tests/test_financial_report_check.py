from datetime import date
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from financial_report_check import build_financial_report_check


class FinancialReportCheckTests(unittest.TestCase):
    def test_before_first_checkpoint_shows_next_date(self):
        result = build_financial_report_check(date(2026, 7, 18))

        self.assertEqual(result["status"], "upcoming")
        self.assertEqual(result["next_date"], date(2026, 7, 20))
        self.assertIn("7月20日", result["headline"])

    def test_checkpoint_day_is_not_marked_as_completed(self):
        result = build_financial_report_check(date(2026, 7, 20))

        self.assertEqual(result["status"], "today")
        self.assertIn("今天检查", result["headline"])

    def test_after_august_checkpoint_points_to_unified_review(self):
        result = build_financial_report_check(date(2026, 8, 16))

        self.assertEqual(result["status"], "upcoming")
        self.assertEqual(result["next_date"], date(2026, 9, 1))
        self.assertIn("统一复盘", result["headline"])

    def test_unified_review_date_stays_due(self):
        result = build_financial_report_check(date(2026, 9, 1))

        self.assertEqual(result["status"], "due")
        self.assertIsNone(result["next_date"])
        self.assertIn("已到期", result["headline"])
        self.assertEqual(len(result["checkpoints"]), 3)
        self.assertEqual(len(result["disclosure_notes"]), 2)

    def test_electric_grid_is_included_throughout_the_report_review(self):
        first_check = build_financial_report_check(date(2026, 7, 18))
        final_check = build_financial_report_check(date(2026, 9, 1))
        timeline_text = " ".join(
            checkpoint["action"] for checkpoint in first_check["checkpoints"]
        )
        disclosure_text = " ".join(first_check["disclosure_notes"])

        self.assertIn("电网", first_check["headline"])
        self.assertIn("电网", timeline_text)
        self.assertIn("电网", disclosure_text)
        self.assertIn("电网", final_check["headline"])

    def test_battery_is_included_as_first_alternate_not_purchase_target(self):
        first_check = build_financial_report_check(date(2026, 7, 18))
        final_check = build_financial_report_check(date(2026, 9, 1))
        timeline_text = " ".join(
            checkpoint["action"] for checkpoint in first_check["checkpoints"]
        )
        disclosure_text = " ".join(first_check["disclosure_notes"])

        self.assertIn("电池候补", timeline_text)
        self.assertIn("电池候补", disclosure_text)
        self.assertIn("电池候补", final_check["headline"])
        self.assertEqual(
            first_check["candidate_note"],
            "电池只作为第一候补参与复核，暂不加入买入计划。",
        )


if __name__ == "__main__":
    unittest.main()
