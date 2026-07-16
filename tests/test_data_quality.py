import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from data import attach_data_quality, normalize_known_corporate_actions


class DataQualityTests(unittest.TestCase):
    def test_159995_one_to_two_split_adjusts_pre_split_prices(self):
        frame = pd.DataFrame(
            {
                "open": [3.0, 1.5],
                "high": [3.1, 1.6],
                "low": [2.9, 1.4],
                "close": [3.0, 1.5],
                "volume": [100.0, 200.0],
                "amount": [300.0, 300.0],
            },
            index=pd.to_datetime(["2026-07-06", "2026-07-07"]),
        )

        result = normalize_known_corporate_actions(frame, "159995")

        self.assertAlmostEqual(result.loc["2026-07-06", "close"], 1.5)
        self.assertAlmostEqual(result.loc["2026-07-06", "high"], 1.55)
        self.assertAlmostEqual(result.loc["2026-07-06", "volume"], 200.0)
        self.assertAlmostEqual(result.loc["2026-07-06", "amount"], 300.0)
        self.assertIn("1:2", result.attrs["corporate_action_adjustment"])

    def test_561380_one_to_two_point_five_split_adjusts_pre_split_history(self):
        frame = pd.DataFrame(
            {
                "open": [2.355, 0.960],
                "high": [2.383, 0.969],
                "low": [2.323, 0.939],
                "close": [2.373, 0.961],
                "volume": [100.0, 250.0],
                "amount": [237.3, 240.25],
            },
            index=pd.to_datetime(["2026-06-24", "2026-06-25"]),
        )

        result = normalize_known_corporate_actions(frame, "561380")

        self.assertAlmostEqual(result.loc["2026-06-24", "close"], 0.9492)
        self.assertAlmostEqual(result.loc["2026-06-24", "high"], 0.9532)
        self.assertAlmostEqual(result.loc["2026-06-24", "volume"], 250.0)
        self.assertAlmostEqual(result.loc["2026-06-24", "amount"], 237.3)
        self.assertAlmostEqual(result.loc["2026-06-25", "close"], 0.961)
        self.assertIn("1:2.5", result.attrs["corporate_action_adjustment"])

    def test_estimated_amount_is_explicitly_marked_unverified(self):
        frame = pd.DataFrame({"close": [1.0], "amount": [100.0]})

        result = attach_data_quality(
            frame,
            source="腾讯",
            amount_verified=False,
            freshness="current",
            note="成交额由成交量和均价估算",
        )

        self.assertEqual(result.attrs["source"], "腾讯")
        self.assertFalse(result.attrs["amount_verified"])
        self.assertEqual(result.attrs["data_freshness"], "current")
        self.assertIn("估算", result.attrs["data_note"])


if __name__ == "__main__":
    unittest.main()
