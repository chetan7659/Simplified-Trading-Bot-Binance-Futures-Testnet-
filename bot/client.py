"""
Binance Futures Testnet REST API client.

Responsibilities:
  - HMAC-SHA256 request signing
  - Timestamp & recvWindow management
  - HTTP transport with retries
  - Raw request/response logging
  - Surface BinanceAPIError for caller-friendly error handling
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bot.logging_config import get_logger

logger = get_logger(__name__)

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000          # ms; increase if clock skew causes -1021 errors
DEFAULT_TIMEOUT = 10        # seconds per HTTP request


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx response or an error payload."""

    def __init__(self, code: int, message: str, http_status: int = 0) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"Binance API error {code}: {message} (HTTP {http_status})")


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API.

    Usage:
        client = BinanceFuturesClient(api_key="...", api_secret="...")
        response = client.post("/fapi/v1/order", params={...})
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be non-empty strings.")

        self._api_key = api_key
        self._api_secret = api_secret.encode()   # bytes for HMAC
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = self._build_session()
        logger.info("BinanceFuturesClient initialised (base_url=%s)", self.base_url)

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session() -> requests.Session:
        """Return a requests.Session with automatic retries on transient errors."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append timestamp + recvWindow, then compute and append the HMAC-SHA256
        signature. Returns a *new* dict (never mutates the caller's dict).
        """
        signed_params = dict(params)
        signed_params["timestamp"] = int(time.time() * 1000)
        signed_params["recvWindow"] = RECV_WINDOW

        query_string = urllib.parse.urlencode(signed_params)
        signature = hmac.new(
            self._api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        signed_params["signature"] = signature
        return signed_params

    # ------------------------------------------------------------------
    # Low-level HTTP methods
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "X-MBX-APIKEY": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse JSON, raise BinanceAPIError on error payloads or bad status."""
        logger.debug(
            "HTTP %s %s → status=%s body=%s",
            response.request.method,
            response.url,
            response.status_code,
            response.text[:500],  # truncate large bodies in logs
        )

        try:
            data = response.json()
        except ValueError:
            raise BinanceAPIError(
                code=-1,
                message=f"Non-JSON response: {response.text[:200]}",
                http_status=response.status_code,
            )

        # Binance error payloads always carry a negative integer code, e.g.:
        # {"code": -1121, "msg": "Invalid symbol."}
        # Success responses never contain a "code" key, so checking < 0 is safe.
        if isinstance(data, dict) and "code" in data and int(data["code"]) < 0:
            raise BinanceAPIError(
                code=data["code"],
                message=data.get("msg", "Unknown error"),
                http_status=response.status_code,
            )

        if not response.ok:
            raise BinanceAPIError(
                code=response.status_code,
                message=response.text[:200],
                http_status=response.status_code,
            )

        return data

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Signed GET request."""
        params = params or {}
        signed = self._sign(params)
        url = f"{self.base_url}{path}"
        logger.info("GET %s params=%s", path, {k: v for k, v in params.items()})
        try:
            resp = self._session.get(url, params=signed, headers=self._headers(), timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            logger.error("Network error on GET %s: %s", path, exc)
            raise
        return self._handle_response(resp)

    def post(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Signed POST request (params sent as form-encoded body)."""
        params = params or {}
        signed = self._sign(params)
        url = f"{self.base_url}{path}"
        logger.info("POST %s params=%s", path, {k: v for k, v in params.items()})
        try:
            resp = self._session.post(url, data=signed, headers=self._headers(), timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            logger.error("Network error on POST %s: %s", path, exc)
            raise
        return self._handle_response(resp)

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if the testnet is reachable."""
        try:
            url = f"{self.base_url}/fapi/v1/ping"
            resp = self._session.get(url, timeout=self.timeout)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def get_account_info(self) -> Dict[str, Any]:
        """Fetch futures account information (balances, positions, etc.)."""
        return self.get("/fapi/v2/account")

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch exchange info; optionally filter by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        # Exchange info is public — no signing needed, but our get() always signs.
        return self.get("/fapi/v1/exchangeInfo", params)
