"""
╔══════════════════════════════════════════════════════════╗
║          CME Provider — Futures & Options Analysis      ║
╠══════════════════════════════════════════════════════════╣
║  Analyzes CME futures positioning, open interest,       ║
║  options max pain, gamma levels, and put/call ratios.   ║
║  Returns directional signal + detailed option chain.    ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
import random
from datetime import datetime
from config import PAIRS

CME_FUTURES = {
    "EURUSD": {"future": "6E", "name": "Euro FX", "point_value": 125000, "strike_step": 0.0025},
    "GBPUSD": {"future": "6B", "name": "British Pound", "point_value": 62500, "strike_step": 0.0025},
    "XAUUSD": {"future": "GC", "name": "Gold", "point_value": 100, "strike_step": 5.0},
    "BTCUSD": {"future": "BTC", "name": "Bitcoin", "point_value": 5, "strike_step": 500.0},
    "ETHUSD": {"future": "ETH", "name": "Ethereum", "point_value": 50, "strike_step": 25.0},
}


def _get_seed(pair_key):
    return abs(hash(pair_key + datetime.now().strftime("%Y%m%d%H"))) % 2**32


def _generate_option_chain(pair_key, current_price):
    """Generate a simulated option chain with strikes, OI, volume, and put/call data."""
    info = CME_FUTURES.get(pair_key, {})
    strike_step = info.get("strike_step", 0.0025)
    price = float(current_price) if current_price else 1.0

    seed = _get_seed(pair_key)
    np.random.seed(seed)
    random.seed(seed)

    # Generate strikes around current price (10 below, 10 above)
    num_strikes = 21
    half = num_strikes // 2
    strikes = [price + (i - half) * strike_step for i in range(num_strikes)]

    chain = []
    for strike in strikes:
        # Distance from current price
        dist_pct = abs(strike - price) / price

        # OI decays with distance from current price (ATM has highest OI)
        oi_base = max(1000, np.random.exponential(15000) * np.exp(-dist_pct * 50))
        call_oi = int(oi_base * np.random.uniform(0.7, 1.3))
        put_oi = int(oi_base * np.random.uniform(0.7, 1.3))

        # Volume correlates with OI
        call_vol = int(call_oi * np.random.uniform(0.1, 0.4))
        put_vol = int(put_oi * np.random.uniform(0.1, 0.4))

        # Implied volatility skew (OTM puts > OTM calls for most pairs)
        if strike < price:
            iv = np.random.uniform(0.12, 0.28)  # Puts slightly higher IV
        elif strike > price:
            iv = np.random.uniform(0.10, 0.22)  # Calls slightly lower IV
        else:
            iv = np.random.uniform(0.11, 0.20)  # ATM

        # Greeks (simplified)
        moneyness = (strike - price) / price
        delta_call = 1 / (1 + np.exp(-moneyness * 20))
        delta_put = delta_call - 1
        gamma = np.exp(-moneyness**2 * 100) * 0.05
        theta = -np.random.uniform(0.5, 2.0)

        chain.append({
            "strike": round(strike, 5),
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "total_oi": call_oi + put_oi,
            "total_volume": call_vol + put_vol,
            "pc_ratio": round(put_oi / call_oi, 2) if call_oi > 0 else 99.99,
            "iv": round(iv * 100, 1),
            "delta_call": round(delta_call, 3),
            "delta_put": round(delta_put, 3),
            "gamma": round(gamma, 4),
            "theta": round(theta, 2),
            "distance_pct": round(dist_pct * 100, 2),
        })

    # Sort by strike
    chain.sort(key=lambda x: x["strike"])
    return chain


def _find_key_levels(chain, current_price):
    """Find key support/resistance levels from option chain concentrations."""
    if not chain:
        return [], []

    # Find strikes with high total OI (concentration levels)
    max_oi = max(c["total_oi"] for c in chain)
    oi_threshold = max_oi * 0.6

    high_oi_strikes = [c for c in chain if c["total_oi"] >= oi_threshold]

    # Separate into support (below price) and resistance (above price)
    supports = []
    resistances = []

    for c in high_oi_strikes:
        level = {
            "price": c["strike"],
            "total_oi": c["total_oi"],
            "call_oi": c["call_oi"],
            "put_oi": c["put_oi"],
            "call_volume": c["call_volume"],
            "put_volume": c["put_volume"],
            "pc_ratio": c["pc_ratio"],
            "distance_pct": c["distance_pct"],
            "strength": "MAJOR" if c["total_oi"] >= max_oi * 0.85 else "MINOR",
        }
        if c["strike"] < current_price:
            supports.append(level)
        elif c["strike"] > current_price:
            resistances.append(level)

    # Sort supports descending (closest to price first), resistances ascending
    supports.sort(key=lambda x: x["price"], reverse=True)
    resistances.sort(key=lambda x: x["price"])

    return supports[:5], resistances[:5]


def get_cme_signal(pair_key, current_price):
    """Generate CME-based signal score (0-100)."""
    seed = _get_seed(pair_key)
    np.random.seed(seed)
    random.seed(seed)

    price = float(current_price) if current_price else 1.0

    # Generate option chain
    chain = _generate_option_chain(pair_key, price)

    # Calculate aggregated metrics from the chain
    total_call_oi = sum(c["call_oi"] for c in chain)
    total_put_oi = sum(c["put_oi"] for c in chain)
    total_call_vol = sum(c["call_volume"] for c in chain)
    total_put_vol = sum(c["put_volume"] for c in chain)

    # Put/Call ratio from total OI
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else 1.0

    # Max pain: strike with highest combined OI (call_oi + put_oi)
    max_pain_strike = max(chain, key=lambda c: c["total_oi"])
    max_pain = max_pain_strike["strike"]

    # Volume profile: find price level with highest volume
    max_vol_strike = max(chain, key=lambda c: c["total_volume"])

    # Find key support/resistance levels
    supports, resistances = _find_key_levels(chain, price)

    # Simulated futures positioning
    net_non_commercial = np.random.uniform(-150000, 150000)
    positioning = "net_long" if net_non_commercial > 0 else "net_short"
    positioning_strength = min(100, abs(net_non_commercial) / 3000)

    # Compute score from positioning + options sentiment
    score = 50  # Start neutral
    if positioning == "net_long":
        score += 15 * (positioning_strength / 100)
    else:
        score -= 15 * (positioning_strength / 100)

    pc_sentiment = "bullish" if pc_oi_ratio < 0.85 else "bearish" if pc_oi_ratio > 1.15 else "neutral"
    if pc_sentiment == "bullish":
        score += 10
    elif pc_sentiment == "bearish":
        score -= 10

    # Volume confirmation
    volume_sentiment = total_call_vol / (total_call_vol + total_put_vol) * 100 if (total_call_vol + total_put_vol) > 0 else 50
    if volume_sentiment > 60:
        score += 5
    elif volume_sentiment < 40:
        score -= 5

    score = max(0, min(100, score))
    direction = "BUY" if score >= 60 else "SELL" if score <= 40 else "NEUTRAL"

    return {
        "score": round(score, 0),
        "direction": direction,
        "pair": pair_key,
        "max_pain": round(max_pain, 5),
        "current_price": round(price, 5),
        "put_call_ratio_oi": round(pc_oi_ratio, 3),
        "put_call_ratio_vol": round(pc_vol_ratio, 3),
        "pc_sentiment": pc_sentiment,
        "positioning": positioning,
        "positioning_strength": round(positioning_strength, 0),
        "max_volume_strike": round(max_vol_strike["strike"], 5),
        "max_volume": max_vol_strike["total_volume"],
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
        "supports": supports,
        "resistances": resistances,
    }


def get_cme_levels(pair_key, current_price):
    """Get detailed CME option chain levels for a pair."""
    price = float(current_price) if current_price else 1.0
    chain = _generate_option_chain(pair_key, price)
    supports, resistances = _find_key_levels(chain, price)
    max_pain_strike = max(chain, key=lambda c: c["total_oi"])

    # Aggregated metrics for frontend
    total_call_oi = sum(c["call_oi"] for c in chain)
    total_put_oi = sum(c["put_oi"] for c in chain)
    total_call_vol = sum(c["call_volume"] for c in chain)
    total_put_vol = sum(c["put_volume"] for c in chain)
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else 1.0
    pc_sentiment = "bullish" if pc_oi_ratio < 0.85 else "bearish" if pc_oi_ratio > 1.15 else "neutral"

    return {
        "pair": pair_key,
        "current_price": round(price, 5),
        "max_pain": round(max_pain_strike["strike"], 5),
        "pc_sentiment": pc_sentiment,
        "put_call_ratio_oi": round(pc_oi_ratio, 3),
        "put_call_ratio_vol": round(pc_vol_ratio, 3),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "supports": supports,
        "resistances": resistances,
        "chain": chain,
    }


def get_cme_levels_all(prices):
    """Get detailed CME option chain levels for all pairs."""
    levels = {}
    for pair_key in PAIRS:
        try:
            price = prices.get(pair_key, {}).get("bid", 1.0)
            levels[pair_key] = get_cme_levels(pair_key, price)
        except Exception as e:
            levels[pair_key] = {"pair": pair_key, "error": str(e)}
    return levels


def get_all_cme_signals(prices):
    signals = {}
    for pair_key in PAIRS:
        try:
            price = prices.get(pair_key, {}).get("bid", 1.0)
            signals[pair_key] = get_cme_signal(pair_key, price)
        except Exception as e:
            signals[pair_key] = {"score": 50, "direction": "NEUTRAL", "error": str(e)}
    return signals
