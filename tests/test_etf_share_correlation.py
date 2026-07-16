import unittest

import pandas as pd

from scripts.etf_share_correlation import campaign_event_frame


class CampaignCorrelationTests(unittest.TestCase):
    def test_campaign_returns_use_three_entry_cost_basis(self):
        dates = pd.date_range("2026-01-01", periods=5, freq="B")
        frame = pd.DataFrame(
            {
                "close": [90.0, 80.0, 100.0, 105.0, 110.0],
                "share_change_5d": [1.0] * 5,
            },
            index=dates,
        )
        campaign = {
            "status": "complete",
            "entries": [
                {"stage": "第一观察位", "date": dates[0], "price": 90.0},
                {"stage": "第二观察位", "date": dates[1], "price": 80.0},
                {"stage": "右侧确认", "date": dates[2], "price": 100.0},
            ],
        }

        result = campaign_event_frame(frame, [campaign], windows=(2,))

        units = (1 / 3) / 90 + (1 / 3) / 80 + (1 / 3) / 100
        expected_return = (units * 110 - 1) * 100
        expected_adverse = (units * 105 - 1) * 100
        self.assertAlmostEqual(result.iloc[0]["forward_return_2d"], expected_return)
        self.assertAlmostEqual(result.iloc[0]["forward_drawdown_2d"], expected_adverse)


if __name__ == "__main__":
    unittest.main()
