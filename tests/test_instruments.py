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
            "588000": (30, 25),
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

    def test_experimental_symbols_cannot_borrow_core_strategy_rules(self):
        for spec in list_instruments(include_experimental=True):
            if spec.is_core:
                continue
            self.assertFalse(spec.supports_campaign)
            self.assertFalse(spec.supports_backtest)
            self.assertIsNone(spec.rsi_first_entry)
            self.assertIsNone(spec.rsi_second_entry)

    def test_unknown_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            get_instrument("UNKNOWN")


if __name__ == "__main__":
    unittest.main()
