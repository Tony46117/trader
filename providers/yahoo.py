"""
╔══════════════════════════════════════════════════════════╗
║          Yahoo Finance — Direct REST API Provider       ║
╠══════════════════════════════════════════════════════════╣
║  Fetches OHLCV data via query2.finance.yahoo.com        ║
║  with browser User-Agent to avoid rate limiting.        ║
║  Caches results to disk with configurable TTL.          ║
╚══════════════════════════════════════════════════════════╝
"""
import os
import json
import time
import pandas as pd
import requests
from config import CACHE_DIR, YAHOO_TIMEOUT

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "60m", "1d": "1d", "5d": "5d",
    "1wk": "1wk", "1mo": "1mo",
}

_RANGE_MAP = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y",
    "ytd": "ytd", "max": "max",
}

CACHE_TTL = 300  # 5 minutes


def _cache_key(ticker, period, interval):
    safe = ticker.replace("^", "_").replace("=", "_")
    return os.path.join(CACHE_DIR, f"yahoo_{safe}_{period}_{interval}.json")


def _read_cache(path):
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > CACHE_TTL:
        return None
    try:
        return pd.read_json(path)
    except Exception:
        return None


def _write_cache(path, df):
    try:
        df.to_json(path)
    except Exception:
        pass


def fetch_ohlcv(ticker, period="1mo", interval="1h"):
    """Fetch OHLCV data from Yahoo Finance.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume.
    Returns empty DataFrame on any failure.
    """
    cache_path = _cache_key(ticker, period, interval)
    cached = _read_cache(cache_path)
    if cached is not None and not cached.empty:
        return cached

    try:
        yahoo_range = _RANGE_MAP.get(period, "1mo")
        yahoo_int = _INTERVAL_MAP.get(interval, "60m")
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range={yahoo_range}&interval={yahoo_int}"
        r = requests.get(url, headers=_HEADERS, timeout=YAHOO_TIMEOUT)

        if r.status_code != 200:
            return pd.DataFrame()

        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return pd.DataFrame()

        result = result[0]
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quotes:
            return pd.DataFrame()

        # Build OHLCV arrays, handling None values
        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        volumes = quotes.get("volume", [])

        rows = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) and closes[i] is not None else None
            o = opens[i] if i < len(opens) and opens[i] is not None else c
            h = highs[i] if i < len(highs) and highs[i] is not None else c
            l = lows[i] if i < len(lows) and lows[i] is not None else c
            v = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
            if c is not None and c > 0:
                rows.append({
                    "Date": pd.Timestamp(ts, unit="s"),
                    "Open": float(o or c),
                    "High": float(h or c),
                    "Low": float(l or c),
                    "Close": float(c),
                    "Volume": float(v or 0),
                })

        df = pd.DataFrame(rows).set_index("Date")
        if not df.empty:
            _write_cache(cache_path, df)
        return df

    except Exception:
        return pd.DataFrame()
