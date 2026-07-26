"""C++ Accelerated Indicator Module.

Provides high-speed implementations of:
- RSI, MACD, Bollinger Bands, ATR
- EMA, SMA, Stochastic RSI
- Rolling correlation

Falls back to pure Python if C++ module isn't compiled.
"""

import numpy as np
import pandas as pd

# Try to import the compiled C++ module
try:
    import fast_indicators as _cpp
    HAS_CPP = True
    print("⚡ Using C++ accelerated indicators")
except ImportError:
    HAS_CPP = False
    print("⚠️  C++ indicators not available, using pure Python (compile with: cd engine/cpp_indicator && make)")


# ── Public API ──────────────────────────────────────────────────────

def compute_rsi(series, period=14):
    """Compute RSI — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_rsi(data.tolist(), period)
        return pd.Series(result, index=series.index if isinstance(series, pd.Series) else None)
    # Pure Python fallback
    return _py_compute_rsi(series, period)


def compute_macd(series, fast=12, slow=26, signal=9):
    """Compute MACD — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_macd(data.tolist(), fast, slow, signal)
        index = series.index if isinstance(series, pd.Series) else None
        return (pd.Series(result.macd_line, index=index),
                pd.Series(result.signal_line, index=index),
                pd.Series(result.histogram, index=index))
    return _py_compute_macd(series, fast, slow, signal)


def compute_bollinger_bands(series, period=20, std_dev=2):
    """Compute Bollinger Bands — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_bollinger_bands(data.tolist(), period, std_dev)
        index = series.index if isinstance(series, pd.Series) else None
        return (pd.Series(result.upper, index=index),
                pd.Series(result.middle, index=index),
                pd.Series(result.lower, index=index))
    return _py_compute_bollinger_bands(series, period, std_dev)


def compute_atr(high, low, close, period=14):
    """Compute ATR — uses C++ when available."""
    h = high.values if isinstance(high, pd.Series) else np.asarray(high, dtype=np.float64)
    l = low.values if isinstance(low, pd.Series) else np.asarray(low, dtype=np.float64)
    c = close.values if isinstance(close, pd.Series) else np.asarray(close, dtype=np.float64)

    if HAS_CPP:
        result = _cpp.compute_atr(h.tolist(), l.tolist(), c.tolist(), period)
        index = close.index if isinstance(close, pd.Series) else None
        return pd.Series(result, index=index)
    return _py_compute_atr(high, low, close, period)


def compute_ema(series, period):
    """Compute EMA — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_ema(data.tolist(), period)
        return pd.Series(result, index=series.index if isinstance(series, pd.Series) else None)
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series, period):
    """Compute SMA — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_sma(data.tolist(), period)
        return pd.Series(result, index=series.index if isinstance(series, pd.Series) else None)
    return series.rolling(window=period).mean()


def compute_stoch_rsi(series, period=14, k_period=3, d_period=3):
    """Compute Stochastic RSI — uses C++ when available."""
    data = series.values if isinstance(series, pd.Series) else np.asarray(series, dtype=np.float64)
    if HAS_CPP:
        result = _cpp.compute_stoch_rsi(data.tolist(), period, k_period, d_period)
        index = series.index if isinstance(series, pd.Series) else None
        return (pd.Series(result.k, index=index),
                pd.Series(result.d, index=index))
    return _py_compute_stoch_rsi(series, period, k_period, d_period)


def rolling_corr(series_a, series_b, window=20):
    """Compute rolling correlation — uses C++ when available."""
    a = series_a.values if isinstance(series_a, pd.Series) else np.asarray(series_a, dtype=np.float64)
    b = series_b.values if isinstance(series_b, pd.Series) else np.asarray(series_b, dtype=np.float64)

    if HAS_CPP:
        result = _cpp.rolling_correlation(a.tolist(), b.tolist(), window)
        index = series_a.index if isinstance(series_a, pd.Series) else None
        return pd.Series(result, index=index)
    return series_a.rolling(window).corr(series_b)


# ── Pure Python fallback implementations ────────────────────────────

def _py_compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return pd.Series(100 - (100 / (1 + rs)), index=series.index)


def _py_compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def _py_compute_bollinger_bands(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return sma + (std * std_dev), sma, sma - (std * std_dev)


def _py_compute_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def _py_compute_stoch_rsi(series, period=14, k_period=3, d_period=3):
    rsi = _py_compute_rsi(series, period)
    min_rsi = rsi.rolling(window=period).min()
    max_rsi = rsi.rolling(window=period).max()
    stoch = (rsi - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan) * 100
    k = stoch.rolling(window=k_period).mean()
    d = k.rolling(window=d_period).mean()
    return k, d
