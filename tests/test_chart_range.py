import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from chart import resolve_chart_start


class ChartRangeTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2020-01-01", periods=10, freq="D")

    def test_since_inception_starts_at_first_available_date(self):
        self.assertEqual(resolve_chart_start(self.index, "从诞生至今"), self.index[0])

    def test_recent_range_uses_last_date_as_anchor(self):
        self.assertEqual(resolve_chart_start(self.index, "近 6 个月"), self.index[-1] - pd.Timedelta(days=183))


if __name__ == "__main__":
    unittest.main()
