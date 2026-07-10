import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from backtest import run_campaign_backtest, simulate_campaigns
from instruments import get_instrument


class CampaignBacktestTests(unittest.TestCase):
    def test_campaign_tracks_two_observation_entries_then_right_confirmation(self):
        dates = pd.date_range("2026-01-01", periods=7, freq="B")
        df = pd.DataFrame(
            {
                "close": [100, 99, 98, 96, 97, 99, 101],
                "rsi": [50, 40, 35, 31, 34, 41, 45],
                "MACDh_12_26_9": [0.2, -0.1, -0.4, -0.7, -0.5, -0.2, 0.1],
            },
            index=dates,
        )

        campaigns = simulate_campaigns(df, get_instrument("563360"))

        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["status"], "complete")
        self.assertEqual([entry["stage"] for entry in campaign["entries"]], ["第一观察位", "第二观察位", "右侧确认"])
        self.assertEqual(campaign["entries"][-1]["date"], dates[5])

    def test_experimental_symbol_has_no_campaign_simulation(self):
        df = pd.DataFrame({"close": [1.0], "rsi": [20], "MACDh_12_26_9": [0.0]})
        self.assertEqual(simulate_campaigns(df, get_instrument("HSI")), [])

    def test_backtest_uses_equal_weighted_campaign_cost_basis(self):
        dates = pd.date_range("2026-01-01", periods=7, freq="B")
        df = pd.DataFrame(
            {
                "close": [100, 99, 98, 96, 97, 99, 101],
                "rsi": [50, 40, 35, 31, 34, 41, 45],
                "MACDh_12_26_9": [0.2, -0.1, -0.4, -0.7, -0.5, -0.2, 0.1],
            },
            index=dates,
        )

        summary = run_campaign_backtest(df, get_instrument("563360"), holding_windows=(1,))

        self.assertEqual(int(summary.iloc[0]["可计算战役"]), 1)
        self.assertEqual(summary.iloc[0]["平均收益"], "+2.37%")


if __name__ == "__main__":
    unittest.main()
