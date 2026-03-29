"""
web/app.py — Flask web application layer.

Wraps the existing bot/ layer behind a REST JSON API.
The frontend (HTML/JS) talks to these endpoints.
"""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()   # loads .env into os.environ automatically


import os
import sys
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# Make sure bot/ is importable when running from web/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderManager
from bot.validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)

setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = Flask(__name__)
CORS(app)

# In-memory order history (per-session; swap for SQLite for persistence)
_order_history: list[Dict[str, Any]] = []


def _get_client() -> BinanceFuturesClient:
    api_key    = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise EnvironmentError("BINANCE_API_KEY and BINANCE_API_SECRET are not set.")
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API — status
# ---------------------------------------------------------------------------

@app.route("/api/ping")
def api_ping():
    try:
        client = _get_client()
        ok = client.ping()
        return jsonify({"status": "ok" if ok else "unreachable", "connected": ok})
    except EnvironmentError as exc:
        return jsonify({"status": "no_credentials", "connected": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Ping failed")
        return jsonify({"status": "error", "connected": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — account
# ---------------------------------------------------------------------------

@app.route("/api/account")
def api_account():
    try:
        client = _get_client()
        info   = client.get_account_info()
        assets = [
            {"asset": a["asset"], "balance": a["walletBalance"]}
            for a in info.get("assets", [])
            if float(a.get("walletBalance", 0)) > 0
        ]
        return jsonify({
            "totalWalletBalance":          info.get("totalWalletBalance", "0"),
            "totalUnrealizedProfit":       info.get("totalUnrealizedProfit", "0"),
            "totalMarginBalance":          info.get("totalMarginBalance", "0"),
            "availableBalance":            info.get("availableBalance", "0"),
            "totalPositionInitialMargin":  info.get("totalPositionInitialMargin", "0"),
            "assets": assets,
        })
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 400
    except BinanceAPIError as exc:
        return jsonify({"error": f"API {exc.code}: {exc.message}"}), 400
    except Exception as exc:
        logger.exception("Account fetch failed")
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — place order
# ---------------------------------------------------------------------------

@app.route("/api/order", methods=["POST"])
def api_place_order():
    body = request.get_json(force=True) or {}

    # Validate
    try:
        symbol     = validate_symbol(body.get("symbol", ""))
        side       = validate_side(body.get("side", ""))
        order_type = validate_order_type(body.get("orderType", ""))
        quantity   = validate_quantity(body.get("quantity", ""))
        price      = validate_price(body.get("price") or None, order_type)
        stop_price = validate_stop_price(body.get("stopPrice") or None, order_type)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    try:
        client  = _get_client()
        manager = OrderManager(client)

        if order_type == "MARKET":
            result = manager.place_market_order(symbol, side, quantity)
        elif order_type == "LIMIT":
            tif    = body.get("timeInForce", "GTC") or "GTC"
            result = manager.place_limit_order(symbol, side, quantity, price, tif)
        elif order_type == "STOP_MARKET":
            result = manager.place_stop_market_order(symbol, side, quantity, stop_price)
        else:
            return jsonify({"success": False, "error": f"Unsupported order type: {order_type}"}), 400

    except EnvironmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Order placement failed")
        return jsonify({"success": False, "error": str(exc)}), 500

    # Store in history
    entry = {
        "timestamp":    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol":       symbol,
        "side":         side,
        "orderType":    order_type,
        "quantity":     str(quantity),
        "price":        str(price) if price else "—",
        "stopPrice":    str(stop_price) if stop_price else "—",
        "success":      result.success,
        "orderId":      result.order_id,
        "status":       result.status,
        "executedQty":  result.executed_qty,
        "avgPrice":     result.avg_price,
        "errorMessage": result.error_message,
    }
    _order_history.insert(0, entry)

    if result.success:
        return jsonify({"success": True, "order": entry})
    else:
        return jsonify({"success": False, "error": result.error_message, "order": entry}), 400


# ---------------------------------------------------------------------------
# API — order history
# ---------------------------------------------------------------------------

@app.route("/api/orders")
def api_order_history():
    return jsonify(_order_history)

@app.route("/api/market")
def api_market():
    """Fetch live prices for popular symbols."""
    try:
        client = _get_client()
        # Get ticker prices for key symbols
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
        prices = []
        for symbol in symbols:
            try:
                data = client.get(f"/fapi/v1/ticker/24hr", {"symbol": symbol})
                prices.append({
                    "symbol":        symbol.replace("USDT", ""),
                    "full":          symbol,
                    "price":         float(data.get("lastPrice", 0)),
                    "change":        float(data.get("priceChangePercent", 0)),
                    "high":          float(data.get("highPrice", 0)),
                    "low":           float(data.get("lowPrice", 0)),
                    "volume":        float(data.get("volume", 0)),
                })
            except Exception:
                continue
        return jsonify(prices)
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Market data fetch failed")
        return jsonify({"error": str(exc)}), 500
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Flask server on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
