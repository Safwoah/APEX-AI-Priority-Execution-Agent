"""
APEX Binance Client
Connects to Binance API to fetch portfolio holdings, live prices, and account data.

This module is the #1 APEX priority for the crypto tracker goal:
  Score: 8,300 / 9,750
  Reasoning: Everything else (charts, alerts, social sharing) depends on live data.
             No sync = no product.

Usage:
  client = BinanceClient()
  client.connect(api_key="...", secret="...")
  holdings = client.get_portfolio()
  prices   = client.get_prices(["BTCUSDT", "ETHUSDT"])

Environment variables (never hardcode keys):
  BINANCE_API_KEY    — your Binance API key
  BINANCE_API_SECRET — your Binance API secret

Testnet:
  Set BINANCE_TESTNET=true to use https://testnet.binance.vision
  Get free testnet keys at: https://testnet.binance.vision
"""

import os
import time
import hmac
import hashlib
import requests
from typing import Optional
from urllib.parse import urlencode


class BinanceAuthError(Exception):
    """Raised when API credentials are missing or rejected."""
    pass


class BinanceAPIError(Exception):
    """Raised when Binance returns an error response."""
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    """
    Lightweight Binance REST client. No third-party SDK dependency —
    uses only the standard `requests` library so the dependency footprint
    stays small and the code stays readable.

    Supports:
      - Signed endpoints (account data, portfolio)
      - Public endpoints (prices, 24hr ticker)
      - Testnet mode for development without real funds
    """

    MAINNET_BASE = "https://api.binance.com"
    TESTNET_BASE = "https://testnet.binance.vision"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        testnet: Optional[bool] = None
    ):
        """
        Initialise the client. Credentials can be passed directly or
        loaded from environment variables.

        Args:
            api_key: Binance API key. Falls back to BINANCE_API_KEY env var.
            secret:  Binance secret key. Falls back to BINANCE_API_SECRET env var.
            testnet: Use testnet endpoint. Falls back to BINANCE_TESTNET env var.
        """
        self._api_key = api_key or os.environ.get("BINANCE_API_KEY", "")
        self._secret  = secret  or os.environ.get("BINANCE_API_SECRET", "")

        use_testnet = testnet if testnet is not None else (
            os.environ.get("BINANCE_TESTNET", "false").lower() == "true"
        )
        self._base_url = self.TESTNET_BASE if use_testnet else self.MAINNET_BASE
        self._testnet  = use_testnet
        self._session  = requests.Session()

    # ─────────────────────────────────────────────
    # Public methods (no auth required)
    # ─────────────────────────────────────────────

    def ping(self) -> bool:
        """Test connectivity to Binance. Returns True if reachable."""
        try:
            resp = self._get("/api/v3/ping")
            return resp == {}
        except Exception:
            return False

    def get_server_time(self) -> int:
        """Return Binance server time as Unix timestamp (ms)."""
        return self._get("/api/v3/time")["serverTime"]

    def get_price(self, symbol: str) -> float:
        """
        Get the latest price for a single trading pair.

        Args:
            symbol: Trading pair e.g. "BTCUSDT"

        Returns:
            Current price as float.

        Example:
            price = client.get_price("BTCUSDT")  # 67420.15
        """
        data = self._get("/api/v3/ticker/price", {"symbol": symbol.upper()})
        return float(data["price"])

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        Get latest prices for multiple symbols in one call.

        Args:
            symbols: List of trading pairs e.g. ["BTCUSDT", "ETHUSDT"]

        Returns:
            Dict mapping symbol -> price.

        Example:
            prices = client.get_prices(["BTCUSDT", "ETHUSDT"])
            # {"BTCUSDT": 67420.15, "ETHUSDT": 3541.88}
        """
        # Binance accepts a JSON array in the symbols param for batch fetch
        symbols_upper = [s.upper() for s in symbols]
        import json
        data = self._get("/api/v3/ticker/price", {"symbols": json.dumps(symbols_upper)})
        return {item["symbol"]: float(item["price"]) for item in data}

    def get_ticker_24h(self, symbol: str) -> dict:
        """
        Get 24-hour rolling statistics for a symbol.

        Returns dict with keys: priceChange, priceChangePercent, highPrice,
        lowPrice, volume, quoteVolume, lastPrice.
        """
        raw = self._get("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
        return {
            "symbol":              raw["symbol"],
            "price_change":        float(raw["priceChange"]),
            "price_change_pct":    float(raw["priceChangePercent"]),
            "high_24h":            float(raw["highPrice"]),
            "low_24h":             float(raw["lowPrice"]),
            "volume_base":         float(raw["volume"]),
            "volume_quote":        float(raw["quoteVolume"]),
            "last_price":          float(raw["lastPrice"]),
        }

    # ─────────────────────────────────────────────
    # Authenticated methods (require API key + secret)
    # ─────────────────────────────────────────────

    def connect(self, api_key: Optional[str] = None, secret: Optional[str] = None) -> bool:
        """
        Set credentials and verify they work against Binance.

        Args:
            api_key: Override the key set in __init__ or env var.
            secret:  Override the secret set in __init__ or env var.

        Returns:
            True if authentication succeeds.

        Raises:
            BinanceAuthError: If credentials are missing or rejected.
        """
        if api_key:
            self._api_key = api_key
        if secret:
            self._secret = secret

        if not self._api_key or not self._secret:
            raise BinanceAuthError(
                "API key and secret are required. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables, "
                "or pass them to connect()."
            )

        # Verify credentials by hitting account endpoint
        try:
            self._get_signed("/api/v3/account", {"omitZeroBalances": "true"})
            mode = "TESTNET" if self._testnet else "MAINNET"
            print(f"✅ Binance connected ({mode})")
            return True
        except BinanceAPIError as e:
            raise BinanceAuthError(f"Credential verification failed: {e}") from e

    def get_account(self) -> dict:
        """
        Fetch full account info including balances.

        Returns:
            Dict with keys: maker_commission, taker_commission,
            can_trade, can_withdraw, can_deposit, balances.
        """
        raw = self._get_signed("/api/v3/account", {"omitZeroBalances": "true"})
        return {
            "maker_commission":  raw["makerCommission"],
            "taker_commission":  raw["takerCommission"],
            "can_trade":         raw["canTrade"],
            "can_withdraw":      raw["canWithdraw"],
            "can_deposit":       raw["canDeposit"],
            "balances":          [
                {
                    "asset":  b["asset"],
                    "free":   float(b["free"]),
                    "locked": float(b["locked"]),
                    "total":  float(b["free"]) + float(b["locked"]),
                }
                for b in raw["balances"]
            ]
        }

    def get_portfolio(self, quote_currency: str = "USDT") -> list[dict]:
        """
        Get portfolio holdings with current USD value.

        Fetches non-zero balances and enriches each with current price
        and total value in the quote currency (default USDT).

        Args:
            quote_currency: The currency to value holdings in (default "USDT").

        Returns:
            List of dicts sorted by value descending:
            [{"asset": "BTC", "total": 0.5, "price_usdt": 67420.0, "value_usdt": 33710.0}, ...]

        Example:
            portfolio = client.get_portfolio()
            total_value = sum(h["value_usdt"] for h in portfolio)
        """
        account   = self.get_account()
        balances  = account["balances"]

        # Build list of symbols to price (skip stablecoins priced at ~1)
        STABLECOINS = {"USDT", "BUSD", "USDC", "TUSD", "DAI", "FDUSD"}
        to_price    = []
        result      = []

        for balance in balances:
            asset = balance["asset"]
            total = balance["total"]
            if total <= 0:
                continue

            if asset in STABLECOINS or asset == quote_currency:
                result.append({
                    "asset":           asset,
                    "free":            balance["free"],
                    "locked":          balance["locked"],
                    "total":           total,
                    f"price_{quote_currency.lower()}": 1.0,
                    f"value_{quote_currency.lower()}": total,
                })
            else:
                symbol = f"{asset}{quote_currency}"
                to_price.append((asset, symbol, total, balance))

        # Batch-fetch prices for non-stablecoins
        if to_price:
            symbols    = [row[1] for row in to_price]
            try:
                price_map  = self.get_prices(symbols)
            except Exception:
                price_map  = {}

            for asset, symbol, total, balance in to_price:
                price = price_map.get(symbol)
                result.append({
                    "asset":           asset,
                    "free":            balance["free"],
                    "locked":          balance["locked"],
                    "total":           total,
                    f"price_{quote_currency.lower()}": price,
                    f"value_{quote_currency.lower()}": round(price * total, 2) if price else None,
                })

        # Sort by value descending (None values go to the bottom)
        key = f"value_{quote_currency.lower()}"
        result.sort(key=lambda x: x[key] or 0, reverse=True)
        return result

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """
        Get all open orders, optionally filtered by symbol.

        Args:
            symbol: Trading pair to filter by. If None, returns all open orders.
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._get_signed("/api/v3/openOrders", params)

    # ─────────────────────────────────────────────
    # Internal HTTP helpers
    # ─────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        """Unsigned GET request."""
        url  = f"{self._base_url}{path}"
        resp = self._session.get(url, params=params or {}, timeout=10)
        return self._handle_response(resp)

    def _get_signed(self, path: str, params: Optional[dict] = None) -> dict | list:
        """Signed GET request — required for account/order endpoints."""
        if not self._api_key or not self._secret:
            raise BinanceAuthError("Call connect() before accessing account endpoints.")

        p = params or {}
        p["timestamp"]  = int(time.time() * 1000)
        p["recvWindow"] = 5000
        p["signature"]  = self._sign(urlencode(p))

        url  = f"{self._base_url}{path}"
        resp = self._session.get(
            url,
            params=p,
            headers={"X-MBX-APIKEY": self._api_key},
            timeout=10
        )
        return self._handle_response(resp)

    def _sign(self, query_string: str) -> str:
        """HMAC-SHA256 signature required by all signed Binance endpoints."""
        return hmac.new(
            self._secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _handle_response(resp: requests.Response) -> dict | list:
        """Parse response, raise BinanceAPIError on non-200."""
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            return {}

        if isinstance(data, dict) and "code" in data and data["code"] < 0:
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        resp.raise_for_status()
        return data


# ─────────────────────────────────────────────
# Quick connectivity test (run directly)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("APEX Binance Client — connectivity test")
    print("=" * 45)

    bc = BinanceClient()

    # Public ping (no auth)
    ok = bc.ping()
    print(f"Ping: {'OK' if ok else 'FAILED'}")

    # Live BTC price (no auth)
    try:
        price = bc.get_price("BTCUSDT")
        print(f"BTC/USDT: ${price:,.2f}")

        ticker = bc.get_ticker_24h("BTCUSDT")
        print(f"24h change: {ticker['price_change_pct']:+.2f}%")
    except Exception as e:
        print(f"Price fetch failed: {e}")

    # Authenticated: portfolio (requires keys)
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")

    if api_key and api_secret:
        try:
            bc.connect()
            portfolio = bc.get_portfolio()
            total_value = sum(h.get("value_usdt") or 0 for h in portfolio)
            print(f"\nPortfolio ({len(portfolio)} assets):")
            for holding in portfolio[:5]:  # Top 5
                val = holding.get("value_usdt")
                val_str = f"${val:,.2f}" if val else "price unavailable"
                print(f"  {holding['asset']:<8} {holding['total']:.6f}  =  {val_str}")
            if len(portfolio) > 5:
                print(f"  ... and {len(portfolio) - 5} more")
            print(f"\nTotal portfolio value: ${total_value:,.2f} USDT")
        except BinanceAuthError as e:
            print(f"\nAuth failed: {e}")
    else:
        print("\nSkipping portfolio test — set BINANCE_API_KEY and BINANCE_API_SECRET to test auth.")
        print("Free testnet keys: https://testnet.binance.vision (set BINANCE_TESTNET=true)")
