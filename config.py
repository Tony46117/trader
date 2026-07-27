"""
╔══════════════════════════════════════════════════════════╗
║          TRADER — Configuration                         ║
╠══════════════════════════════════════════════════════════╣
║  All config in one place. Override with env vars.       ║
║  PAIRS: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD         ║
║  Min RR: 1:2 ·  Cache: 30s ·  5-Source Fusion          ║
╚══════════════════════════════════════════════════════════╝
"""
import os

# ── Paths ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_DIR = os.path.join(BASE_DIR, "data", "news")
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(NEWS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Server ──────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("FLASK_ENV", "development") == "development"
CACHE_TTL = int(os.environ.get("CACHE_TTL", 30))
YAHOO_TIMEOUT = int(os.environ.get("YAHOO_TIMEOUT", 8))

# ── Trading Pairs ───────────────────────────────────────────────────
PAIRS = {
    "EURUSD": {"name": "EUR/USD", "yahoo": "EURUSD=X",    "type": "forex",    "pip": 0.0001, "precision": 5},
    "GBPUSD": {"name": "GBP/USD", "yahoo": "GBPUSD=X",    "type": "forex",    "pip": 0.0001, "precision": 5},
    "XAUUSD": {"name": "Gold",    "yahoo": "GC=F",        "type": "commodity","pip": 0.1,    "precision": 2},
    "BTCUSD": {"name": "Bitcoin", "crypto": "BTC/USDT",   "type": "crypto",   "pip": 1.0,    "precision": 2},
    "ETHUSD": {"name": "Ethereum","crypto": "ETH/USDT",   "type": "crypto",   "pip": 0.1,    "precision": 2},
}

# ── Cross-Asset Tickers ─────────────────────────────────────────────
CROSS_ASSETS = {
    "DXY":   {"name": "US Dollar Index",   "yahoo": "DX-Y.NYB"},
    "VIX":   {"name": "Volatility Index",   "yahoo": "^VIX"},
    "US10Y": {"name": "US 10Y Yield",       "yahoo": "^TNX"},
    "US5Y":  {"name": "US 5Y Yield",        "yahoo": "^FVX"},
    "US30Y": {"name": "US 30Y Yield",       "yahoo": "^TYX"},
}

# ── Signal Parameters ───────────────────────────────────────────────
# TP multipliers enforce minimum 1:2 RR
# SL = 1.5× ATR → TP1 = 3.0× ATR → RR = 1:2.0
SIGNAL_CONFIG = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "atr_multiplier_sl": 1.5,
    "atr_multiplier_tp1": 3.0,     # 1:2.0 RR minimum
    "atr_multiplier_tp2": 4.5,     # 1:3.0 RR
    "atr_multiplier_tp3": 6.0,     # 1:4.0 RR
    "bb_period": 20,
    "bb_std": 2,
    "sma_fast": 20,
    "sma_slow": 50,
    "ema_fast": 9,
    "ema_slow": 21,
    "min_rr_ratio": 2.0,
}

# ── Fusion Weights ──────────────────────────────────────────────────
FUSION_WEIGHTS = {
    "technical": 0.40,
    "news":      0.20,
    "tick":      0.15,
    "cme":       0.15,
    "social":    0.10,
}
