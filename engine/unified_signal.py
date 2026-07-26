"""Unified Signal Engine — Combines Technical + News signals into one per-pair verdict.

Each pair gets:
- technical_signal: { score (0-100), direction, details }
- news_signal: { score (0-100), direction, details }
- unified: { score (0-100), direction (BUY/SELL/NEUTRAL), verdict }
"""

from config import PAIRS
from engine.signal_engine import generate_technical_signal, generate_all_technical_signals
from engine.news_engine import get_news_signal_for_pair, get_all_news_signals

# Weights for combining (technical more weight for live action, news for context)
TECHNICAL_WEIGHT = 0.65
NEWS_WEIGHT = 0.35


def generate_unified_signal(pair_key):
    """Generate a unified signal for a single pair combining tech + news."""
    # Get technical component
    tech = generate_technical_signal(pair_key)

    # Get news component
    news = get_news_signal_for_pair(pair_key)

    if tech is None:
        return {
            "pair": pair_key,
            "pair_name": PAIRS.get(pair_key, {}).get("name", pair_key),
            "error": "Insufficient data for technical analysis",
            "news_signal": news,
            "unified": {"score": 50, "direction": "NEUTRAL", "verdict": "HOLD — waiting for data"},
        }

    tech_score = tech.get("technical_score", 50)
    news_score = news.get("score", 50)

    # Combined weighted score
    combined_score = (tech_score * TECHNICAL_WEIGHT) + (news_score * NEWS_WEIGHT)

    # Add a slight boost if both agree
    tech_dir = tech.get("technical_direction", "NEUTRAL")
    news_dir = news.get("direction", "NEUTRAL")

    agreement = "ALIGNED" if tech_dir == news_dir else "CONFLICTING" if (tech_dir == "BUY" and news_dir == "SELL") or (tech_dir == "SELL" and news_dir == "BUY") else "PARTIAL"

    if agreement == "ALIGNED" and tech_dir != "NEUTRAL":
        # Boost confidence when both agree
        combined_score = combined_score * 1.1 if combined_score > 50 else combined_score * 0.9

    combined_score = max(0, min(100, combined_score))

    # Determine unified direction
    if combined_score >= 60:
        direction = "BUY"
    elif combined_score <= 40:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    # Generate a clear verdict
    if direction == "BUY":
        verdict = f"BUY {pair_key} — "
        if agreement == "ALIGNED":
            verdict += "Technical + News both bullish. Strong confluence."
            conf = "HIGH"
        elif agreement == "PARTIAL":
            verdict += "Technical bullish, news neutral. Technically-driven setup."
            conf = "MEDIUM"
        else:
            verdict += "Technical bullish despite bearish news. Cautious entry."
            conf = "LOW"
    elif direction == "SELL":
        verdict = f"SELL {pair_key} — "
        if agreement == "ALIGNED":
            verdict += "Technical + News both bearish. Strong confluence."
            conf = "HIGH"
        elif agreement == "PARTIAL":
            verdict += "Technical bearish, news neutral. Technically-driven setup."
            conf = "MEDIUM"
        else:
            verdict += "Technical bearish despite bullish news. Cautious entry."
            conf = "LOW"
    else:
        verdict = f"HOLD {pair_key} — "
        if agreement == "CONFLICTING":
            verdict += "Tech says one thing, news says another. Wait for clarity."
            conf = "LOW"
        elif tech_score == 50 and news_score == 50:
            verdict += "No clear signal from either technical or news. Stand aside."
            conf = "LOW"
        else:
            verdict += "Mixed signals. Let confluence build."
            conf = "LOW"

    return {
        "pair": pair_key,
        "pair_name": PAIRS.get(pair_key, {}).get("name", pair_key),
        "type": PAIRS.get(pair_key, {}).get("type", "unknown"),
        # Technical component
        "technical_signal": {
            "score": round(tech_score, 0),
            "direction": tech_dir,
            "indicators": tech.get("technical_details", []),
            "summary": {
                "rsi": tech.get("technical_indicators", {}).get("rsi"),
                "pivot_points": tech.get("technical_indicators", {}).get("pivot_points"),
            },
        },
        # News component
        "news_signal": {
            "score": round(news_score, 0),
            "direction": news_dir,
            "events_analyzed": news.get("events_analyzed", 0),
            "top_events": news.get("details", []),
            "note": news.get("note", ""),
        },
        # Unified
        "unified": {
            "score": round(combined_score, 0),
            "direction": direction,
            "verdict": verdict,
            "confidence": conf,
            "agreement": agreement,
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
        # Support/Resistance
        "support_levels": tech.get("support_levels", []),
        "resistance_levels": tech.get("resistance_levels", []),
        # Timing
        "timing": tech.get("timing", "PATIENT"),
        "price_change_24h": tech.get("price_change_24h", 0),
        "updated": tech.get("updated", ""),
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
                    "unified": {"score": 50, "direction": "NEUTRAL", "verdict": f"No data for {pair_key}", "confidence": "LOW"},
                }
        except Exception as e:
            signals[pair_key] = {
                "pair": pair_key,
                "error": str(e),
                "unified": {"score": 50, "direction": "NEUTRAL", "verdict": f"Error: {e}", "confidence": "LOW"},
            }
    return signals


def get_top_setups(min_score=60, max_results=5):
    """Get the best trading setups ranked by unified score."""
    all_sigs = generate_all_unified_signals()
    setups = []

    for pair_key, sig in all_sigs.items():
        unified = sig.get("unified", {})
        score = unified.get("score", 50)
        direction = unified.get("direction", "NEUTRAL")

        if direction != "NEUTRAL" and score >= min_score:
            setups.append({
                "pair": pair_key,
                "pair_name": sig.get("pair_name", pair_key),
                "type": sig.get("type", ""),
                "score": score,
                "direction": direction,
                "verdict": unified.get("verdict", ""),
                "confidence": unified.get("confidence", "LOW"),
                "entry": sig.get("entry_price"),
                "sl": sig.get("stop_loss"),
                "tp1": sig.get("take_profit_1"),
                "tp2": sig.get("take_profit_2"),
                "rr1": sig.get("risk_reward_1"),
                "timing": sig.get("timing", "PATIENT"),
                "tech_score": sig.get("technical_signal", {}).get("score"),
                "news_score": sig.get("news_signal", {}).get("score"),
                "current_price": sig.get("current_price"),
            })

    setups.sort(key=lambda x: x["score"], reverse=True)
    return setups[:max_results]
