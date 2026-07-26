"""Trading Framework Configuration.

Enforces a minimum 1:2 risk-reward ratio on all setups.
Only generates signals for: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD.
Cross-asset analysis covers: DXY, VIX, US yields (2Y, 5Y, 10Y, 30Y).
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Trading Pairs (signals only for these) ──
PAIRS = {
    "EURUSD": {"name": "EUR/USD", "yahoo": "EURUSD=X", "type": "forex", "pip": 0.0001},
    "GBPUSD": {"name": "GBP/USD", "yahoo": "GBPUSD=X", "type": "forex", "pip": 0.0001},
    "XAUUSD": {"name": "Gold", "yahoo": "GC=F", "type": "commodity", "pip": 0.1},
    "BTCUSD": {"name": "Bitcoin", "crypto": "BTC/USDT", "type": "crypto", "pip": 1.0},
    "ETHUSD": {"name": "Ethereum", "crypto": "ETH/USDT", "type": "crypto", "pip": 0.1},
}

# ── Cross-Asset tickers (DXY, VIX, US yields & treasuries) ──
CROSS_ASSETS = {
    "DXY": {"name": "US Dollar Index", "yahoo": "DX-Y.NYB"},
    "VIX": {"name": "Volatility Index", "yahoo": "^VIX"},
    "US10Y": {"name": "US 10Y Yield", "yahoo": "^TNX"},
    "US2Y": {"name": "US 2Y Yield", "yahoo": "^IRX=F"},
    "US30Y": {"name": "US 30Y Yield", "yahoo": "^TYX"},
    "US5Y": {"name": "US 5Y Yield", "yahoo": "^FVX"},
}

# News data directory
NEWS_DIR = os.path.join(BASE_DIR, "data", "news")
os.makedirs(NEWS_DIR, exist_ok=True)

# Cache directory
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Signal Parameters ──
# TP multipliers enforce minimum 1:2 RR (risk = SL distance, reward = TP distance)
# SL = 1.5x ATR → TP1 = 3.0x ATR → RR = 1:2.0 minimum
SIGNAL_CONFIG = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "atr_multiplier_sl": 1.5,
    "atr_multiplier_tp1": 3.0,   # 1:2.0 RR minimum
    "atr_multiplier_tp2": 4.5,   # 1:3.0 RR
    "atr_multiplier_tp3": 6.0,   # 1:4.0 RR
    "bb_period": 20,
    "bb_std": 2,
    "sma_fast": 20,
    "sma_slow": 50,
    "ema_fast": 9,
    "ema_slow": 21,
    "min_rr_ratio": 2.0,         # Minimum R:R for any setup to be shown
}
