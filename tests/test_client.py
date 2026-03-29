"""
tests/test_client.py — Unit tests for BinanceFuturesClient (no network needed).
Run: python -m unittest discover tests/   OR   pytest tests/ -v
"""
import unittest
from unittest.mock import MagicMock
from bot.client import BinanceFuturesClient, BinanceAPIError

KEY, SECRET = "test_key", "test_secret"

def make_client(): return BinanceFuturesClient(api_key=KEY, api_secret=SECRET)

def mock_response(json_data, status_code=200):
    r = MagicMock()
    r.json.return_value = json_data
    r.status_code = status_code
    r.ok = status_code < 400
    r.text = str(json_data)
    r.request.method = "POST"
    r.url = "https://testnet.binancefuture.com/fapi/v1/order"
    return r

class TestConstructor(unittest.TestCase):
    def test_empty_key_raises(self):
        with self.assertRaises(ValueError): BinanceFuturesClient(api_key="", api_secret="s")
    def test_empty_secret_raises(self):
        with self.assertRaises(ValueError): BinanceFuturesClient(api_key="k", api_secret="")
    def test_trailing_slash_stripped(self):
        c = BinanceFuturesClient(api_key="k", api_secret="s",
                                  base_url="https://testnet.binancefuture.com/")
        self.assertFalse(c.base_url.endswith("/"))

class TestSign(unittest.TestCase):
    def test_signature_added(self):
        signed = make_client()._sign({"symbol": "BTCUSDT"})
        self.assertIn("signature", signed)

    def test_timestamp_added(self):
        self.assertIn("timestamp", make_client()._sign({}))

    def test_recv_window_added(self):
        self.assertIn("recvWindow", make_client()._sign({}))

    def test_does_not_mutate_original(self):
        original = {"symbol": "BTCUSDT"}
        make_client()._sign(original)
        self.assertNotIn("signature", original)

    def test_signature_is_64_char_hex(self):
        sig = make_client()._sign({})["signature"]
        self.assertEqual(len(sig), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))

class TestHandleResponse(unittest.TestCase):
    def test_success_returned(self):
        data = {"orderId": 999, "status": "FILLED"}
        result = make_client()._handle_response(mock_response(data, 200))
        self.assertEqual(result["orderId"], 999)

    def test_negative_code_raises(self):
        data = {"code": -1121, "msg": "Invalid symbol."}
        with self.assertRaises(BinanceAPIError) as ctx:
            make_client()._handle_response(mock_response(data, 400))
        self.assertEqual(ctx.exception.code, -1121)
        self.assertIn("Invalid symbol", ctx.exception.message)

    def test_non_json_raises(self):
        r = MagicMock()
        r.json.side_effect = ValueError("No JSON")
        r.text = "<html>Error</html>"
        r.status_code = 500
        r.ok = False
        r.request.method = "GET"
        r.url = "https://testnet.binancefuture.com/fapi/v1/ping"
        with self.assertRaises(BinanceAPIError) as ctx:
            make_client()._handle_response(r)
        self.assertEqual(ctx.exception.code, -1)

    def test_http_error_without_code_raises(self):
        data = {"msg": "Service unavailable"}
        r = mock_response(data, 503)
        r.ok = False
        with self.assertRaises(BinanceAPIError):
            make_client()._handle_response(r)

    def test_positive_code_in_response_not_treated_as_error(self):
        # Some Binance endpoints return {"code": 200, ...} — must NOT raise
        data = {"code": 200, "msg": "success", "orderId": 42}
        result = make_client()._handle_response(mock_response(data, 200))
        self.assertEqual(result["orderId"], 42)

if __name__ == "__main__": unittest.main()
