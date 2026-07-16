import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import pandas as pd

from etf_shares import build_share_observation, load_share_observation
from dashboard import show
from tests.test_market_analysis import _base_df


def make_history(symbol: str, shares: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-06-01", periods=len(shares), freq="B")
    return pd.DataFrame(
        {"symbol": symbol, "shares": shares},
        index=pd.DatetimeIndex(dates, name="date"),
    )


def sse_day(date: str, values: dict[str, float]) -> pd.DataFrame:
    day = pd.Timestamp(date).strftime("%Y-%m-%d")
    return pd.DataFrame(
        {
            "序号": range(1, len(values) + 1),
            "基金代码": list(values),
            "基金简称": [f"ETF-{symbol}" for symbol in values],
            "ETF类型": ["跨市"] * len(values),
            "统计日期": [day] * len(values),
            "基金份额": list(values.values()),
        }
    )


class ShareObservationTests(unittest.TestCase):
    def test_calculates_daily_five_and_twenty_period_changes(self):
        history = make_history("563360", [100 + i for i in range(21)])

        result = build_share_observation(history, "563360", history.index[-1])

        self.assertAlmostEqual(result["daily_change_pct"], 100 / 119)
        self.assertAlmostEqual(result["change_5d_pct"], 500 / 115)
        self.assertAlmostEqual(result["change_20d_pct"], 20.0)
        self.assertEqual(result["state"], "中短期均增加")

    def test_classifies_stable_before_direction(self):
        history = make_history("563360", [100.0] * 19 + [100.2, 100.4])

        result = build_share_observation(history, "563360", history.index[-1])

        self.assertEqual(result["state"], "基本平稳")

    def test_classifies_decrease_and_direction_divergence(self):
        decreasing = make_history("563360", [120 - i for i in range(21)])
        mixed = make_history(
            "563360",
            [100.0] * 15 + [110.0, 108.0, 106.0, 104.0, 102.0, 101.0],
        )

        self.assertEqual(
            build_share_observation(decreasing, "563360")["state"],
            "中短期均减少",
        )
        self.assertEqual(
            build_share_observation(mixed, "563360")["state"],
            "方向分化",
        )

    def test_reports_insufficient_twenty_day_history(self):
        history = make_history("563360", [100, 101, 102, 103, 104, 105])

        result = build_share_observation(history, "563360", history.index[-1])

        self.assertIsNotNone(result["change_5d_pct"])
        self.assertIsNone(result["change_20d_pct"])
        self.assertEqual(result["state"], "数据不足")

    def test_explanation_never_claims_price_prediction(self):
        result = build_share_observation(
            make_history("563360", list(range(100, 121))),
            "563360",
        )

        self.assertIn("不等于价格必然上涨", result["explanation"])
        self.assertNotIn("主力", result["explanation"])


class ShareCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = os.path.join(self.tmp.name, "sse_etf_shares.csv")
        self.dates = pd.date_range("2026-06-01", periods=21, freq="B")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetches_each_missing_date_once_and_reuses_all_symbols(self):
        calls = []

        def fake_fetcher(date):
            calls.append(date)
            offset = len(calls)
            return sse_day(date, {"563360": 100 + offset, "510300": 200 + offset})

        first = load_share_observation(
            "563360", self.dates, cache_path=self.cache_path, fetcher=fake_fetcher
        )
        second = load_share_observation(
            "510300", self.dates, cache_path=self.cache_path, fetcher=fake_fetcher
        )

        self.assertEqual(calls, [d.strftime("%Y%m%d") for d in self.dates])
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first["freshness"], "current")
        self.assertEqual(second["freshness"], "cached")

    def test_empty_refresh_does_not_overwrite_valid_cache(self):
        rows = []
        for index, date in enumerate(self.dates):
            rows.append(
                {
                    "date": date,
                    "symbol": "563360",
                    "name": "A500基金",
                    "etf_type": "跨市",
                    "shares": 100 + index,
                }
            )
        pd.DataFrame(rows).to_csv(self.cache_path, index=False)

        result = load_share_observation(
            "563360",
            self.dates,
            force_refresh=True,
            cache_path=self.cache_path,
            fetcher=lambda date: pd.DataFrame(),
        )

        persisted = pd.read_csv(self.cache_path)
        self.assertEqual(result["latest_shares"], 120.0)
        self.assertEqual(result["freshness"], "cached")
        self.assertEqual(len(persisted), 21)

    def test_force_refresh_only_requests_latest_cached_date(self):
        calls = []
        rows = []
        for index, date in enumerate(self.dates):
            rows.append(
                {
                    "date": date,
                    "symbol": "563360",
                    "name": "A500基金",
                    "etf_type": "跨市",
                    "shares": 100 + index,
                }
            )
        pd.DataFrame(rows).to_csv(self.cache_path, index=False)

        load_share_observation(
            "563360",
            self.dates,
            force_refresh=True,
            cache_path=self.cache_path,
            fetcher=lambda date: calls.append(date) or pd.DataFrame(),
        )

        self.assertEqual(calls, [self.dates[-1].strftime("%Y%m%d")])

    def test_experimental_symbol_returns_none_without_fetching(self):
        calls = []

        result = load_share_observation(
            "HSI",
            self.dates,
            cache_path=self.cache_path,
            fetcher=lambda date: calls.append(date),
        )

        self.assertIsNone(result)
        self.assertEqual(calls, [])


class ShareCliTests(unittest.TestCase):
    def test_cli_hides_observation_by_default_without_changing_campaign_output(self):
        history = make_history("563360", list(range(100, 121)))
        observation = build_share_observation(history, "563360", history.index[-1])
        observation["freshness"] = "current"
        observation["refresh_error"] = ""
        output = StringIO()

        with redirect_stdout(output):
            show(
                _base_df(include_amount=True),
                symbol="563360",
                name="A500 ETF",
                share_observation=observation,
            )

        text = output.getvalue()
        self.assertNotIn("ETF 份额观察（不参与战役）", text)
        self.assertNotIn("中短期均增加", text)
        self.assertIn("战役观察", text)


if __name__ == "__main__":
    unittest.main()
