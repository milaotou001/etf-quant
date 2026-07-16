import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from trades import (
    extract_account_snapshot,
    load_account_snapshot,
    load_trade_cache,
    parse_trade_dataframe,
    save_account_snapshot,
    save_trade_cache,
    update_trade_cache,
)


class TradeStatementTests(unittest.TestCase):
    @staticmethod
    def _statement_rows():
        header = ["日期", "币种", "股东账号", "证券代码", "证券名称", "摘要", "成交数量", "成交均价", "佣金", "印花税", "其他费", "发生金额", "资金余额"]
        return [
            ["电子对账单"] + [None] * 12,
            header,
            ["20260701", "人民币", "private", "563360", "A500", "证券买入", 100, 1.0, 0, 0, 0, -100, 50000.0],
            ["20260702", "人民币", "private", "563360", "A500", "证券卖出", 100, 1.1, 0, 0, 0, 110, 50110.0],
        ]

    def test_uploaded_statement_is_parsed_without_a_fixed_local_path(self):
        parsed = parse_trade_dataframe(pd.DataFrame(self._statement_rows()))

        self.assertEqual([entry["type"] for entry in parsed["563360"]], ["buy", "sell_profit"])

    def test_parsed_trades_round_trip_through_private_cache(self):
        import tempfile

        trades = {
            "563360": [
                {"date": pd.Timestamp("2026-07-01"), "type": "buy", "price": 1.0, "qty": 100, "amount": 100.0}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trades.json")
            save_trade_cache(trades, path)
            loaded = load_trade_cache(path)

        self.assertEqual(loaded["563360"][0]["date"], pd.Timestamp("2026-07-01"))
        self.assertEqual(loaded["563360"][0]["qty"], 100)

    def test_missing_private_cache_returns_empty_mapping(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_trade_cache(os.path.join(directory, "missing.json")), {})

    def test_new_statement_replaces_previous_cache(self):
        import tempfile
        from unittest.mock import patch

        old_trades = {"563360": [{"date": pd.Timestamp("2026-07-01"), "type": "buy", "price": 1.0, "qty": 100, "amount": 100.0}]}
        new_rows = self._statement_rows()
        new_rows[2] = ["20260708", "人民币", "private", "510300", "沪深300", "证券买入", 50, 4.0, 0, 0, 0, -200, 49910.0]
        new_rows = new_rows[:3]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trades.json")
            snapshot_path = os.path.join(directory, "account_snapshot.json")
            save_trade_cache(old_trades, path)
            with patch("trades.pd.read_excel", return_value=pd.DataFrame(new_rows)):
                update_trade_cache(object(), path, snapshot_path)
            loaded = load_trade_cache(path)

        self.assertNotIn("563360", loaded)
        self.assertEqual(loaded["510300"][0]["qty"], 50)

    def test_last_valid_cash_balance_is_extracted_with_its_date(self):
        snapshot = extract_account_snapshot(pd.DataFrame(self._statement_rows()))

        self.assertEqual(snapshot, {"cash_balance": 50110.0, "cash_date": "2026-07-02"})

    def test_account_snapshot_round_trips_through_private_json(self):
        import tempfile

        snapshot = {"cash_balance": 50110.0, "cash_date": "2026-07-02"}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "account_snapshot.json")
            save_account_snapshot(snapshot, path)
            loaded = load_account_snapshot(path)

        self.assertEqual(loaded, snapshot)


if __name__ == "__main__":
    unittest.main()
