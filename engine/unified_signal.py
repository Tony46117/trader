"""Unified Signal Engine — Combines all signal sources into one per-pair verdict.

Each pair gets signals from:
- Technical analysis (RSI, MACD, BB, EMA, Ichimoku, etc.) — 40%
- News events (Forex Factory, economic calendar) — 20%
- Tick data (volatility, momentum, microstructure) — 15%
- CME futures/options (open interest, max pain, gamma) — 15%
- Social media sentiment (Twitter, Truth Social, Reddit) — 10%

Total = high-quality unified signal with entry, SL, TP and conviction scoring.
"""

import numpy as np
from datetime import datetime

from config import PAIRS
from engine.signal_engine import generate_technical_signal, generate_all_technical_signals
from engine.news_engine import get_news_signal_for_pair, get_all_news_signals
from engine.tick_data import get_tick_signal
from engine.cme_data import get_cme_analysis
from engine.social_news import get_social_signal

# Weights for each signal component
WEIGHTS = {
    "technical": 0.40,
    "news": 0.20,
    "tick": 0.15,
    "cme": 0.15,
    "social": 0.10,
}


def _score_to_direction(score):
    """Convert 0-100 score to direction."""
    if score >= 60:
        return "BUY"
    elif score <= 40:
        return "SELL"
    return "NEUTRAL"


def _compute_conviction(score, agreement_level, vol_factor=1.0):
    """Compute conviction level based on score strength and agreement."""
    base = abs(score - 50) * 2  # 0-100 scaled from deviation
    agreement_bonus = {"ALIGNED": 20, "PARTIAL": 10, "CONFLICTING": -20, "NEUTRAL": 0}.get(agreement_level, 0)
    vol_penalty = (1.0 - vol_factor) * 15  # Reduce conviction in high vol

    total = base + agreement_bonus - vol_penalty

    if total >= 70:
        return "HIGH"
    elif total >= 40:
        return "MEDIUM"
    else:
        return "LOW"


def generate_unified_signal(pair_key):
    """Generate a comprehensive unified signal for a single pair.

    Combines technical, news, tick, CME, and social signals into one verdict.
    """
    # ── 1. Technical signal ──
    tech = generate_technical_signal(pair_key)
    if tech is None:
        return {
            "pair": pair_key,
            "pair_name": PAIRS.get(pair_key, {}).get("name", pair_key),
            "error": "Insufficient data for technical analysis",
            "unified": {"score": 50, "direction": "NEUTRAL", "verdict": "HOLD — waiting for data"},
        }

    tech_score = tech.get("technical_score", 50)
    tech_dir = tech.get("technical_direction", "NEUTRAL")
    current_price = tech.get("current_price", 0)

    # ── 2. News signal ──
    news = get_news_signal_for_pair(pair_key)
    news_score = news.get("score", 50)
    news_dir = news.get("direction", "NEUTRAL")

    # ── 3. Tick data signal ──
    tick = get_tick_signal(pair_key, current_price)
    tick_momentum = tick.get("momentum_score", 50)
    tick_dir = "BUY" if tick_momentum > 55 else "SELL" if tick_momentum < 45 else "NEUTRAL"
    vol_factor = tick.get("vol_factor", 1.0)

    # ── 4. CME signal ──
    cme = get_cme_analysis(pair_key, current_price)
    cme_assessment = cme.get("assessment", "neutral")
    cme_score = {"bullish": 70, "bearish": 30, "neutral": 50}.get(cme_assessment, 50)
    cme_dir = cme_assessment.upper() if cme_assessment in ("bullish", "bearish") else "NEUTRAL"
    cme_conviction = cme.get("conviction", "low")

    # ── 5. Social media signal ──
    social = get_social_signal(pair_key)
    social_score = social.get("sentiment_score", 50)
    social_class = social.get("classification", "neutral")
    social_dir = social_class.upper() if social_class in ("bullish", "bearish") else "NEUTRAL"

    # ── Weighted combination ──
    w = WEIGHTS
    combined_score = (
        tech_score * w["technical"] +
        news_score * w["news"] +
        tick_momentum * w["tick"] +
        cme_score * w["cme"] +
        social_score * w["social"]
    )

    # Compute agreement between all sources
    directions = [tech_dir, news_dir, tick_dir, cme_dir, social_dir]
    buy_count = sum(1 for d in directions if d == "BUY")
    sell_count = sum(1 for d in directions if d == "SELL")
    neutral_count = sum(1 for d in directions if d == "NEUTRAL")

    if buy_count >= 4:
        agreement = "ALIGNED"
    elif sell_count >= 4:
        agreement = "ALIGNED"
    elif buy_count >= 3 and sell_count == 0:
        agreement = "ALIGNED"
    elif sell_count >= 3 and buy_count == 0:
        agreement = "ALIGNED"
    elif buy_count >= 2 and sell_count >= 2:
        agreement = "CONFLICTING"
    elif buy_count >= 1 and sell_count >= 1:
        agreement = "PARTIAL"
    else:
        agreement = "NEUTRAL"

    # Apply agreement boost
    if agreement == "ALIGNED" and buy_count > sell_count:
        combined_score = min(100, combined_score * 1.08)
    elif agreement == "ALIGNED" and sell_count > buy_count:
        combined_score = max(0, combined_score * 0.92)

    combined_score = max(0, min(100, combined_score))
    direction = _score_to_direction(combined_score)
    confidence = _compute_conviction(combined_score, agreement, vol_factor)

    # ── Generate verdict ──
    pair_name = PAIRS.get(pair_key, {}).get("name", pair_key)

    if direction == "BUY":
        if agreement == "ALIGNED":
            verdict = f"STRONG BUY {pair_key} — All signal sources aligned bullish."
        elif agreement == "PARTIAL":
            verdict = f"BUY {pair_key} — Majority of signals bullish."
        else:
            verdict = f"CAUTIOUS BUY {pair_key} — Mixed signals but technicals favor longs."
    elif direction == "SELL":
        if agreement == "ALIGNED":
            verdict = f"STRONG SELL {pair_key} — All signal sources aligned bearish."
        elif agreement == "PARTIAL":
            verdict = f"SELL {pair_key} — Majority of signals bearish."
        else:
            verdict = f"CAUTIOUS SELL {pair_key} — Mixed signals but technicals favor shorts."
    else:
        if agreement == "CONFLICTING":
            verdict = f"HOLD {pair_key} — Conflicting signals. Wait for alignment."
        else:
            verdict = f"HOLD {pair_key} — No clear directional bias."

    # ── Build CME key levels ──
    cme_levels = cme.get("key_levels", {})

    return {
        "pair": pair_key,
        "pair_name": pair_name,
        "type": PAIRS.get(pair_key, {}).get("type", "unknown"),
        # Individual components
        "technical_signal": {
            "score": round(tech_score, 0),
            "direction": tech_dir,
            "indicators": tech.get("technical_details", []),
            "rsi": tech.get("technical_indicators", {}).get("rsi"),
            "atr": tech.get("technical_indicators", {}).get("atr"),
        },
        "news_signal": {
            "score": round(news_score, 0),
            "direction": news_dir,
            "events_analyzed": news.get("events_analyzed", 0),
            "top_events": news.get("details", []),
        },
        "tick_signal": {
            "score": round(tick_momentum, 0),
            "direction": tick_dir,
            "volatility_regime": tick.get("volatility_regime", "unknown"),
            "micro_trend": tick.get("micro_trend", "neutral"),
            "tick_imbalance": tick.get("tick_imbalance", 0),
            "liquidity_score": tick.get("liquidity_score", 5),
        },
        "cme_signal": {
            "score": round(cme_score, 0),
            "direction": cme_dir,
            "assessment": cme_assessment,
            "conviction": cme_conviction,
            "max_pain": cme.get("options", {}).get("max_pain", 0),
            "put_call_ratio": cme.get("options", {}).get("put_call_ratio", 1.0),
            "gamma_levels": {
                "high": cme_levels.get("gamma_flip_high", 0),
                "low": cme_levels.get("gamma_flip_low", 0),
            },
        },
        "social_signal": {
            "score": round(social_score, 0),
            "direction": social_dir,
            "classification": social_class,
            "mention_volume": social.get("mention_volume", 0),
            "consensus": social.get("consensus", "mixed"),
        },
        # Unified
        "unified": {
            "score": round(combined_score, 0),
            "direction": direction,
            "verdict": verdict,
            "confidence": confidence,
            "agreement": agreement,
            "components": {
                "technical": round(tech_score, 0),
                "news": round(news_score, 0),
                "tick": round(tick_momentum, 0),
                "cme": round(cme_score, 0),
                "social": round(social_score, 0),
            },
        },
        # Levels from technical
        "current_price": tech.get("current_price"),
        "entry_price": tech.get("entry"),
        "stop_loss": tech.get("sl"),
        "take_profit_1": tech.get("tp1"),
        "take_profit_2": tech.get("tp2"),
        "take_profit_3": tech.get("tp3"),
        "risk_reward_1": tech.get("rr1"),
        "risk_reward_2": tech.get("rr2"),
        # CME levels
        "cme_levels": {
            "primary_resistance": cme_levels.get("primary_resistance"),
            "primary_support": cme_levels.get("primary_support"),
            "max_pain": cme_levels.get("max_pain"),
        },
        # Support/Resistance
        "support_levels": tech.get("support_levels", []),
        "resistance_levels": tech.get("resistance_levels", []),
        # Timing
        "timing": tech.get("timing", "PATIENT"),
        "price_change_24h": tech.get("price_change_24h", 0),
        "updated": datetime.now().strftime("%H:%M:%S"),
    }


def generate_all_unified_signals():
    """Generate unified signals for all trading pairs."""
    signals = {}
    for pair_key in PAIRS:
        try:
            sig = generate_unified_signal(pair_key)
            if sig:
                signals[pair_key] = sig
            else:
                signals[pair_key] = {
                    "pair": pair_key,
                    "unified": {"score": 50, "direction": "NEUTRAL", "verdict": f"No data for {pair_key}"},
                }
        except Exception as e:
            signals[pair_key] = {
                "pair": pair_key,
                "error": str(e),
                "unified": {"score": 50, "direction": "NEUTRAL", "verdict": f"Error: {e}"},
            }
    return signals


def get_top_setups(min_score=60, max_results=5):
    """Get the best trading setups ranked by unified score.

    Filters for high-confidence setups with clear entry/SL/TP levels.
    """
    all_sigs = generate_all_unified_signals()
    setups = []

    for pair_key, sig in all_sigs.items():
        unified = sig.get("unified", {})
        score = unified.get("score", 50)
        direction = unified.get("direction", "NEUTRAL")
        confidence = unified.get("confidence", "LOW")

        if direction != "NEUTRAL" and score >= min_score:
            rr1 = sig.get("risk_reward_1", 0)
            setup_quality = score * (1.0 if confidence == "HIGH" else 0.8 if confidence == "MEDIUM" else 0.5)

            setups.append({
                "pair": pair_key,
                "pair_name": sig.get("pair_name", pair_key),
                "type": sig.get("type", ""),
                "score": score,
                "direction": direction,
                "verdict": unified.get("verdict", ""),
                "confidence": confidence,
                "setup_quality": round(setup_quality, 0),
                "entry": sig.get("entry_price"),
                "sl": sig.get("stop_loss"),
                "tp1": sig.get("take_profit_1"),
                "tp2": sig.get("take_profit_2"),
                "rr1": rr1,
                "timing": sig.get("timing", "PATIENT"),
                "components": unified.get("components", {}),
                "current_price": sig.get("current_price"),
                "cme_levels": sig.get("cme_levels", {}),
            })

    setups.sort(key=lambda x: x["setup_quality"], reverse=True)
    return setups[:max_results]
