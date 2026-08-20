import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

import data


class CustomSymbolSearchTests(unittest.TestCase):
    def setUp(self):
        lookup = getattr(data, "lookup_cn_security_name", None)
        if lookup is not None:
            lookup.cache_clear()

    @patch("data.ak.fund_etf_spot_em")
    def test_looks_up_etf_name(self, spot):
        spot.return_value = pd.DataFrame({"代码": ["512880"], "名称": ["证券ETF"]})

        self.assertEqual(data.lookup_cn_security_name("512880"), "证券ETF")

    @patch("data.ak.stock_individual_info_em")
    def test_looks_up_a_share_name(self, info):
        info.return_value = pd.DataFrame({"item": ["股票简称"], "value": ["伊利股份"]})

        self.assertEqual(data.lookup_cn_security_name("600887"), "伊利股份")

    @patch("data.ak.fund_etf_spot_em", side_effect=RuntimeError("offline"))
    def test_name_lookup_falls_back_to_code_when_data_source_is_unavailable(self, spot):
        self.assertEqual(data.lookup_cn_security_name("512880"), "512880")

    def test_classifies_supported_etf_codes(self):
        self.assertEqual(data.classify_cn_security("561380"), "etf")
        self.assertEqual(data.classify_cn_security("159570"), "etf")

    def test_classifies_supported_a_share_codes(self):
        for symbol in ("600887", "300750", "688981", "430047", "920002"):
            with self.subTest(symbol=symbol):
                self.assertEqual(data.classify_cn_security(symbol), "ashare")

    def test_rejects_non_six_digit_or_unsupported_codes(self):
        for symbol in ("", "60088", "ABCDEF", "200001"):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    data.classify_cn_security(symbol)

    def test_a_share_cache_path_is_separate_from_etf_cache_path(self):
        self.assertEqual(
            data._ashare_cache_path("600887"),
            os.path.join(data.CACHE_DIR, "ASHARE_600887.csv"),
        )
        self.assertNotEqual(
            data._ashare_cache_path("600887"),
            os.path.join(data.CACHE_DIR, "600887.csv"),
        )

    @patch("data._load_ashare")
    def test_load_data_routes_a_share_to_its_own_loader(self, load_ashare):
        expected = pd.DataFrame({"close": [1.0]})
        load_ashare.return_value = expected

        result = data.load_data("600887")

        self.assertIs(result, expected)
        load_ashare.assert_called_once_with("600887", False)

    @patch("data._load_cn_etf")
    def test_load_data_routes_etf_to_existing_loader(self, load_etf):
        expected = pd.DataFrame({"close": [1.0]})
        load_etf.return_value = expected

        result = data.load_data("561380")

        self.assertIs(result, expected)
        load_etf.assert_called_once_with("561380", False)

    @patch("data.ak.stock_zh_a_hist")
    def test_a_share_eastmoney_frame_keeps_real_amount(self, fetch):
        fetch.return_value = pd.DataFrame(
            {
                "日期": ["2026-07-29"],
                "开盘": [10.0],
                "最高": [10.5],
                "最低": [9.8],
                "收盘": [10.2],
                "成交量": [1000],
                "成交额": [10200],
            }
        )

        result = data.fetch_klines_ashare_eastmoney("600887")

        self.assertEqual(list(result.columns), ["open", "high", "low", "close", "volume", "amount"])
        self.assertEqual(result.iloc[0]["amount"], 10200)
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
