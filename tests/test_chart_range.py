import base64
import os
import sys
import unittest

import pandas as pd
from matplotlib.figure import Figure


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from chart import figure_to_data_uri, resolve_chart_start


class ChartRangeTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2020-01-01", periods=10, freq="D")

    def test_since_inception_starts_at_first_available_date(self):
        self.assertEqual(resolve_chart_start(self.index, "从诞生至今"), self.index[0])

    def test_recent_range_uses_last_date_as_anchor(self):
        self.assertEqual(resolve_chart_start(self.index, "近 6 个月"), self.index[-1] - pd.Timedelta(days=183))


class FigureDataUriTests(unittest.TestCase):
    def test_figure_is_embedded_as_png_data_uri(self):
        fig = Figure(figsize=(2, 1))
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1])

        uri = figure_to_data_uri(fig, dpi=72)

        prefix = "data:image/png;base64,"
        self.assertTrue(uri.startswith(prefix))
        png = base64.b64decode(uri[len(prefix):])
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(png), 0)


if __name__ == "__main__":
    unittest.main()
