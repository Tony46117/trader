"""Market data fetching module.
Fetches live and historical data for forex, commodities, and crypto.
"""

import time
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import ccxt
import requests

from config import PAIRS, CROSS_ASSETS, CACHE_DIR


def fetch_yahoo_data(ticker, period="1mo", interval="1h"):
    """Fetch data from Yahoo Finance with timeout."""
    cache_key = f"yahoo_{ticker}_{period}_{interval}".replace("^", "_")
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    # Check cache (5-minute freshness)
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 300:  # 5 min
            with open(cache_path) as f:
                return pd.read_json(f)

    try:
        stock = yf.Ticker(ticker)
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                stock.history, period=period, interval=interval,
                auto_adjust=False
            )
            try:
                df = future.result(timeout=15)
            except TimeoutError:
                print(f"⏰ Yahoo fetch timeout for {ticker} (15s)")
                return pd.DataFrame()
        if not df.empty:
            df.to_json(cache_path)
        return df
    except Exception as e:
        print(f"⚠️ Yahoo fetch error for {ticker}: {e}")
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


def get_current_prices():
    """Get current prices for all trading pairs."""
    prices = {}

    # Forex
    for pair, info in PAIRS.items():
        try:
            if info.get("yahoo"):
                df = fetch_yahoo_data(info["yahoo"], period="5d", interval="1m")
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
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    prices[pair] = {"bid": 0, "ask": 0, "error": "No data"}
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
                        "updated": datetime.now().strftime("%H:%M:%S"),
                    }
                else:
                    prices[pair] = {"bid": 0, "ask": 0, "error": "No data"}
        except Exception as e:
            prices[pair] = {"bid": 0, "ask": 0, "error": str(e)}

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
