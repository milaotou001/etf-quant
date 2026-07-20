import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from instruments import CORE_SYMBOLS, get_instrument, list_instruments


class InstrumentRegistryTests(unittest.TestCase):
    def test_core_etfs_have_fixed_campaign_thresholds(self):
        expected = {
            "563360": (40, 35),
            "510300": (40, 35),
            "518880": (35, 30),
        }

        self.assertEqual(CORE_SYMBOLS, tuple(expected))
        for symbol, (first_entry, second_entry) in expected.items():
            spec = get_instrument(symbol)
            self.assertTrue(spec.is_core)
            self.assertTrue(spec.supports_campaign)
            self.assertTrue(spec.supports_backtest)
            self.assertEqual((spec.rsi_first_entry, spec.rsi_second_entry), (first_entry, second_entry))
            self.assertEqual(spec.rsi_confirmation, 40)
            self.assertTrue(spec.requires_verified_amount)

    def test_suspended_core_preserves_thresholds_but_not_campaign(self):
        spec = get_instrument("588000")
        self.assertFalse(spec.is_core)
        self.assertFalse(spec.supports_campaign)
        self.assertFalse(spec.supports_backtest)
        self.assertEqual(spec.rsi_first_entry, 30)
        self.assertEqual(spec.rsi_second_entry, 25)
        self.assertEqual(spec.rsi_confirmation, 40)

    def test_experimental_symbols_cannot_borrow_core_strategy_rules(self):
        for spec in list_instruments(include_experimental=True):
            if spec.is_core or spec.symbol == "588000":
                continue
            self.assertFalse(spec.supports_campaign)
            self.assertFalse(spec.supports_backtest)
            self.assertIsNone(spec.rsi_first_entry)
            self.assertIsNone(spec.rsi_second_entry)

    def test_personal_holdings_are_available_as_experimental_observations(self):
        spec = get_instrument("159920")
        self.assertEqual(spec.name, "恒生 ETF")
        self.assertEqual(spec.market, "HK")
        self.assertFalse(spec.is_core)
        self.assertFalse(spec.supports_campaign)
        self.assertFalse(spec.supports_backtest)
        self.assertIn(spec, list_instruments(include_experimental=True))

    def test_focus_watchlist_symbols_are_labeled_without_strategy_rules(self):
        expected = {
            "561380": "电网设备 ETF",
            "516150": "稀土 ETF",
            "159570": "港股创新药 ETF",
        }
        for symbol, name in expected.items():
            spec = get_instrument(symbol)
            self.assertEqual(spec.name, name)
            self.assertTrue(spec.is_focus)
            self.assertEqual(spec.display_tier, "重点")
            self.assertFalse(spec.is_core)
            self.assertFalse(spec.supports_campaign)
            self.assertFalse(spec.supports_backtest)

        dbo = get_instrument("DBO")
        self.assertFalse(dbo.is_focus)
        self.assertEqual(dbo.display_tier, "观察")
        self.assertEqual(get_instrument("510300").display_tier, "核心")

    def test_battery_is_available_as_an_alternate_without_strategy_rules(self):
        battery = get_instrument("159755")

        self.assertEqual(battery.name, "电池 ETF")
        self.assertEqual(battery.market, "CN")
        self.assertTrue(battery.is_alternate)
        self.assertFalse(battery.is_focus)
        self.assertEqual(battery.display_tier, "候补")
        self.assertFalse(battery.is_core)
        self.assertFalse(battery.supports_campaign)
        self.assertFalse(battery.supports_backtest)
        self.assertIn(battery, list_instruments(include_experimental=True))

    def test_unknown_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            get_instrument("UNKNOWN")


if __name__ == "__main__":
    unittest.main()
