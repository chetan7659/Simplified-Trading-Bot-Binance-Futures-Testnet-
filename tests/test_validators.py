"""
tests/test_validators.py — Unit tests for all validator functions.
Run: python -m unittest discover tests/   OR   pytest tests/ -v
"""
import unittest
from decimal import Decimal
from bot.validators import (
    validate_symbol, validate_side, validate_order_type,
    validate_quantity, validate_price, validate_stop_price,
)

class TestValidateSymbol(unittest.TestCase):
    def test_valid_uppercase(self):             self.assertEqual(validate_symbol("BTCUSDT"), "BTCUSDT")
    def test_lowercase_normalised(self):        self.assertEqual(validate_symbol("ethusdt"), "ETHUSDT")
    def test_whitespace_stripped(self):         self.assertEqual(validate_symbol("  BtcUsdt  "), "BTCUSDT")
    def test_too_short_raises(self):
        with self.assertRaisesRegex(ValueError, "Length must be between"): validate_symbol("BTC")
    def test_too_long_raises(self):
        with self.assertRaisesRegex(ValueError, "Length must be between"): validate_symbol("A"*21)
    def test_empty_raises(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):      validate_symbol("")
    def test_digits_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only letters"):           validate_symbol("BTC123")
    def test_special_chars_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only letters"):           validate_symbol("BTC-USD")

class TestValidateSide(unittest.TestCase):
    def test_buy(self):                         self.assertEqual(validate_side("buy"), "BUY")
    def test_sell(self):                        self.assertEqual(validate_side("SELL"), "SELL")
    def test_whitespace(self):                  self.assertEqual(validate_side("  Sell  "), "SELL")
    def test_invalid_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid side"):           validate_side("LONG")
    def test_empty_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid side"):           validate_side("")

class TestValidateOrderType(unittest.TestCase):
    def test_market(self):                      self.assertEqual(validate_order_type("MARKET"), "MARKET")
    def test_limit_lowercase(self):             self.assertEqual(validate_order_type("limit"), "LIMIT")
    def test_stop_market(self):                 self.assertEqual(validate_order_type("stop_market"), "STOP_MARKET")
    def test_invalid_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid order type"):     validate_order_type("OCO")
    def test_empty_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid order type"):     validate_order_type("")

class TestValidateQuantity(unittest.TestCase):
    def test_decimal_string(self):              self.assertEqual(validate_quantity("0.001"), Decimal("0.001"))
    def test_integer_string(self):              self.assertEqual(validate_quantity("10"), Decimal("10"))
    def test_float(self):                       self.assertEqual(validate_quantity(0.005), Decimal("0.005"))
    def test_zero_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):      validate_quantity("0")
    def test_negative_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):      validate_quantity("-1")
    def test_non_numeric_rejected(self):
        with self.assertRaisesRegex(ValueError, "Must be a positive number"): validate_quantity("abc")
    def test_empty_rejected(self):
        with self.assertRaisesRegex(ValueError, "Must be a positive number"): validate_quantity("")

class TestValidatePrice(unittest.TestCase):
    def test_limit_valid(self):                 self.assertEqual(validate_price("95000", "LIMIT"), Decimal("95000"))
    def test_limit_none_raises(self):
        with self.assertRaisesRegex(ValueError, "required for LIMIT"):     validate_price(None, "LIMIT")
    def test_limit_empty_raises(self):
        with self.assertRaisesRegex(ValueError, "required for LIMIT"):     validate_price("", "LIMIT")
    def test_limit_zero_raises(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):      validate_price("0", "LIMIT")
    def test_limit_negative_raises(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):      validate_price("-500", "LIMIT")
    def test_limit_non_numeric_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid price"):          validate_price("abc", "LIMIT")
    def test_market_none_ok(self):              self.assertIsNone(validate_price(None, "MARKET"))
    def test_market_empty_ok(self):             self.assertIsNone(validate_price("", "MARKET"))
    def test_market_price_raises(self):
        with self.assertRaisesRegex(ValueError, "must not be provided"):   validate_price("50000", "MARKET")
    def test_stop_market_price_ignored(self):   self.assertIsNone(validate_price(None, "STOP_MARKET"))

class TestValidateStopPrice(unittest.TestCase):
    def test_stop_market_valid(self):           self.assertEqual(validate_stop_price("90000", "STOP_MARKET"), Decimal("90000"))
    def test_stop_market_none_raises(self):
        with self.assertRaisesRegex(ValueError, "required for STOP_MARKET"): validate_stop_price(None, "STOP_MARKET")
    def test_stop_market_empty_raises(self):
        with self.assertRaisesRegex(ValueError, "required for STOP_MARKET"): validate_stop_price("", "STOP_MARKET")
    def test_stop_market_zero_raises(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):      validate_stop_price("0", "STOP_MARKET")
    def test_stop_market_non_numeric_raises(self):
        with self.assertRaisesRegex(ValueError, "Invalid stop price"):     validate_stop_price("bad", "STOP_MARKET")
    def test_market_stop_ignored(self):         self.assertIsNone(validate_stop_price("90000", "MARKET"))
    def test_limit_stop_ignored(self):          self.assertIsNone(validate_stop_price("90000", "LIMIT"))

if __name__ == "__main__": unittest.main()
