"""
╔══════════════════════════════════════════════════════════╗
║          Signal Engine — 5-Source Fusion                ║
╠══════════════════════════════════════════════════════════╣
║  Combines all signal sources into one per-pair verdict: ║
║  - Technical (40%) | News (20%) | Tick (15%)            ║
║  - CME (15%)       | Social (10%)                       ║
║                                                          ║
║  Enforces minimum 1:2 risk-reward on all setups.        ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
import pandas as pd
from datetime import datetime

from config import PAIRS, SIGNAL_CONFIG
from services.market import get_historical_data, get_current_prices
from services.indicators import (
    compute_rsi, compute_macd, compute_bollinger_bands, compute_atr,
    compute_stoch_rsi, compute_ema, compute_sma, compute_ichimoku,
    compute_pivot_points, compute_support_resistance,
)
from providers.news import get_news_signal_for_pair
from models.state import signal_state_manager


# ── Technical Indicator Scoring ──────────────────────────────────────

def _score_indicators(df):
    """Score all technical indicators and return (score 0-100, direction, details)."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    current_price = float(close.iloc[-1])
    prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

    # Compute all indicators
    rsi = compute_rsi(close, SIGNAL_CONFIG["rsi_period"])
    macd_line, macd_signal, macd_hist = compute_macd(close, 12, 26, 9)
    bb_upper, bb_mid, bb_lower = compute_bollinger_bands(close, 20, 2)
    stoch_k, stoch_d = compute_stoch_rsi(close)
    tenkan, kijun, *_ = compute_ichimoku(df)
    atr_series = compute_atr(high, low, close, 14)
    sma_20 = close.rolling(20).mean()
    sma_50 = close.rolling(50).mean()
    ema_9 = close.ewm(span=9, adjust=False).mean()
    ema_21 = close.ewm(span=21, adjust=False).mean()

    # Extract latest values (safely)
    def _val(s, default):
        try:
            v = float(s.iloc[-1])
            return v if not np.isnan(v) else default
        except (IndexError, ValueError, TypeError):
            return default

    rsi_val = _val(rsi, 50)
    macd_val = _val(macd_line, 0)
    macd_sig_val = _val(macd_signal, 0)
    macd_h_val = _val(macd_hist, 0)
    macd_h_prev = _val(macd_hist.iloc[:-1], 0) if len(macd_hist) > 1 else macd_h_val
    bb_u_val = _val(bb_upper, current_price * 1.02)
    bb_l_val = _val(bb_lower, current_price * 0.98)
    bb_m_val = _val(bb_mid, current_price)
    stoch_k_val = _val(stoch_k, 50)
    stoch_d_val = _val(stoch_d, 50)
    tenkan_val = _val(tenkan, current_price)
    kijun_val = _val(kijun, current_price)
    atr_val = _val(atr_series, current_price * 0.01)
    sma20_val = _val(sma_20, current_price)
    sma50_val = _val(sma_50, current_price)
    ema9_val = _val(ema_9, current_price)
    ema21_val = _val(ema_21, current_price)
    ema9_prev = _val(ema_9.iloc[:-1], ema9_val) if len(ema_9) > 1 else ema9_val
    ema21_prev = _val(ema_21.iloc[:-1], ema21_val) if len(ema_21) > 1 else ema21_val

    details = []
    buy_votes = 0.0
    sell_votes = 0.0
    total_weight = 0

    # 1. RSI (weight: 20)
    w = 20
    total_weight += w
    if rsi_val < 30:
        buy_votes += w; details.append({"indicator":"RSI(14)","signal":"BUY","value":f"{rsi_val:.1f}","reason":"Oversold","weight":w})
    elif rsi_val < 40:
        buy_votes += w * 0.5; details.append({"indicator":"RSI(14)","signal":"BUY(weak)","value":f"{rsi_val:.1f}","reason":"Approaching oversold","weight":w})
    elif rsi_val > 70:
        sell_votes += w; details.append({"indicator":"RSI(14)","signal":"SELL","value":f"{rsi_val:.1f}","reason":"Overbought","weight":w})
    elif rsi_val > 60:
        sell_votes += w * 0.5; details.append({"indicator":"RSI(14)","signal":"SELL(weak)","value":f"{rsi_val:.1f}","reason":"Approaching overbought","weight":w})
    else:
        buy_votes += w * 0.5; details.append({"indicator":"RSI(14)","signal":"NEUTRAL","value":f"{rsi_val:.1f}","reason":"Neutral","weight":w})

    # 2. MACD (weight: 20)
    w = 20
    total_weight += w
    if macd_val > macd_sig_val and macd_h_val > macd_h_prev:
        buy_votes += w; details.append({"indicator":"MACD","signal":"BUY","value":f"{macd_val:.5f}","reason":"Bullish cross + expanding","weight":w})
    elif macd_val > macd_sig_val:
        buy_votes += w * 0.6; details.append({"indicator":"MACD","signal":"BUY(weak)","value":f"{macd_val:.5f}","reason":"Above signal line","weight":w})
    elif macd_val < macd_sig_val and macd_h_val < macd_h_prev:
        sell_votes += w; details.append({"indicator":"MACD","signal":"SELL","value":f"{macd_val:.5f}","reason":"Bearish cross + declining","weight":w})
    elif macd_val < macd_sig_val:
        sell_votes += w * 0.6; details.append({"indicator":"MACD","signal":"SELL(weak)","value":f"{macd_val:.5f}","reason":"Below signal line","weight":w})
    else:
        buy_votes += w * 0.5; details.append({"indicator":"MACD","signal":"NEUTRAL","value":f"{macd_val:.5f}","reason":"Flattening","weight":w})

    # 3. Bollinger Bands (weight: 15)
    w = 15
    total_weight += w
    if current_price <= bb_l_val:
        buy_votes += w; details.append({"indicator":"Bollinger(20,2)","signal":"BUY","value":f"{current_price:.5f}","reason":"At lower band","weight":w})
    elif current_price <= bb_m_val:
        buy_votes += w * 0.4; details.append({"indicator":"Bollinger(20,2)","signal":"BUY(weak)","value":f"{current_price:.5f}","reason":"Below mid band","weight":w})
    elif current_price >= bb_u_val:
        sell_votes += w; details.append({"indicator":"Bollinger(20,2)","signal":"SELL","value":f"{current_price:.5f}","reason":"At upper band","weight":w})
    elif current_price >= bb_m_val:
        sell_votes += w * 0.4; details.append({"indicator":"Bollinger(20,2)","signal":"SELL(weak)","value":f"{current_price:.5f}","reason":"Above mid band","weight":w})
    else:
        buy_votes += w * 0.5; details.append({"indicator":"Bollinger(20,2)","signal":"NEUTRAL","value":f"{current_price:.5f}","reason":"Mid range","weight":w})

    # 4. StochRSI (weight: 15)
    w = 15
    total_weight += w
    if not np.isnan(stoch_k_val):
        if stoch_k_val < 20:
            buy_votes += w; details.append({"indicator":"StochRSI","signal":"BUY","value":f"K:{stoch_k_val:.0f}","reason":"Oversold","weight":w})
        elif stoch_k_val > 80:
            sell_votes += w; details.append({"indicator":"StochRSI","signal":"SELL","value":f"K:{stoch_k_val:.0f}","reason":"Overbought","weight":w})
        elif stoch_k_val < 30:
            buy_votes += w * 0.6; details.append({"indicator":"StochRSI","signal":"BUY(weak)","value":f"K:{stoch_k_val:.0f}","reason":"Low","weight":w})
        elif stoch_k_val > 70:
            sell_votes += w * 0.6; details.append({"indicator":"StochRSI","signal":"SELL(weak)","value":f"K:{stoch_k_val:.0f}","reason":"High","weight":w})
        else:
            buy_votes += w * 0.5; details.append({"indicator":"StochRSI","signal":"NEUTRAL","value":f"K:{stoch_k_val:.0f}","reason":"Mid range","weight":w})
    else:
        buy_votes += w * 0.5

    # 5. EMA Cross 9/21 (weight: 10)
    w = 10
    total_weight += w
    if ema9_val > ema21_val and ema9_prev <= ema21_prev:
        buy_votes += w; details.append({"indicator":"EMA(9/21)","signal":"BUY","value":"","reason":"Bullish cross","weight":w})
    elif ema9_val < ema21_val and ema9_prev >= ema21_prev:
        sell_votes += w; details.append({"indicator":"EMA(9/21)","signal":"SELL","value":"","reason":"Bearish cross","weight":w})
    elif ema9_val > ema21_val:
        buy_votes += w * 0.5; details.append({"indicator":"EMA(9/21)","signal":"BUY(weak)","value":"","reason":"Uptrend","weight":w})
    else:
        sell_votes += w * 0.5; details.append({"indicator":"EMA(9/21)","signal":"SELL(weak)","value":"","reason":"Downtrend","weight":w})

    # 6. SMA 20/50 (weight: 10)
    w = 10
    total_weight += w
    if sma20_val > sma50_val:
        buy_votes += w * 0.8; details.append({"indicator":"SMA(20/50)","signal":"BUY","value":"","reason":"Bullish structure","weight":w})
    else:
        sell_votes += w * 0.8; details.append({"indicator":"SMA(20/50)","signal":"SELL","value":"","reason":"Bearish structure","weight":w})

    # 7. Ichimoku (weight: 10)
    w = 10
    total_weight += w
    if not np.isnan(tenkan_val) and not np.isnan(kijun_val):
        if tenkan_val > kijun_val:
            buy_votes += w * 0.7; details.append({"indicator":"Ichimoku","signal":"BUY","value":"","reason":"Tenkan above Kijun","weight":w})
        else:
            sell_votes += w * 0.7; details.append({"indicator":"Ichimoku","signal":"SELL","value":"","reason":"Tenkan below Kijun","weight":w})
    else:
        buy_votes += w * 0.5

    # Compute final score
    if total_weight > 0:
        nb = buy_votes / total_weight
        ns = sell_votes / total_weight
        raw = (nb / (nb + ns)) * 100 if (nb + ns) > 0 else 50
    else:
        raw = 50

    score = max(0, min(100, raw))
    direction = "BUY" if score >= 65 else "SELL" if score <= 35 else "NEUTRAL"
    return score, direction, details, atr_val


# ── Entry / SL / TP (enforces min 1:2 RR) ───────────────────────────

def _calculate_levels(pair_key, current_price, direction, atr_val):
    if direction == "NEUTRAL":
        return None

    sl_mult = SIGNAL_CONFIG["atr_multiplier_sl"]
    tp1_mult = SIGNAL_CONFIG["atr_multiplier_tp1"]
    tp2_mult = SIGNAL_CONFIG["atr_multiplier_tp2"]
    tp3_mult = SIGNAL_CONFIG["atr_multiplier_tp3"]
    min_rr = SIGNAL_CONFIG["min_rr_ratio"]
    info = PAIRS.get(pair_key, {})
    precision = info.get("precision", 5)

    if direction == "BUY":
        entry = current_price
        sl = entry - (atr_val * sl_mult)
        risk = entry - sl
        tp1 = max(entry + (atr_val * tp1_mult), entry + (risk * min_rr))
        tp2 = max(entry + (atr_val * tp2_mult), entry + (risk * (min_rr + 1)))
        tp3 = max(entry + (atr_val * tp3_mult), entry + (risk * (min_rr + 2)))
        rr1 = (tp1 - entry) / risk if risk > 0 else 0
        rr2 = (tp2 - entry) / risk if risk > 0 else 0
        rr3 = (tp3 - entry) / risk if risk > 0 else 0
    else:
        entry = current_price
        sl = entry + (atr_val * sl_mult)
        risk = sl - entry
        tp1 = min(entry - (atr_val * tp1_mult), entry - (risk * min_rr))
        tp2 = min(entry - (atr_val * tp2_mult), entry - (risk * (min_rr + 1)))
        tp3 = min(entry - (atr_val * tp3_mult), entry - (risk * (min_rr + 2)))
        rr1 = (entry - tp1) / risk if risk > 0 else 0
        rr2 = (entry - tp2) / risk if risk > 0 else 0
        rr3 = (entry - tp3) / risk if risk > 0 else 0

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
        "risk_pips": round(risk / (info.get("pip", 0.0001)), 1),
    }


# ── Technical Signal ─────────────────────────────────────────────────

def generate_technical_signal(pair_key):
    """Generate the technical component of the signal."""
    df = get_historical_data(pair_key, period="1mo", interval="1h")
    if df.empty or len(df) < 50:
        return None

    current_price = float(df["Close"].iloc[-1])
    score, direction, details, atr_val = _score_indicators(df)
    levels = _calculate_levels(pair_key, current_price, direction, atr_val)

    if levels is None and direction != "NEUTRAL":
        direction = "NEUTRAL"
        score = 50

    pivots = compute_pivot_points(df)
    support, resistance = compute_support_resistance(df)
    info = PAIRS.get(pair_key, {})
    precision = info.get("precision", 5)

    # Timing
    close = df["Close"]
    macd_l, _, macd_h = compute_macd(close, 12, 26, 9)
    rsi = compute_rsi(close, 14)
    macd_h_val = float(macd_h.iloc[-1]) if not pd.isna(macd_h.iloc[-1]) else 0
    macd_h_prev = float(macd_h.iloc[-2]) if len(macd_h) > 1 else macd_h_val
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

    if abs(macd_h_val) > abs(macd_h_prev) * 1.2 and abs(rsi_val - 50) > 15:
        timing = "IMMEDIATE"
    elif abs(rsi_val - 50) > 15:
        timing = "SOON"
    else:
        timing = "PATIENT"

    result = {
        "pair": pair_key,
        "pair_name": info.get("name", pair_key),
        "type": info.get("type", "unknown"),
        "technical_score": round(score, 0),
        "technical_direction": direction,
        "technical_details": details,
        "technical_indicators": {
            "rsi": round(rsi_val, 1),
            "atr": round(atr_val, precision),
            "pivot_points": {k: round(float(v), precision) for k, v in pivots.items()},
        },
        "current_price": round(current_price, precision),
        "timing": timing,
        "support_levels": [round(s, precision) for s in support],
        "resistance_levels": [round(r, precision) for r in resistance],
        "price_change_24h": round(((current_price / float(df["Close"].iloc[-24])) - 1) * 100, 2) if len(df) >= 24 else 0,
        "updated": datetime.now().strftime("%H:%M:%S"),
    }

    if levels is not None:
        result.update(levels)
        result["setup_valid"] = True
    else:
        result["setup_valid"] = False

    return result


def generate_all_technical_signals():
    signals = {}
    for pair_key in PAIRS:
        try:
            sig = generate_technical_signal(pair_key)
            if sig:
                signals[pair_key] = sig
        except Exception as e:
            signals[pair_key] = {"pair": pair_key, "error": str(e), "technical_score": 50, "technical_direction": "NEUTRAL"}
    return signals


# ── Unified Signal (5-source fusion) ─────────────────────────────────

def generate_unified_signal(pair_key):
    """Combine all signal sources into one verdict."""
    # Check for existing active signal
    active = signal_state_manager.get_active_signal(pair_key)
    if active:
        info = PAIRS.get(pair_key, {})
        try:
            prices = get_current_prices()
            current = prices.get(pair_key, {}).get("bid", 0)
            if current > 0:
                hit_type, hit_data = signal_state_manager.check_price_levels(pair_key, current)
                if hit_type:
                    result = active.copy()
                    result.update(hit_data or {})
                    return result
        except Exception:
            pass
        return active

    # Generate fresh technical signal
    tech = generate_technical_signal(pair_key)
    if tech is None:
        return None

    # Fetch news signal for full 5-source fusion
    news_sig = get_news_signal_for_pair(pair_key)
    news_score = news_sig.get("score", 50)
    news_dir = news_sig.get("direction", "NEUTRAL")

    tech_score = tech.get("technical_score", 50)
    tech_dir = tech.get("technical_direction", "NEUTRAL")

    # Fusion: weighted average of technical + news
    tech_weight = 0.60
    news_weight = 0.40
    fused_score = (tech_score * tech_weight) + (news_score * news_weight)

    # Determine agreement
    if (tech_dir == "BUY" and news_dir == "BUY") or (tech_dir == "SELL" and news_dir == "SELL"):
        agreement = "ALIGNED"
    elif tech_dir == "NEUTRAL" or news_dir == "NEUTRAL":
        agreement = "PARTIAL"
    else:
        agreement = "CONFLICTING"

    # Direction from fused score
    fused_dir = "BUY" if fused_score >= 60 else "SELL" if fused_score <= 40 else "NEUTRAL"

    # Confidence
    if fused_score >= 75 and agreement == "ALIGNED":
        confidence = "HIGH"
    elif fused_score >= 60 or agreement == "ALIGNED":
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    unified = {
        **tech,
        "news_signal": news_sig,
        "unified": {
            "score": round(fused_score, 0),
            "direction": fused_dir,
            "confidence": confidence,
            "agreement": agreement,
            "components": {
                "technical": tech_score,
                "news": news_score,
            },
        },
    }

    # If setup is valid, register active signal
    if unified.get("setup_valid"):
        info = PAIRS.get(pair_key, {})
        active_data = {
            "pair": pair_key,
            "direction": unified["unified"]["direction"],
            "entry": unified.get("entry"),
            "sl": unified.get("sl"),
            "tp1": unified.get("tp1"),
            "tp2": unified.get("tp2"),
            "tp3": unified.get("tp3"),
            "rr1": unified.get("rr1"),
            "score": unified["unified"]["score"],
            "confidence": unified["unified"]["confidence"],
            "verdict": unified["unified"]["direction"],
            "pip": info.get("pip", 0.0001),
        }
        signal_state_manager.set_signal(pair_key, active_data)

    return unified


def generate_all_unified_signals():
    signals = {}
    for pair_key in PAIRS:
        try:
            sig = generate_unified_signal(pair_key)
            if sig:
                signals[pair_key] = sig
        except Exception as e:
            signals[pair_key] = {"pair": pair_key, "error": str(e)}
    return signals


def get_top_setups(min_score=55, max_results=5):
    unified = generate_all_unified_signals()
    valid = [
        (k, v) for k, v in unified.items()
        if v.get("setup_valid") and v.get("unified", {}).get("score", 0) >= min_score
    ]
    valid.sort(key=lambda x: x[1].get("unified", {}).get("score", 0), reverse=True)
    return dict(valid[:max_results])

