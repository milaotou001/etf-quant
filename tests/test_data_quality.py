import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from data import attach_data_quality


class DataQualityTests(unittest.TestCase):
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
