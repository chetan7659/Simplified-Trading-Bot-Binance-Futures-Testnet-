# FuturesBot — Binance USDT-M Futures Testnet Trading Bot

A structured Python CLI + Web UI for placing orders on the Binance Futures Testnet.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package metadata
│   ├── client.py            # Binance REST API client (HMAC signing, retries, error handling)
│   ├── orders.py            # Order placement logic + OrderResult dataclass
│   ├── validators.py        # Pure input validation functions
│   └── logging_config.py   # Rotating file + console logging setup
├── web/
│   ├── app.py               # Flask backend (REST API endpoints)
│   └── templates/
│       └── index.html       # Dashboard (order form, balance, history)
├── tests/
│   ├── test_validators.py   # 26 validator unit tests
│   ├── test_orders.py       # 13 OrderManager unit tests (mocked API)
│   └── test_client.py       # 13 client unit tests (mocked HTTP)
├── logs/
│   ├── market_order_sample.log
│   └── limit_order_sample.log
├── cli.py                   # CLI entry point (argparse)
├── .env.example             # Credential template
├── .gitignore
├── render.yaml              # One-click Render.com deployment
├── Procfile
└── requirements.txt
```

### Architectural Layers

| Layer | File | Does |
|---|---|---|
| Transport | `bot/client.py` | HMAC signing, HTTP, retries, raw logging |
| Business | `bot/orders.py` | Constructs payloads, normalises responses |
| Validation | `bot/validators.py` | Raises `ValueError` on bad input |
| CLI | `cli.py` | Parses args, formats output |
| Web | `web/app.py` + `index.html` | Flask API + dashboard |

---

## Setup

### 1. Get Testnet Credentials

1. Visit [testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Sign in with GitHub
3. Go to **API Management → Create API**
4. Copy your **API Key** and **Secret Key**

### 2. Install

```bash
git clone https://github.com/your-username/trading-bot.git
cd trading_bot

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure Credentials

```bash
cp .env.example .env
# Edit .env and add your keys, then:

export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_secret_key"
```

---

## Running — CLI

### Check connectivity
```bash
python cli.py ping
```

### View account balance
```bash
python cli.py account-info
```

### Place a MARKET order
```bash
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --qty 0.001
```

### Place a LIMIT order
```bash
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 100000
```

### Place a STOP_MARKET order (bonus)
```bash
python cli.py place-order --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.001 --stop-price 90000
```

### Time-in-force options for LIMIT orders
```bash
# GTC (default), IOC, FOK
python cli.py place-order --symbol ETHUSDT --side BUY --type LIMIT --qty 0.01 --price 2500 --tif IOC
```

### Get full help
```bash
python cli.py --help
python cli.py place-order --help
```

---

## Running — Web Dashboard

```bash
python web/app.py
# Open http://localhost:5000
```

The dashboard provides:
- 🟢 Live testnet connection status
- 💰 Account balance panel (wallet, available, unrealised PnL)
- 📋 Order form (symbol, BUY/SELL toggle, type, qty, price)
- 📊 Order history table with colour-coded status chips
- ✅ / ❌ Toast notifications on success or failure

---

## Running Tests

```bash
# No external test runner required — uses Python stdlib unittest
python -m unittest discover tests/ -v

# Or with pytest if installed
pytest tests/ -v
```

Expected output: **66 tests, 0 failures**

---

## Sample CLI Output

```
────────────────────────────────────────────────────────────
  Order Request Summary
────────────────────────────────────────────────────────────
  Symbol:                       BTCUSDT
  Side:                         BUY
  Order Type:                   MARKET
  Quantity:                     0.001

────────────────────────────────────────────────────────────
  Order Placed Successfully
────────────────────────────────────────────────────────────
  Order ID:                     4174515336
  Symbol:                       BTCUSDT
  Side:                         BUY
  Type:                         MARKET
  Status:                       FILLED
  Original Qty:                 0.001
  Executed Qty:                 0.001
  Avg Fill Price:               97842.50

  ✓  Order accepted by the exchange.
```

---

## Logging

All activity is written to `logs/trading_bot.log` (rotating, 5 MB × 3 backups).

```
2025-01-15 10:23:41 | INFO     | bot.orders | Placing MARKET order | symbol=BTCUSDT side=BUY qty=0.001
2025-01-15 10:23:41 | INFO     | bot.client | POST /fapi/v1/order params={...}
2025-01-15 10:23:41 | INFO     | bot.orders | Order accepted | orderId=4174515336 status=FILLED
```

Set `LOG_LEVEL=DEBUG` to see full request/response JSON payloads.

---

## Deploy to Render (free public URL)

1. Push to GitHub
2. [render.com](https://render.com) → **New Web Service** → connect repo
3. Render auto-reads `render.yaml`
4. Add env vars in the Render dashboard:
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`
5. Deploy → get `https://your-app.onrender.com`

---

## Assumptions & Design Decisions

| Decision | Reason |
|---|---|
| Direct `requests` over `python-binance` | Full control over signing, retries, error parsing |
| `Decimal` for all prices and quantities | Floating-point arithmetic is unsafe in financial code |
| `OrderResult` dataclass | CLI and Web layers never touch raw API dicts — resilient to response changes |
| Credentials via env vars | Never hardcoded; `.env.example` provided as template |
| Validation raises `ValueError` | Business layer is completely decoupled from CLI/web |
| Rotating log file (5 MB × 3) | Production-safe; won't fill disk on long runs |
| `code < 0` for Binance error detection | Binance error payloads always have negative codes; success responses never carry a `code` field |
| Tests use stdlib `unittest` only | Zero extra dependencies needed to run the test suite |
| Testnet base URL hardcoded | Safety guard — prevents accidental mainnet orders |
