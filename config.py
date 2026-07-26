"""Trading Framework Configuration."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Trading pairs
PAIRS = {
    "EURUSD": {"name": "EUR/USD", "yahoo": "EURUSD=X", "type": "forex", "pip": 0.0001},
    "GBPUSD": {"name": "GBP/USD", "yahoo": "GBPUSD=X", "type": "forex", "pip": 0.0001},
    "XAUUSD": {"name": "Gold", "yahoo": "GC=F", "type": "commodity", "pip": 0.1},
    "BTCUSD": {"name": "Bitcoin", "crypto": "BTC/USDT", "type": "crypto", "pip": 1.0},
    "ETHUSD": {"name": "Ethereum", "crypto": "ETH/USDT", "type": "crypto", "pip": 0.1},
}

# Cross-asset tickers
CROSS_ASSETS = {
    "DXY": {"name": "US Dollar Index", "yahoo": "DX-Y.NYB"},
    "VIX": {"name": "Volatility Index", "yahoo": "^VIX"},
    "US10Y": {"name": "US 10Y Yield", "yahoo": "^TNX"},
    "US2Y": {"name": "US 2Y Yield", "yahoo": "^2YY=F"},
    "US30Y": {"name": "US 30Y Yield", "yahoo": "^TYX=F"},
    "US5Y": {"name": "US 5Y Yield", "yahoo": "^FVX=F"},
}

# News data directory
NEWS_DIR = os.path.join(BASE_DIR, "data", "news")

# Cache directory
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Signal parameters
SIGNAL_CONFIG = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "atr_multiplier_sl": 1.5,
    "atr_multiplier_tp1": 1.0,
    "atr_multiplier_tp2": 2.0,
    "atr_multiplier_tp3": 3.0,
    "bb_period": 20,
    "bb_std": 2,
    "sma_fast": 20,
    "sma_slow": 50,
    "ema_fast": 9,
    "ema_slow": 21,
}
