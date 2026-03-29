#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Binance Futures Testnet Trading Bot.

Usage examples:
  python cli.py place-order --symbol BTCUSDT --side BUY  --type MARKET --qty 0.001
  python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT  --qty 0.001 --price 80000
  python cli.py place-order --symbol ETHUSDT --side BUY  --type STOP_MARKET --qty 0.01 --stop-price 2000
  python cli.py account-info
  python cli.py ping
"""
from __future__ import annotations
# from dotenv import load_dotenv
# load_dotenv()   # loads .env into os.environ automatically


import argparse
import json
import os
import sys
from decimal import Decimal
from typing import Optional

from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderManager, OrderResult
from bot.validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)

# ---------------------------------------------------------------------------
# Logging is set up before anything else so all imports are covered.
# ---------------------------------------------------------------------------
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Console output helpers  (rich-free, zero extra deps)
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
DIM    = "\033[2m"


def _c(color: str, text: str) -> str:
    """Wrap text in ANSI colour codes (gracefully skipped when not a TTY)."""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def print_header(title: str) -> None:
    width = 60
    print()
    print(_c(CYAN, "─" * width))
    print(_c(CYAN + BOLD, f"  {title}"))
    print(_c(CYAN, "─" * width))


def print_kv(key: str, value: str, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{_c(DIM, key + ':'):<30}{_c(BOLD, value)}")


def print_success(msg: str) -> None:
    print()
    print(_c(GREEN, f"  ✓  {msg}"))
    print()


def print_failure(msg: str) -> None:
    print()
    print(_c(RED, f"  ✗  {msg}"))
    print()


def print_order_result(result: OrderResult) -> None:
    """Pretty-print an OrderResult to stdout."""
    if result.success:
        print_header("Order Placed Successfully")
        print_kv("Order ID",       str(result.order_id))
        print_kv("Client Order ID", str(result.client_order_id))
        print_kv("Symbol",         str(result.symbol))
        print_kv("Side",           str(result.side))
        print_kv("Type",           str(result.order_type))
        print_kv("Status",         str(result.status))
        print_kv("Original Qty",   str(result.orig_qty))
        print_kv("Executed Qty",   str(result.executed_qty))
        avg = result.avg_price if result.avg_price and result.avg_price != "0" else "N/A (pending)"
        print_kv("Avg Fill Price", avg)
        if result.price and result.price != "0":
            print_kv("Limit Price",   str(result.price))
        if result.time_in_force:
            print_kv("Time In Force", str(result.time_in_force))
        print_success("Order accepted by the exchange.")
    else:
        print_header("Order Failed")
        print_kv("Error Code",    str(result.error_code))
        print_kv("Error Message", str(result.error_message))
        print_failure("Order was rejected. See logs for details.")


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def _load_credentials() -> tuple[str, str]:
    """
    Load API credentials from environment variables.
    Raises SystemExit with a clear message if they are missing.
    """
    api_key    = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print(_c(RED, "\n  Error: BINANCE_API_KEY and BINANCE_API_SECRET must be set.\n"))
        print("  Export them before running:")
        print('    export BINANCE_API_KEY="your_key"')
        print('    export BINANCE_API_SECRET="your_secret"\n')
        sys.exit(1)
    return api_key, api_secret


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def cmd_place_order(args: argparse.Namespace) -> int:
    """Validate inputs, place order, print results. Returns exit code."""
    # --- Validate all inputs up-front before touching the network ---
    try:
        symbol     = validate_symbol(args.symbol)
        side       = validate_side(args.side)
        order_type = validate_order_type(args.type)
        quantity   = validate_quantity(args.qty)
        price      = validate_price(args.price, order_type)
        stop_price = validate_stop_price(getattr(args, "stop_price", None), order_type)
    except ValueError as exc:
        print(_c(RED, f"\n  Validation error: {exc}\n"))
        logger.warning("Input validation failed: %s", exc)
        return 1

    # --- Print order request summary ---
    print_header("Order Request Summary")
    print_kv("Symbol",     symbol)
    print_kv("Side",       side)
    print_kv("Order Type", order_type)
    print_kv("Quantity",   str(quantity))
    if price is not None:
        print_kv("Limit Price", str(price))
    if stop_price is not None:
        print_kv("Stop Price",  str(stop_price))

    # --- Build client & manager ---
    api_key, api_secret = _load_credentials()
    client  = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    manager = OrderManager(client)

    # --- Route to correct placement method ---
    try:
        if order_type == "MARKET":
            result = manager.place_market_order(symbol, side, quantity)
        elif order_type == "LIMIT":
            tif    = getattr(args, "time_in_force", "GTC") or "GTC"
            result = manager.place_limit_order(symbol, side, quantity, price, tif)
        elif order_type == "STOP_MARKET":
            result = manager.place_stop_market_order(symbol, side, quantity, stop_price)
        else:
            print(_c(RED, f"\n  Unsupported order type: {order_type}\n"))
            return 1
    except Exception as exc:
        print(_c(RED, f"\n  Unexpected error: {exc}\n"))
        logger.exception("Unhandled exception in cmd_place_order")
        return 1

    print_order_result(result)
    return 0 if result.success else 1


def cmd_account_info(args: argparse.Namespace) -> int:
    """Print futures account balances and summary."""
    api_key, api_secret = _load_credentials()
    client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    try:
        info = client.get_account_info()
        print_header("Account Information")
        print_kv("Total Wallet Balance",     info.get("totalWalletBalance", "N/A"))
        print_kv("Total Unrealised PnL",     info.get("totalUnrealizedProfit", "N/A"))
        print_kv("Total Margin Balance",     info.get("totalMarginBalance", "N/A"))
        print_kv("Available Balance",        info.get("availableBalance", "N/A"))
        print_kv("Total Position Initial Margin", info.get("totalPositionInitialMargin", "N/A"))

        assets = [a for a in info.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        if assets:
            print()
            print(_c(CYAN, "  Non-zero Asset Balances:"))
            for a in assets:
                print_kv(a["asset"], a["walletBalance"], indent=4)
        print()
        return 0
    except BinanceAPIError as exc:
        print(_c(RED, f"\n  API error {exc.code}: {exc.message}\n"))
        return 1
    except Exception as exc:
        print(_c(RED, f"\n  Unexpected error: {exc}\n"))
        logger.exception("Unhandled exception in cmd_account_info")
        return 1


def cmd_ping(args: argparse.Namespace) -> int:
    """Check if the testnet is reachable."""
    api_key, api_secret = _load_credentials()
    client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    if client.ping():
        print(_c(GREEN, "\n  ✓  Binance Futures Testnet is reachable.\n"))
        return 0
    else:
        print(_c(RED, "\n  ✗  Could not reach Binance Futures Testnet.\n"))
        return 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py ping
  python cli.py account-info
  python cli.py place-order --symbol BTCUSDT --side BUY  --type MARKET --qty 0.001
  python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT  --qty 0.001 --price 80000
  python cli.py place-order --symbol ETHUSDT --side BUY  --type STOP_MARKET --qty 0.01 --stop-price 2000

Environment variables:
  BINANCE_API_KEY     — your testnet API key   (required)
  BINANCE_API_SECRET  — your testnet secret     (required)
  LOG_LEVEL           — DEBUG / INFO / WARNING  (default: INFO)
        """,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- ping ---
    sub.add_parser("ping", help="Check testnet connectivity")

    # --- account-info ---
    sub.add_parser("account-info", help="Show futures account balances")

    # --- place-order ---
    po = sub.add_parser("place-order", help="Place a futures order")
    po.add_argument("--symbol",    required=True,  metavar="SYM",  help="Trading pair, e.g. BTCUSDT")
    po.add_argument("--side",      required=True,  metavar="SIDE", help="BUY or SELL")
    po.add_argument("--type",      required=True,  metavar="TYPE", help="MARKET, LIMIT, or STOP_MARKET")
    po.add_argument("--qty",       required=True,  metavar="QTY",  type=str, help="Order quantity")
    po.add_argument("--price",     required=False, metavar="PX",   type=str, default=None,
                    help="Limit price (required for LIMIT orders)")
    po.add_argument("--stop-price", dest="stop_price", required=False, metavar="SPX", type=str, default=None,
                    help="Stop trigger price (required for STOP_MARKET orders)")
    po.add_argument("--tif",       dest="time_in_force", required=False, default="GTC",
                    choices=["GTC", "IOC", "FOK"], help="Time-in-force for LIMIT orders (default: GTC)")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "ping":         cmd_ping,
        "account-info": cmd_account_info,
        "place-order":  cmd_place_order,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = handler(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
