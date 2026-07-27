"""
╔══════════════════════════════════════════════════════════╗
║          Technical Indicators Service                   ║
╠══════════════════════════════════════════════════════════╣
║  Wraps C++ accelerated indicators (pybind11).           ║
║  Falls back to pure numpy/pandas if C++ unavailable.   ║
║  Indicators: RSI, MACD, BB, ATR, StochRSI, EMA, SMA,   ║
║  Ichimoku Cloud, Pivot Points, Support/Resistance.     ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
import pandas as pd

# Try to import the C++ module; fall back to pure Python
_INDICATORS_CPP = False
try:
    from engine.cpp_indicator import (  # type: ignore
        compute_rsi as _cpp_rsi,
        compute_macd as _cpp_macd,
        compute_bollinger_bands as _cpp_bb,
        compute_atr as _cpp_atr,
        compute_stoch_rsi as _cpp_stoch,
        compute_ema as _cpp_ema,
        compute_sma as _cpp_sma,
    )
    _INDICATORS_CPP = True
except ImportError:
    pass


# ── RSI ─────────────────────────────────────────────────────────────
def compute_rsi(series, period=14):
    if _INDICATORS_CPP:
        return _cpp_rsi(series, period)
    # Pure Python fallback
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── MACD ────────────────────────────────────────────────────────────
def compute_macd(series, fast=12, slow=26, signal=9):
    if _INDICATORS_CPP:
        return _cpp_macd(series, fast, slow, signal)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


# ── Bollinger Bands ─────────────────────────────────────────────────
def compute_bollinger_bands(series, period=20, std=2):
    if _INDICATORS_CPP:
        return _cpp_bb(series, period, std)
    mid = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    upper = mid + sigma * std
    lower = mid - sigma * std
    return upper, mid, lower


# ── ATR ─────────────────────────────────────────────────────────────
def compute_atr(high, low, close, period=14):
    if _INDICATORS_CPP:
        return _cpp_atr(high, low, close, period)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ── Stochastic RSI ──────────────────────────────────────────────────
def compute_stoch_rsi(series, period=14, smooth_k=3, smooth_d=3):
    if _INDICATORS_CPP:
        return _cpp_stoch(series, period)
    rsi = compute_rsi(series, period)
    stoch = ((rsi - rsi.rolling(period).min()) /
             (rsi.rolling(period).max() - rsi.rolling(period).min())) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


# ── EMA / SMA ────────────────────────────────────────────────────────
def compute_ema(series, span=9):
    if _INDICATORS_CPP:
        return _cpp_ema(series, span)
    return series.ewm(span=span, adjust=False).mean()


def compute_sma(series, window=20):
    if _INDICATORS_CPP:
        return _cpp_sma(series, window)
    return series.rolling(window).mean()


# ── Ichimoku Cloud ──────────────────────────────────────────────────
def compute_ichimoku(df):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    chikou = close.shift(-26)
    return tenkan, kijun, senkou_a, senkou_b


# ── Pivot Points ────────────────────────────────────────────────────
def compute_pivot_points(df):
    if len(df) < 48:
        return {"pivot": 0, "r1": 0, "r2": 0, "s1": 0, "s2": 0}
    prior = df.tail(24)
    high = prior["High"].max()
    low = prior["Low"].min()
    close = prior["Close"].iloc[-1]
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    return {"pivot": pivot, "r1": r1, "r2": r2, "s1": s1, "s2": s2}


# ── Support / Resistance ────────────────────────────────────────────
def compute_support_resistance(df, lookback=100):
    highs = df["High"].tail(lookback)
    lows = df["Low"].tail(lookback)

    def cluster(prices, n=3):
        vals = sorted(prices.dropna().values)
        if len(vals) < 5:
            return []
        step = max(1, len(vals) // n)
        levels = []
        for i in range(n):
            cluster_vals = vals[i * step : (i * step + step) if i < n - 1 else len(vals)]
            if cluster_vals:
                levels.append(float(np.mean(cluster_vals)))
        return levels

    return cluster(lows, 3), cluster(highs, 3)
