"""
tests/test_orders.py — Unit tests for OrderManager (all API calls mocked).
Run: python -m unittest discover tests/   OR   pytest tests/ -v
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock
from bot.client import BinanceAPIError
from bot.orders import OrderManager, OrderResult

MARKET_RESP = {"orderId":111,"clientOrderId":"abc","symbol":"BTCUSDT","side":"BUY",
               "type":"MARKET","status":"FILLED","origQty":"0.001","executedQty":"0.001",
               "avgPrice":"97500.00","price":"0","timeInForce":"GTC"}
LIMIT_RESP  = {"orderId":222,"clientOrderId":"xyz","symbol":"BTCUSDT","side":"SELL",
               "type":"LIMIT","status":"NEW","origQty":"0.001","executedQty":"0.000",
               "avgPrice":"0","price":"100000.00","timeInForce":"GTC"}
STOP_RESP   = {"orderId":333,"clientOrderId":"stp","symbol":"BTCUSDT","side":"SELL",
               "type":"STOP_MARKET","status":"NEW","origQty":"0.001","executedQty":"0.000",
               "avgPrice":"0","price":"0","stopPrice":"90000","timeInForce":"GTC"}

def make_manager():
    client = MagicMock()
    return OrderManager(client=client), client

class TestPlaceMarketOrder(unittest.TestCase):

    def test_success_fields(self):
        mgr, cli = make_manager()
        cli.post.return_value = MARKET_RESP
        r = mgr.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, 111)
        self.assertEqual(r.status, "FILLED")
        self.assertEqual(r.avg_price, "97500.00")

    def test_payload_has_no_price_key(self):
        mgr, cli = make_manager()
        cli.post.return_value = MARKET_RESP
        mgr.place_market_order("ETHUSDT", "SELL", Decimal("0.05"))
        _, payload = cli.post.call_args[0]
        self.assertEqual(payload["type"], "MARKET")
        self.assertNotIn("price", payload)

    def test_api_error_returns_failed_result(self):
        mgr, cli = make_manager()
        cli.post.side_effect = BinanceAPIError(-1121, "Invalid symbol.", 400)
        r = mgr.place_market_order("BAD", "BUY", Decimal("0.001"))
        self.assertFalse(r.success)
        self.assertEqual(r.error_code, -1121)
        self.assertIn("Invalid symbol", r.error_message)

    def test_network_error_propagates(self):
        import requests
        mgr, cli = make_manager()
        cli.post.side_effect = requests.exceptions.ConnectionError("timeout")
        with self.assertRaises(requests.exceptions.ConnectionError):
            mgr.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))

class TestPlaceLimitOrder(unittest.TestCase):

    def test_success_fields(self):
        mgr, cli = make_manager()
        cli.post.return_value = LIMIT_RESP
        r = mgr.place_limit_order("BTCUSDT", "SELL", Decimal("0.001"), Decimal("100000"), "GTC")
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, 222)
        self.assertEqual(r.status, "NEW")
        self.assertEqual(r.price, "100000.00")

    def test_payload_correct(self):
        mgr, cli = make_manager()
        cli.post.return_value = LIMIT_RESP
        mgr.place_limit_order("BTCUSDT", "BUY", Decimal("0.002"), Decimal("85000"), "IOC")
        _, payload = cli.post.call_args[0]
        self.assertEqual(payload["type"], "LIMIT")
        self.assertEqual(payload["price"], "85000")
        self.assertEqual(payload["timeInForce"], "IOC")
        self.assertEqual(payload["quantity"], "0.002")

    def test_api_error_returns_failed_result(self):
        mgr, cli = make_manager()
        cli.post.side_effect = BinanceAPIError(-1013, "Invalid quantity.", 400)
        r = mgr.place_limit_order("BTCUSDT", "BUY", Decimal("999999"), Decimal("100000"))
        self.assertFalse(r.success)
        self.assertEqual(r.error_code, -1013)

class TestPlaceStopMarketOrder(unittest.TestCase):

    def test_success_fields(self):
        mgr, cli = make_manager()
        cli.post.return_value = STOP_RESP
        r = mgr.place_stop_market_order("BTCUSDT", "SELL", Decimal("0.001"), Decimal("90000"))
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, 333)
        self.assertEqual(r.order_type, "STOP_MARKET")

    def test_payload_has_stop_price(self):
        mgr, cli = make_manager()
        cli.post.return_value = STOP_RESP
        mgr.place_stop_market_order("BTCUSDT", "SELL", Decimal("0.001"), Decimal("90000"))
        _, payload = cli.post.call_args[0]
        self.assertEqual(payload["type"], "STOP_MARKET")
        self.assertEqual(payload["stopPrice"], "90000")
        self.assertNotIn("price", payload)

class TestOrderResult(unittest.TestCase):

    def test_from_api_response(self):
        r = OrderResult.from_api_response(MARKET_RESP)
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, 111)
        self.assertEqual(r.raw, MARKET_RESP)

    def test_from_error(self):
        err = BinanceAPIError(-2019, "Margin is insufficient.", 400)
        r = OrderResult.from_error(err)
        self.assertFalse(r.success)
        self.assertEqual(r.error_code, -2019)
        self.assertEqual(r.error_message, "Margin is insufficient.")
        self.assertIsNone(r.order_id)

if __name__ == "__main__": unittest.main()
