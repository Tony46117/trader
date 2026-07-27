"""Market data fetching module.
Fetches live and historical data for forex, commodities, and crypto.
"""

import time
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import ccxt
import requests

from config import PAIRS, CROSS_ASSETS, CACHE_DIR


_YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Map interval names to Yahoo's interval parameter values
_YAHOO_INTERVALS = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "60m", "1d": "1d", "5d": "5d",
    "1wk": "1wk", "1mo": "1mo",
}

# Map period names to Yahoo's range parameter values
_YAHOO_RANGES = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y",
    "ytd": "ytd", "max": "max",
}


def fetch_yahoo_data(ticker, period="1mo", interval="1h"):
    """Fetch OHLCV data from Yahoo Finance via direct REST API.
    Uses proper browser User-Agent to avoid blocking.
    Falls back to empty DataFrame on any failure.
    """
    cache_key = f"yahoo_{ticker}_{period}_{interval}".replace("^", "_").replace("=", "_")
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    # Check cache (5-minute freshness)
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 300:
            with open(cache_path) as f:
                return pd.read_json(f)

    try:
        yahoo_range = _YAHOO_RANGES.get(period, "1mo")
        yahoo_interval = _YAHOO_INTERVALS.get(interval, "60m")

        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range={yahoo_range}&interval={yahoo_interval}"
        r = requests.get(url, headers=_YAHOO_HEADERS, timeout=8)

        if r.status_code != 200:
            return pd.DataFrame()

        data = r.json()
        result = data["chart"]["result"]
        if not result:
            return pd.DataFrame()

        result = result[0]
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quotes:
            return pd.DataFrame()

        ohlcv = {
            "Open": quotes.get("open", []),
            "High": quotes.get("high", []),
            "Low": quotes.get("low", []),
            "Close": quotes.get("close", []),
            "Volume": quotes.get("volume", []),
        }

        # Handle None values in quote data (market closed periods)
        closes = []
        for i, ts in enumerate(timestamps):
            c = None
            for field in ["Close", "Open", "High", "Low"]:
                vals = ohlcv.get(field, [])
                if i < len(vals) and vals[i] is not None:
                    c = vals[i]
                    break
            closes.append(c if c is not None else 0)

        df = pd.DataFrame({
            "Date": pd.to_datetime(timestamps, unit="s"),
            "Open": ohlcv["Open"],
            "High": ohlcv["High"],
            "Low": ohlcv["Low"],
            "Close": closes,
            "Volume": ohlcv["Volume"],
        })
        df.set_index("Date", inplace=True)

        # Drop rows where Close is 0 or NaN
        df = df[df["Close"] > 0].dropna()

        if not df.empty:
            df.to_json(cache_path)
        return df

    except Exception:
        return pd.DataFrame()


def fetch_crypto_data(symbol="BTC/USDT", limit=200):
    """Fetch crypto data from Binance via ccxt (with timeout)."""
    cache_key = f"crypto_{symbol.replace('/', '_')}_{limit}".replace("^", "_")
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 120:  # 2 min freshness for crypto
            with open(cache_path) as f:
                return pd.read_json(f)

    try:
        exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 10000,  # 10 second timeout
        })
        ohlcv = exchange.fetch_ohlcv(symbol, "1h", limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "Open", "High", "Low", "Close", "Volume"],
        )
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)
        df.to_json(cache_path)
        return df
    except Exception as e:
        print(f"⚠️ Crypto fetch error for {symbol}: {e}")
        return pd.DataFrame()


# ── Simulated fallback prices (used when live data unavailable) ──
_SIMULATED_PRICES = {
    "EURUSD": {"bid": 1.0850, "ask": 1.0852, "high": 1.0875, "low": 1.0830},
    "GBPUSD": {"bid": 1.2650, "ask": 1.2653, "high": 1.2680, "low": 1.2620},
    "XAUUSD": {"bid": 2350.00, "ask": 2350.50, "high": 2360.00, "low": 2340.00},
    "BTCUSD": {"bid": 65000.00, "ask": 65010.00, "high": 65500.00, "low": 64800.00},
    "ETHUSD": {"bid": 3500.00, "ask": 3505.00, "high": 3550.00, "low": 3480.00},
}


def _generate_simulated_price(pair_key, base_values, tick=0.0001):
    """Generate realistic simulated price with small random walk."""
    seed_val = hash(datetime.now().strftime("%Y%m%d%H") + pair_key) % 2**32
    np.random.seed(abs(seed_val))
    base = base_values["bid"]
    noise = np.random.normal(0, base * 0.0003)  # ~0.03% noise
    bid = base + noise
    # Spread: use tick value directly for realistic market spreads
    spread = tick * (0.5 if tick >= 1 else 2)
    change = noise / base * 100
    return {
        "bid": round(bid, 5),
        "ask": round(bid + spread, 5),
        "high": round(base_values["high"] + abs(noise) * 1.2, 5),
        "low": round(base_values["low"] - abs(noise) * 1.2, 5),
        "change": round(change, 3),
        "volume": float(np.random.exponential(50000)),
        "source": "simulated",
        "updated": datetime.now().strftime("%H:%M:%S"),
    }


def get_current_prices():
    """Get current prices for all trading pairs.

    Tries live data first (Yahoo Finance for forex, CCXT for crypto).
    Falls back to realistic simulated data if live sources fail.
    """
    prices = {}

    for pair, info in PAIRS.items():
        try:
            if info.get("yahoo"):
                # Single attempt — fail fast to simulated data
                df = fetch_yahoo_data(info["yahoo"], period="5d", interval="1h")

                if not df.empty:
                    prices[pair] = {
                        "bid": float(df["Close"].iloc[-1]),
                        "ask": float(df["Close"].iloc[-1]),
                        "high": float(df["High"].max()),
                        "low": float(df["Low"].min()),
                        "change": float(
                            ((df["Close"].iloc[-1] - df["Close"].iloc[0])
                             / df["Close"].iloc[0]) * 100
                        ),
                        "volume": float(df["Volume"].sum()),
                        "source": "yahoo",
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    # Fallback to simulated data
                    base = _SIMULATED_PRICES.get(pair, {"bid": 1.0})
                    pip = info.get("pip", 0.0001)
                    prices[pair] = _generate_simulated_price(pair, base, pip)

            elif info.get("crypto"):
                df = fetch_crypto_data(info["crypto"], limit=24)
                if not df.empty:
                    prices[pair] = {
                        "bid": float(df["Close"].iloc[-1]),
                        "ask": float(df["Close"].iloc[-1]),
                        "high": float(df["High"].max()),
                        "low": float(df["Low"].min()),
                        "change": float(
                            ((df["Close"].iloc[-1] - df["Close"].iloc[0])
                             / df["Close"].iloc[0]) * 100
                        ),
                        "volume": float(df["Volume"].sum()),
                        "source": "crypto",
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    prices[pair] = {"bid": 0, "ask": 0, "error": "No crypto data"}
        except Exception as e:
            # Ultimate fallback
            base = _SIMULATED_PRICES.get(pair, {"bid": 1.0})
            pip = info.get("pip", 0.0001)
            prices[pair] = _generate_simulated_price(pair, base, pip)
            prices[pair]["error"] = str(e)

    return prices


def get_cross_asset_data():
    """Fetch cross-asset data (DXY, VIX, Yields)."""
    data = {}
    for key, info in CROSS_ASSETS.items():
        try:
            df = fetch_yahoo_data(info["yahoo"], period="5d", interval="1h")
            if not df.empty:
                last = float(df["Close"].iloc[-1])
                change = float(
                    (df["Close"].iloc[-1] - df["Close"].iloc[0])
                    / df["Close"].iloc[0] * 100
                )
                data[key] = {
                    "name": info["name"],
                    "value": last,
                    "change": change,
                    "high": float(df["High"].max()),
                    "low": float(df["Low"].min()),
                    "trend": "bullish" if change > 0 else "bearish",
                }
            else:
                data[key] = {"name": info["name"], "value": 0, "error": "No data"}
        except Exception as e:
            data[key] = {"name": info["name"], "value": 0, "error": str(e)}
    return data


def get_historical_data(pair_key, period="1mo", interval="1h"):
    """Get historical OHLCV data for a specific pair."""
    info = PAIRS.get(pair_key)
    if not info:
        return pd.DataFrame()

    if info.get("yahoo"):
        return fetch_yahoo_data(info["yahoo"], period=period, interval=interval)
    elif info.get("crypto"):
        limit_map = {"1d": 24, "5d": 120, "1mo": 720, "3mo": 2160}
        return fetch_crypto_data(info["crypto"], limit=limit_map.get(period, 200))

    return pd.DataFrame()
