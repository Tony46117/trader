"""
╔══════════════════════════════════════════════════════════╗
║          Crypto — CCXT Binance Provider                ║
╠══════════════════════════════════════════════════════════╣
║  Fetches OHLCV data from Binance via CCXT.              ║
║  10s timeout, disk-cached with 2-minute TTL.           ║
╚══════════════════════════════════════════════════════════╝
"""
import os
import time
import pandas as pd
import ccxt
from config import CACHE_DIR

CACHE_TTL = 120  # 2 minutes


def _cache_key(symbol, limit):
    safe = symbol.replace("/", "_").replace(" ", "_")
    return os.path.join(CACHE_DIR, f"crypto_{safe}_{limit}.json")


def fetch_ohlcv(symbol="BTC/USDT", limit=200):
    """Fetch OHLCV data from Binance via CCXT."""
    cache_path = _cache_key(symbol, limit)

    if os.path.exists(cache_path) and time.time() - os.path.getmtime(cache_path) < CACHE_TTL:
        try:
            return pd.read_json(cache_path)
        except Exception:
            pass

    try:
        exchange = ccxt.binance({"enableRateLimit": True, "timeout": 10000})
        ohlcv = exchange.fetch_ohlcv(symbol, "1h", limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)
        df.to_json(cache_path)
        return df
    except Exception as e:
        print(f"⚠️ Crypto fetch error for {symbol}: {e}")
        return pd.DataFrame()
