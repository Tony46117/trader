"""
╔══════════════════════════════════════════════════════════╗
║          Market Data Service                            ║
╠══════════════════════════════════════════════════════════╣
║  Aggregates prices from Yahoo + Crypto providers.       ║
║  Falls back to realistic simulated data when live       ║
║  sources are unavailable (rate-limited, timeout, etc).  ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
import pandas as pd
from datetime import datetime

from config import PAIRS, CROSS_ASSETS
from providers.yahoo import fetch_ohlcv
from providers.crypto import fetch_ohlcv as fetch_crypto_ohlcv

# ── Simulated Price Anchors ─────────────────────────────────────────
_SIMULATED_PRICES = {
    "EURUSD": {"bid": 1.0850, "ask": 1.0852, "high": 1.0875, "low": 1.0830},
    "GBPUSD": {"bid": 1.2650, "ask": 1.2653, "high": 1.2680, "low": 1.2620},
    "XAUUSD": {"bid": 2350.00,"ask": 2350.50,"high": 2360.00,"low": 2340.00},
    "BTCUSD": {"bid": 65000.00,"ask": 65010.00,"high": 65500.00,"low": 64800.00},
    "ETHUSD": {"bid": 3500.00, "ask": 3505.00, "high": 3550.00, "low": 3480.00},
}


def _simulated_price(pair_key, base, tick):
    """Generate a realistic simulated price with small random walk."""
    seed = abs(hash(datetime.now().strftime("%Y%m%d%H") + pair_key)) % 2**32
    np.random.seed(seed)
    noise = np.random.normal(0, base["bid"] * 0.0003)
    bid = base["bid"] + noise
    spread = tick * (0.5 if tick >= 1 else 2)
    change = noise / base["bid"] * 100
    return {
        "bid": round(bid, 5),
        "ask": round(bid + spread, 5),
        "high": round(base["high"] + abs(noise) * 1.2, 5),
        "low": round(base["low"] - abs(noise) * 1.2, 5),
        "change": round(change, 3),
        "volume": float(np.random.exponential(50000)),
        "source": "simulated",
        "updated": datetime.now().strftime("%H:%M:%S"),
    }


def get_current_prices():
    """Get live prices for all pairs. Falls back to simulated on failure."""
    prices = {}
    for pair, info in PAIRS.items():
        try:
            if info.get("yahoo"):
                df = fetch_ohlcv(info["yahoo"], period="5d", interval="1h")
                if not df.empty:
                    last = float(df["Close"].iloc[-1])
                    first = float(df["Close"].iloc[0])
                    prices[pair] = {
                        "bid": last,
                        "ask": last,
                        "high": float(df["High"].max()),
                        "low": float(df["Low"].min()),
                        "change": round((last - first) / first * 100, 3) if first > 0 else 0,
                        "volume": float(df["Volume"].sum()),
                        "source": "yahoo",
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    base = _SIMULATED_PRICES.get(pair, {"bid": 1.0, "ask": 1.0, "high": 1.0, "low": 1.0})
                    prices[pair] = _simulated_price(pair, base, info.get("pip", 0.0001))

            elif info.get("crypto"):
                df = fetch_crypto_ohlcv(info["crypto"], limit=24)
                if not df.empty:
                    last = float(df["Close"].iloc[-1])
                    first = float(df["Close"].iloc[0])
                    prices[pair] = {
                        "bid": last,
                        "ask": last,
                        "high": float(df["High"].max()),
                        "low": float(df["Low"].min()),
                        "change": round((last - first) / first * 100, 3) if first > 0 else 0,
                        "volume": float(df["Volume"].sum()),
                        "source": "crypto",
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    prices[pair] = {"bid": 0, "ask": 0, "error": "No crypto data"}

        except Exception as e:
            base = _SIMULATED_PRICES.get(pair, {"bid": 1.0, "ask": 1.0, "high": 1.0, "low": 1.0})
            prices[pair] = _simulated_price(pair, base, info.get("pip", 0.0001))
            prices[pair]["error"] = str(e)

    return prices


def get_cross_asset_data():
    """Fetch cross-asset data (DXY, VIX, Yields)."""
    data = {}
    for key, info in CROSS_ASSETS.items():
        try:
            df = fetch_ohlcv(info["yahoo"], period="5d", interval="1h")
            if not df.empty:
                last = float(df["Close"].iloc[-1])
                first = float(df["Close"].iloc[0])
                change_pct = round((last - first) / first * 100, 2) if first > 0 else 0
                data[key] = {
                    "name": info["name"],
                    "value": last,
                    "change": change_pct,
                    "high": float(df["High"].max()),
                    "low": float(df["Low"].min()),
                    "trend": "bullish" if change_pct > 0 else "bearish",
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
        return fetch_ohlcv(info["yahoo"], period=period, interval=interval)
    elif info.get("crypto"):
        limit_map = {"1d": 24, "5d": 120, "1mo": 720, "3mo": 2160}
        return fetch_crypto_ohlcv(info["crypto"], limit=limit_map.get(period, 200))

    return pd.DataFrame()
