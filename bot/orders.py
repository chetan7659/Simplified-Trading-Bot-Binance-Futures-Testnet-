"""
Order placement logic — the business layer.

This module knows about order types, constructs the correct payload,
delegates HTTP to BinanceFuturesClient, and returns a normalised
OrderResult dataclass so the CLI layer never has to touch raw dicts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional

from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.logging_config import get_logger

logger = get_logger(__name__)

ORDER_ENDPOINT = "/fapi/v1/order"


@dataclass
class OrderResult:
    """Normalised view of a Binance order response."""

    success: bool
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    status: Optional[str] = None
    orig_qty: Optional[str] = None
    executed_qty: Optional[str] = None
    avg_price: Optional[str] = None
    price: Optional[str] = None
    time_in_force: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[int] = None
    error_message: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "OrderResult":
        return cls(
            success=True,
            order_id=data.get("orderId"),
            client_order_id=data.get("clientOrderId"),
            symbol=data.get("symbol"),
            side=data.get("side"),
            order_type=data.get("type"),
            status=data.get("status"),
            orig_qty=data.get("origQty"),
            executed_qty=data.get("executedQty"),
            avg_price=data.get("avgPrice"),
            price=data.get("price"),
            time_in_force=data.get("timeInForce"),
            raw=data,
        )

    @classmethod
    def from_error(cls, error: BinanceAPIError) -> "OrderResult":
        return cls(
            success=False,
            error_code=error.code,
            error_message=error.message,
        )


class OrderManager:
    """
    High-level order API.

    All public methods log the request summary, call the client, log the
    response, and return an OrderResult.
    """

    def __init__(self, client: BinanceFuturesClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Place a MARKET order."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": str(quantity),
        }
        logger.info(
            "Placing MARKET order | symbol=%s side=%s qty=%s",
            symbol, side, quantity,
        )
        return self._execute(params)

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """Place a LIMIT order (Good-Till-Cancelled by default)."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": str(quantity),
            "price": str(price),
            "timeInForce": time_in_force,
        }
        logger.info(
            "Placing LIMIT order | symbol=%s side=%s qty=%s price=%s tif=%s",
            symbol, side, quantity, price, time_in_force,
        )
        return self._execute(params)

    def place_stop_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
    ) -> OrderResult:
        """
        Bonus: Place a STOP_MARKET order.
        Triggered when the market reaches stop_price; fills at market.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "quantity": str(quantity),
            "stopPrice": str(stop_price),
        }
        logger.info(
            "Placing STOP_MARKET order | symbol=%s side=%s qty=%s stopPrice=%s",
            symbol, side, quantity, stop_price,
        )
        return self._execute(params)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute(self, params: Dict[str, Any]) -> OrderResult:
        """Send the order, handle exceptions, return an OrderResult."""
        logger.debug("Order request payload: %s", json.dumps(params, indent=2))
        try:
            response = self._client.post(ORDER_ENDPOINT, params)
            logger.info("Order accepted | orderId=%s status=%s", response.get("orderId"), response.get("status"))
            logger.debug("Order response payload: %s", json.dumps(response, indent=2))
            return OrderResult.from_api_response(response)

        except BinanceAPIError as exc:
            logger.error("Binance API error | code=%s msg=%s", exc.code, exc.message)
            return OrderResult.from_error(exc)

        except Exception as exc:
            logger.exception("Unexpected error while placing order: %s", exc)
            # Re-raise so the CLI layer can catch and surface it properly.
            raise
