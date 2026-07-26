"""Signal Engine — TradingView-style Technical Analysis using TA-Lib + pandas.

Generates a technical signal component per pair with:
- RSI (14), Stochastic RSI
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- EMA cross (9/21), SMA trend (20/50)
- Classic Pivot Points
- ATR for volatility
- Ichimoku Cloud (tenkan/kijun cross)

Output: technical score 0-100 per pair (0=strong SELL, 50=neutral, 100=strong BUY)
Plus entry/SL/TP levels based on ATR.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from config import PAIRS, SIGNAL_CONFIG
from engine.market_data import get_historical_data, get_current_prices

# ── C++ accelerated indicators (with pure Python fallback) ──
from engine.cpp_indicator import (
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_stoch_rsi,
    compute_atr as _fast_atr,
    compute_ema,
    compute_sma,
)


def compute_atr(df, period=14):
    """Average True Range — wraps C++ indicator with DataFrame support."""
    return _fast_atr(
        df["High"], df["Low"], df["Close"], period
    )


def compute_ichimoku(df):
    """Ichimoku Cloud — tenkan-sen / kijun-sen cross."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    chikou = close.shift(-26)
    return tenkan, kijun, senkou_a, senkou_b


def compute_pivot_points(df):
    """Classic Pivot Points based on prior day's data."""
    if len(df) < 48:
        return {"pivot": 0, "r1": 0, "r2": 0, "s1": 0, "s2": 0}
    # Use last 24h as prior "day"
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


def compute_support_resistance(df, lookback=100):
    """Key support/resistance levels via cluster detection."""
    highs = df["High"].tail(lookback)
    lows = df["Low"].tail(lookback)

    def cluster(prices, n=3):
        if len(prices) < 5:
            return []
        vals = sorted(prices.dropna().values)
        step = max(1, len(vals) // n)
        levels = []
        for i in range(n):
            cluster_vals = vals[i * step : (i * step + step) if i < n - 1 else len(vals)]
            if cluster_vals:
                levels.append(float(np.mean(cluster_vals)))
        return levels

    return cluster(lows, 3), cluster(highs, 3)


# ── Technical Scoring Engine ──────────────────────────────────────────

def score_indicators(df, pair_key):
    """Score each indicator BUY/SELL/NEUTRAL and return a technical score 0-100.

    Returns:
        score: 0-100 (0=strong SELL, 50=neutral, 100=strong BUY)
        details: list of dicts for each indicator
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    current_price = float(latest["Close"])

    # ── Compute all indicators ──
    rsi = compute_rsi(close, SIGNAL_CONFIG["rsi_period"])
    macd_line, macd_signal, macd_hist = compute_macd(
        close, SIGNAL_CONFIG["macd_fast"], SIGNAL_CONFIG["macd_slow"], SIGNAL_CONFIG["macd_signal"]
    )
    bb_upper, bb_mid, bb_lower = compute_bollinger_bands(
        close, SIGNAL_CONFIG["bb_period"], SIGNAL_CONFIG["bb_std"]
    )
    stoch_k, stoch_d = compute_stoch_rsi(close)
    tenkan, kijun, senkou_a, senkou_b = compute_ichimoku(df)
    atr_series = compute_atr(df)
    sma_20 = close.rolling(SIGNAL_CONFIG["sma_fast"]).mean()
    sma_50 = close.rolling(SIGNAL_CONFIG["sma_slow"]).mean()
    ema_9 = close.ewm(span=SIGNAL_CONFIG["ema_fast"], adjust=False).mean()
    ema_21 = close.ewm(span=SIGNAL_CONFIG["ema_slow"], adjust=False).mean()
    pivots = compute_pivot_points(df)
    support_levels, resistance_levels = compute_support_resistance(df)

    # Latest values
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    macd_val = float(macd_line.iloc[-1])
    macd_sig_val = float(macd_signal.iloc[-1])
    macd_h_val = float(macd_hist.iloc[-1])
    macd_h_prev = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else macd_h_val
    bb_u = float(bb_upper.iloc[-1])
    bb_l = float(bb_lower.iloc[-1])
    bb_m = float(bb_mid.iloc[-1])
    stoch_k_val = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else 50
    stoch_d_val = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else 50
    tenkan_val = float(tenkan.iloc[-1]) if not pd.isna(tenkan.iloc[-1]) else current_price
    kijun_val = float(kijun.iloc[-1]) if not pd.isna(kijun.iloc[-1]) else current_price
    atr_val = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else current_price * 0.01
    sma20_val = float(sma_20.iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else current_price
    sma50_val = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else current_price
    ema9_val = float(ema_9.iloc[-1]) if not pd.isna(ema_9.iloc[-1]) else current_price
    ema21_val = float(ema_21.iloc[-1]) if not pd.isna(ema_21.iloc[-1]) else current_price

    details = []
    buy_votes = 0
    sell_votes = 0
    total_weight = 0

    # ── 1. RSI (weight: 20) ──
    weight = 20
    total_weight += weight
    if rsi_val < 30:
        buy_votes += weight * 1.0
        details.append({"indicator": "RSI (14)", "signal": "BUY", "value": f"{rsi_val:.1f}",
                        "reason": f"Oversold at {rsi_val:.1f} (< 30)", "weight": weight})
    elif rsi_val < 40:
        buy_votes += weight * 0.5
        details.append({"indicator": "RSI (14)", "signal": "BUY (weak)", "value": f"{rsi_val:.1f}",
                        "reason": f"Approaching oversold at {rsi_val:.1f}", "weight": weight})
    elif rsi_val > 70:
        sell_votes += weight * 1.0
        details.append({"indicator": "RSI (14)", "signal": "SELL", "value": f"{rsi_val:.1f}",
                        "reason": f"Overbought at {rsi_val:.1f} (> 70)", "weight": weight})
    elif rsi_val > 60:
        sell_votes += weight * 0.5
        details.append({"indicator": "RSI (14)", "signal": "SELL (weak)", "value": f"{rsi_val:.1f}",
                        "reason": f"Approaching overbought at {rsi_val:.1f}", "weight": weight})
    else:
        details.append({"indicator": "RSI (14)", "signal": "NEUTRAL", "value": f"{rsi_val:.1f}",
                        "reason": f"Neutral at {rsi_val:.1f} (30-70)", "weight": weight})
        buy_votes += weight * 0.5  # neutral leans towards no action

    # ── 2. MACD (weight: 20) ──
    weight = 20
    total_weight += weight
    if macd_val > macd_sig_val and macd_h_val > macd_h_prev:
        buy_votes += weight * 1.0
        details.append({"indicator": "MACD (12,26,9)", "signal": "BUY", "value": f"{macd_val:.5f}",
                        "reason": "Bullish cross + expanding histogram", "weight": weight})
    elif macd_val > macd_sig_val and macd_h_val > 0:
        buy_votes += weight * 0.6
        details.append({"indicator": "MACD (12,26,9)", "signal": "BUY (weak)", "value": f"{macd_val:.5f}",
                        "reason": "MACD above signal line", "weight": weight})
    elif macd_val < macd_sig_val and macd_h_val < macd_h_prev:
        sell_votes += weight * 1.0
        details.append({"indicator": "MACD (12,26,9)", "signal": "SELL", "value": f"{macd_val:.5f}",
                        "reason": "Bearish cross + declining histogram", "weight": weight})
    elif macd_val < macd_sig_val and macd_h_val < 0:
        sell_votes += weight * 0.6
        details.append({"indicator": "MACD (12,26,9)", "signal": "SELL (weak)", "value": f"{macd_val:.5f}",
                        "reason": "MACD below signal line", "weight": weight})
    else:
        details.append({"indicator": "MACD (12,26,9)", "signal": "NEUTRAL", "value": f"{macd_val:.5f}",
                        "reason": "MACD flattening near signal line", "weight": weight})
        buy_votes += weight * 0.5

    # ── 3. Bollinger Bands (weight: 15) ──
    weight = 15
    total_weight += weight
    if current_price <= bb_l:
        buy_votes += weight * 1.0
        details.append({"indicator": "Bollinger Bands (20,2)", "signal": "BUY", "value": f"{current_price:.5f}",
                        "reason": "Price at lower band — oversold bounce likely", "weight": weight})
    elif current_price <= bb_m:
        buy_votes += weight * 0.4
        details.append({"indicator": "Bollinger Bands (20,2)", "signal": "BUY (weak)", "value": f"{current_price:.5f}",
                        "reason": "Price below mid-band", "weight": weight})
    elif current_price >= bb_u:
        sell_votes += weight * 1.0
        details.append({"indicator": "Bollinger Bands (20,2)", "signal": "SELL", "value": f"{current_price:.5f}",
                        "reason": "Price at upper band — overextended", "weight": weight})
    elif current_price >= bb_m:
        sell_votes += weight * 0.4
        details.append({"indicator": "Bollinger Bands (20,2)", "signal": "SELL (weak)", "value": f"{current_price:.5f}",
                        "reason": "Price above mid-band", "weight": weight})
    else:
        details.append({"indicator": "Bollinger Bands (20,2)", "signal": "NEUTRAL", "value": f"{current_price:.5f}",
                        "reason": "Price in mid-range", "weight": weight})
        buy_votes += weight * 0.5

    # ── 4. Stochastic RSI (weight: 15) ──
    weight = 15
    total_weight += weight
    if not pd.isna(stoch_k_val) and not pd.isna(stoch_d_val):
        if stoch_k_val < 20 and stoch_k_val < stoch_d_val:
            buy_votes += weight * 1.0
            details.append({"indicator": "Stochastic RSI", "signal": "BUY", "value": f"K:{stoch_k_val:.0f} D:{stoch_d_val:.0f}",
                            "reason": f"Oversold at K={stoch_k_val:.0f}", "weight": weight})
        elif stoch_k_val > 80 and stoch_k_val > stoch_d_val:
            sell_votes += weight * 1.0
            details.append({"indicator": "Stochastic RSI", "signal": "SELL", "value": f"K:{stoch_k_val:.0f} D:{stoch_d_val:.0f}",
                            "reason": f"Overbought at K={stoch_k_val:.0f}", "weight": weight})
        elif stoch_k_val < 30:
            buy_votes += weight * 0.6
            details.append({"indicator": "Stochastic RSI", "signal": "BUY (weak)", "value": f"K:{stoch_k_val:.0f} D:{stoch_d_val:.0f}",
                            "reason": f"Stoch RSI low at {stoch_k_val:.0f}", "weight": weight})
        elif stoch_k_val > 70:
            sell_votes += weight * 0.6
            details.append({"indicator": "Stochastic RSI", "signal": "SELL (weak)", "value": f"K:{stoch_k_val:.0f} D:{stoch_d_val:.0f}",
                            "reason": f"Stoch RSI high at {stoch_k_val:.0f}", "weight": weight})
        else:
            details.append({"indicator": "Stochastic RSI", "signal": "NEUTRAL", "value": f"K:{stoch_k_val:.0f} D:{stoch_d_val:.0f}",
                            "reason": "Stoch RSI in mid-range", "weight": weight})
            buy_votes += weight * 0.5
    else:
        buy_votes += weight * 0.5
        details.append({"indicator": "Stochastic RSI", "signal": "N/A", "value": "—",
                        "reason": "Not enough data", "weight": weight})

    # ── 5. EMA Crossover (9/21) (weight: 10) ──
    weight = 10
    total_weight += weight
    ema9_prev = float(ema_9.iloc[-2]) if len(ema_9) > 1 else ema9_val
    ema21_prev = float(ema_21.iloc[-2]) if len(ema_21) > 1 else ema21_val
    if ema9_val > ema21_val and ema9_prev <= ema21_prev:
        buy_votes += weight * 1.0
        details.append({"indicator": "EMA Cross (9/21)", "signal": "BUY", "value": f"E9:{ema9_val:.5f} E21:{ema21_val:.5f}",
                        "reason": "Bullish crossover", "weight": weight})
    elif ema9_val < ema21_val and ema9_prev >= ema21_prev:
        sell_votes += weight * 1.0
        details.append({"indicator": "EMA Cross (9/21)", "signal": "SELL", "value": f"E9:{ema9_val:.5f} E21:{ema21_val:.5f}",
                        "reason": "Bearish crossover", "weight": weight})
    elif ema9_val > ema21_val:
        buy_votes += weight * 0.5
        details.append({"indicator": "EMA Cross (9/21)", "signal": "BUY (weak)", "value": f"E9:{ema9_val:.5f} E21:{ema21_val:.5f}",
                        "reason": "EMA(9) above EMA(21) — uptrend", "weight": weight})
    else:
        sell_votes += weight * 0.5
        details.append({"indicator": "EMA Cross (9/21)", "signal": "SELL (weak)", "value": f"E9:{ema9_val:.5f} E21:{ema21_val:.5f}",
                        "reason": "EMA(9) below EMA(21) — downtrend", "weight": weight})

    # ── 6. SMA Trend (20/50) (weight: 10) ──
    weight = 10
    total_weight += weight
    if sma20_val > sma50_val:
        buy_votes += weight * 0.8
        details.append({"indicator": "SMA Trend (20/50)", "signal": "BUY", "value": f"S20:{sma20_val:.5f} S50:{sma50_val:.5f}",
                        "reason": "SMA(20) above SMA(50) — bullish structure", "weight": weight})
    else:
        sell_votes += weight * 0.8
        details.append({"indicator": "SMA Trend (20/50)", "signal": "SELL", "value": f"S20:{sma20_val:.5f} S50:{sma50_val:.5f}",
                        "reason": "SMA(20) below SMA(50) — bearish structure", "weight": weight})

    # ── 7. Ichimoku Cloud (weight: 10) ──
    weight = 10
    total_weight += weight
    if not pd.isna(tenkan_val) and not pd.isna(kijun_val):
        if tenkan_val > kijun_val:
            buy_votes += weight * 0.7
            details.append({"indicator": "Ichimoku Cloud", "signal": "BUY", "value": f"T:{tenkan_val:.5f} K:{kijun_val:.5f}",
                            "reason": "Tenkan-sen above Kijun-sen — bullish", "weight": weight})
        else:
            sell_votes += weight * 0.7
            details.append({"indicator": "Ichimoku Cloud", "signal": "SELL", "value": f"T:{tenkan_val:.5f} K:{kijun_val:.5f}",
                            "reason": "Tenkan-sen below Kijun-sen — bearish", "weight": weight})
    else:
        buy_votes += weight * 0.5
        details.append({"indicator": "Ichimoku Cloud", "signal": "N/A", "value": "—",
                        "reason": "Insufficient data for Ichimoku", "weight": weight})

    # ── Compute final technical score 0-100 ──
    if total_weight > 0:
        normalized_buy = buy_votes / total_weight  # 0 to 1
        normalized_sell = sell_votes / total_weight  # 0 to 1
        # Score: 0 = all sell, 50 = balanced, 100 = all buy
        raw_score = (normalized_buy / (normalized_buy + normalized_sell)) * 100 if (normalized_buy + normalized_sell) > 0 else 50
    else:
        raw_score = 50

    score = max(0, min(100, raw_score))

    # Direction label
    if score >= 65:
        direction = "BUY"
    elif score <= 35:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    return score, direction, details


# ── Entry / SL / TP Calculation ──────────────────────────────────────
# Enforces minimum 1:2 risk-reward ratio on all setups.

def calculate_levels(pair_key, current_price, direction, atr_val, df):
    """Calculate entry, stop loss, and take profit levels.
    
    Enforces minimum 1:2 RR ratio. If computed TP doesn't meet
    the minimum, the TP is extended to meet the requirement.
    Returns None if the setup cannot achieve 1:2 RR.
    """
    sl_mult = SIGNAL_CONFIG["atr_multiplier_sl"]
    tp1_mult = SIGNAL_CONFIG["atr_multiplier_tp1"]
    tp2_mult = SIGNAL_CONFIG["atr_multiplier_tp2"]
    tp3_mult = SIGNAL_CONFIG["atr_multiplier_tp3"]
    min_rr = SIGNAL_CONFIG.get("min_rr_ratio", 2.0)

    pair_info = PAIRS.get(pair_key, {})
    precision = 5 if pair_info.get("type") == "forex" else 2

    if direction == "NEUTRAL":
        return None

    if direction == "BUY":
        entry = current_price
        sl = entry - (atr_val * sl_mult)
        risk = entry - sl
        # Enforce minimum RR: TP must be at least min_rr * risk above entry
        tp1 = max(entry + (atr_val * tp1_mult), entry + (risk * min_rr))
        tp2 = max(entry + (atr_val * tp2_mult), entry + (risk * (min_rr + 1)))
        tp3 = max(entry + (atr_val * tp3_mult), entry + (risk * (min_rr + 2)))
        rr1 = (tp1 - entry) / risk if risk > 0 else 0
        rr2 = (tp2 - entry) / risk if risk > 0 else 0
        rr3 = (tp3 - entry) / risk if risk > 0 else 0
    elif direction == "SELL":
        entry = current_price
        sl = entry + (atr_val * sl_mult)
        risk = sl - entry
        # Enforce minimum RR: TP must be at least min_rr * risk below entry
        tp1 = min(entry - (atr_val * tp1_mult), entry - (risk * min_rr))
        tp2 = min(entry - (atr_val * tp2_mult), entry - (risk * (min_rr + 1)))
        tp3 = min(entry - (atr_val * tp3_mult), entry - (risk * (min_rr + 2)))
        rr1 = (entry - tp1) / risk if risk > 0 else 0
        rr2 = (entry - tp2) / risk if risk > 0 else 0
        rr3 = (entry - tp3) / risk if risk > 0 else 0
    else:
        return None

    # Validate minimum RR is met
    if rr1 < min_rr:
        return None

    return {
        "entry": round(entry, precision),
        "sl": round(sl, precision),
        "tp1": round(tp1, precision),
        "tp2": round(tp2, precision),
        "tp3": round(tp3, precision),
        "rr1": round(rr1, 2),
        "rr2": round(rr2, 2),
        "rr3": round(rr3, 2),
        "risk_pips": round(risk / (PAIRS.get(pair_key, {}).get("pip", 0.0001)), 1),
    }


# ── Generate Technical Signal (per pair) ─────────────────────────────

def generate_technical_signal(pair_key):
    """Generate the technical component of the signal using TA indicators.

    Returns dict with:
        - score (0-100)
        - direction (BUY/SELL/NEUTRAL)
        - details (list of indicator signals)
        - levels (entry, SL, TP)
        - indicators summary
    """
    df = get_historical_data(pair_key, period="1mo", interval="1h")
    if df.empty or len(df) < 50:
        return None

    # Compute ATR first
    atr_series = compute_atr(df)
    atr_val = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else float(df["Close"].iloc[-1]) * 0.01
    current_price = float(df["Close"].iloc[-1])

    # Score indicators
    score, direction, details = score_indicators(df, pair_key)

    # Calculate levels — returns None if setup doesn't meet 1:2 RR
    levels = calculate_levels(pair_key, current_price, direction, atr_val, df)

    # If levels don't meet minimum RR, downgrade to NEUTRAL
    if levels is None and direction != "NEUTRAL":
        direction = "NEUTRAL"
        score = 50

    # Compute pivots
    pivots = compute_pivot_points(df)
    support, resistance = compute_support_resistance(df)

    # Timing assessment
    macd_line, macd_signal, macd_hist = compute_macd(
        df["Close"], SIGNAL_CONFIG["macd_fast"], SIGNAL_CONFIG["macd_slow"], SIGNAL_CONFIG["macd_signal"]
    )
    rsi = compute_rsi(df["Close"])
    macd_h_val = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0
    macd_h_prev = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else macd_h_val
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

    if abs(macd_h_val) > abs(macd_h_prev) * 1.2 and abs(rsi_val - 50) > 15:
        timing = "IMMEDIATE"
    elif abs(rsi_val - 50) > 15:
        timing = "SOON"
    else:
        timing = "PATIENT"

    pair_info = PAIRS.get(pair_key, {})
    precision = 5 if pair_info.get("type") == "forex" else 2

    result = {
        "pair": pair_key,
        "pair_name": pair_info.get("name", pair_key),
        "type": pair_info.get("type", "unknown"),
        # Technical component
        "technical_score": round(score, 0),
        "technical_direction": direction,
        "technical_details": details,
        "technical_indicators": {
            "rsi": round(rsi_val, 1),
            "atr": round(atr_val, precision),
            "pivot_points": {k: round(float(v), precision) for k, v in pivots.items()},
        },
        # Levels
        "current_price": round(current_price, precision),
        # Timing
        "timing": timing,
        # Support/Resistance
        "support_levels": [round(s, precision) for s in support],
        "resistance_levels": [round(r, precision) for r in resistance],
        # Meta
        "price_change_24h": round(float(((current_price / df["Close"].iloc[-24]) - 1) * 100), 2) if len(df) >= 24 else 0,
        "updated": datetime.now().strftime("%H:%M:%S"),
    }

    # Add levels only if they meet 1:2 RR
    if levels is not None:
        result.update(levels)
        result["setup_valid"] = True
    else:
        result["setup_valid"] = False
        result["setup_invalid_reason"] = "Does not meet minimum 1:2 R:R ratio"

    return result


def generate_all_technical_signals():
    """Generate technical signals for all trading pairs."""
    signals = {}
    for pair_key in PAIRS:
        try:
            sig = generate_technical_signal(pair_key)
            if sig:
                signals[pair_key] = sig
        except Exception as e:
            signals[pair_key] = {"pair": pair_key, "error": str(e), "technical_score": 50, "technical_direction": "NEUTRAL"}
    return signals
