"""
Input validation layer.

All validation functions raise ValueError with a human-readable message so
the CLI layer can catch them and print a clean error without a traceback.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}   # extend as needed


def validate_symbol(symbol: str) -> str:
    """Normalise and sanity-check a trading pair symbol."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol must not be empty.")
    if not symbol.isalpha():
        raise ValueError(
            f"Invalid symbol '{symbol}'. Only letters are allowed (e.g. BTCUSDT)."
        )
    if len(symbol) < 5 or len(symbol) > 20:
        raise ValueError(
            f"Invalid symbol '{symbol}'. Length must be between 5 and 20 characters."
        )
    return symbol


def validate_side(side: str) -> str:
    """Ensure the order side is BUY or SELL."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}"
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Ensure the order type is supported."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}"
        )
    return order_type


def validate_quantity(quantity: str | float) -> Decimal:
    """Parse and validate the order quantity — must be positive."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero, got {qty}.")
    return qty


def validate_price(price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """
    Parse and validate the limit price.
    - Required for LIMIT orders.
    - Must be None / empty / omitted for MARKET orders.
    """
    # Normalise: empty string → None
    if isinstance(price, str) and not price.strip():
        price = None

    if order_type == "LIMIT":
        if price is None:
            raise ValueError("Price is required for LIMIT orders.")
        try:
            p = Decimal(str(price))
        except InvalidOperation:
            raise ValueError(f"Invalid price '{price}'. Must be a positive number.")
        if p <= 0:
            raise ValueError(f"Price must be greater than zero, got {p}.")
        return p

    if order_type == "MARKET" and price is not None:
        raise ValueError("Price must not be provided for MARKET orders.")

    return None


def validate_stop_price(stop_price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """Validate stop price for STOP_MARKET orders."""
    # Normalise: empty string → None
    if isinstance(stop_price, str) and not stop_price.strip():
        stop_price = None

    if order_type == "STOP_MARKET":
        if stop_price is None:
            raise ValueError("stopPrice is required for STOP_MARKET orders.")
        try:
            sp = Decimal(str(stop_price))
        except InvalidOperation:
            raise ValueError(f"Invalid stop price '{stop_price}'. Must be a positive number.")
        if sp <= 0:
            raise ValueError(f"Stop price must be greater than zero, got {sp}.")
        return sp
    return None
