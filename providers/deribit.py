"""
╔══════════════════════════════════════════════════════════╗
║          Deribit Options Provider — Real Data           ║
╠══════════════════════════════════════════════════════════╣
║  Fetches real-time option chain data from Deribit's     ║
║  free public API for BTC and ETH.                       ║
║  Returns structured data matching the CME provider      ║
║  format for drop-in replacement of simulated data.      ║
║                                                          ║
║  No API key required for public market data.             ║
║  Public endpoints: get_book_summary_by_currency,         ║
║                    get_instruments, get_ticker           ║
╚══════════════════════════════════════════════════════════╝
"""
import time
import threading
import requests
from datetime import datetime

_BASE_URL = "https://www.deribit.com/api/v2/public"

# ── Cache (thread-safe) ────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()

# Deribit instrument_name format: BTC-28AUG26-59000-P
# We'll map Deribit currencies to our pair keys
_DERIBIT_CURRENCIES = {
    "BTCUSD": {"currency": "BTC", "pair": "BTCUSD", "step": 100, "precision": 2},
    "ETHUSD": {"currency": "ETH", "pair": "ETHUSD", "step": 10, "precision": 2},
}


def _map_option_type(instrument_name):
    """Deribit instrument names end with -C or -P."""
    parts = instrument_name.split("-")
    if len(parts) >= 4:
        suffix = parts[-1]
        return "call" if suffix == "C" else "put"
    return None


def _parse_strike(instrument_name):
    """Extract strike price from Deribit instrument name like BTC-28AUG26-59000-P."""
    parts = instrument_name.split("-")
    if len(parts) >= 4:
        try:
            return float(parts[-2])
        except (ValueError, IndexError):
            return None
    return None


def _cached_get(url, ttl=30):
    """Thread-safe cached GET request."""
    with _cache_lock:
        if url in _cache and time.time() - _cache[url][0] < ttl:
            return _cache[url][1]

    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("error"):
            print(f"  ⚠️  Deribit API error for {url}: {data['error']}")
            with _cache_lock:
                _cache[url] = (time.time(), None)
            return None
        result = data.get("result")
        with _cache_lock:
            _cache[url] = (time.time(), result)
        return result
    except Exception as e:
        print(f"  ⚠️  Deribit request failed: {e}")
        with _cache_lock:
            _cache[url] = (time.time(), None)
        return None


def get_option_chain(pair_key, current_price=None):
    """
    Fetch real option chain data from Deribit for BTC or ETH.
    
    Returns a dict matching the CME provider format:
    {
        "pair": "BTCUSD",
        "current_price": 65000.0,
        "chain": [ { strike, call_oi, put_oi, call_volume, put_volume, ... } ],
        "supports": [...],
        "resistances": [...],
        "total_call_oi": int,
        "total_put_oi": int,
        "total_call_volume": int,
        "total_put_volume": int,
        "put_call_ratio_oi": float,
        "put_call_ratio_vol": float,
        "pc_sentiment": str,
        "max_pain": float,
        "data_source": "deribit",
    }
    
    Returns None if the pair is not available on Deribit.
    """
    info = _DERIBIT_CURRENCIES.get(pair_key)
    if not info:
        return None  # Not available on Deribit

    currency = info["currency"]

    # Fetch book summary (has OI, volume, IV for each instrument)
    summary_url = f"{_BASE_URL}/get_book_summary_by_currency?currency={currency}&kind=option"
    summary_data = _cached_get(summary_url, ttl=30)
    if not summary_data:
        return None

    # Parse instrument names to group by strike
    strikes = {}  # strike -> { call_oi, put_oi, call_vol, put_vol, ivs }
    underlying_price = None

    for item in summary_data:
        instr = item.get("instrument_name", "")
        opt_type = _map_option_type(instr)
        strike = _parse_strike(instr)
        if strike is None or opt_type is None:
            continue

        oi = float(item.get("open_interest", 0))
        vol = float(item.get("volume", 0))
        iv = item.get("mark_iv")
        underlying = item.get("underlying_price")

        if underlying and not underlying_price:
            underlying_price = float(underlying)

        if strike not in strikes:
            strikes[strike] = {
                "call_oi": 0.0, "put_oi": 0.0,
                "call_volume": 0.0, "put_volume": 0.0,
                "ivs": [],
            }

        s = strikes[strike]
        if opt_type == "call":
            s["call_oi"] += oi
            s["call_volume"] += vol
        else:
            s["put_oi"] += oi
            s["put_volume"] += vol
        if iv is not None:
            s["ivs"].append(float(iv))

    # Use provided current_price or underlying price
    price = float(current_price) if current_price else (underlying_price or 1.0)

    # Build chain (only include active strikes)
    chain = []
    for strike, s in sorted(strikes.items()):
        call_oi = int(s["call_oi"])
        put_oi = int(s["put_oi"])
        call_vol = int(s["call_volume"])
        put_vol = int(s["put_volume"])
        total_oi = call_oi + put_oi
        total_vol = call_vol + put_vol
        avg_iv = sum(s["ivs"]) / len(s["ivs"]) if s["ivs"] else 0
        dist_pct = abs(strike - price) / price * 100 if price > 0 else 0
        pc_ratio = round(put_oi / call_oi, 2) if call_oi > 0 else 99.99

        # Simplified Greeks
        moneyness = (strike - price) / price
        delta_call = 1 / (1 + 2.71828 ** (-moneyness * 20))
        delta_put = delta_call - 1
        gamma = 2.71828 ** (-(moneyness ** 2) * 100) * 0.05

        chain.append({
            "strike": round(strike, info["precision"]),
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "total_oi": total_oi,
            "total_volume": total_vol,
            "pc_ratio": pc_ratio,
            "iv": round(avg_iv, 1),
            "delta_call": round(delta_call, 3),
            "delta_put": round(delta_put, 3),
            "gamma": round(gamma, 4),
            "theta": 0,  # Not available from Deribit public API
            "distance_pct": round(dist_pct, 2),
        })

    if not chain:
        return None

    # Calculate aggregated metrics
    total_call_oi = sum(c["call_oi"] for c in chain)
    total_put_oi = sum(c["put_oi"] for c in chain)
    total_call_vol = sum(c["call_volume"] for c in chain)
    total_put_vol = sum(c["put_volume"] for c in chain)
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else 1.0
    pc_sentiment = "bullish" if pc_oi_ratio < 0.85 else "bearish" if pc_oi_ratio > 1.15 else "neutral"

    # Max pain: strike with highest total OI
    max_pain_strike = max(chain, key=lambda c: c["total_oi"])

    # Find key support/resistance levels (high OI concentration)
    max_oi = max(c["total_oi"] for c in chain) if chain else 0
    oi_threshold = max_oi * 0.6
    high_oi = [c for c in chain if c["total_oi"] >= oi_threshold]

    supports = []
    resistances = []
    for c in high_oi:
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
        if c["strike"] < price:
            supports.append(level)
        elif c["strike"] > price:
            resistances.append(level)

    supports.sort(key=lambda x: x["price"], reverse=True)
    resistances.sort(key=lambda x: x["price"])

    return {
        "pair": pair_key,
        "current_price": round(price, info["precision"]),
        "max_pain": round(max_pain_strike["strike"], info["precision"]),
        "pc_sentiment": pc_sentiment,
        "put_call_ratio_oi": round(pc_oi_ratio, 3),
        "put_call_ratio_vol": round(pc_vol_ratio, 3),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
        "supports": supports[:5],
        "resistances": resistances[:5],
        "chain": chain,
        "data_source": "deribit",
        "updated": datetime.now().strftime("%H:%M:%S"),
    }


def get_signal_from_chain(pair_key, chain_data):
    """
    Generate a directional signal (0-100) from real option chain data.
    Uses: put/call ratio, volume sentiment, max pain proximity.
    """
    if not chain_data:
        return {"score": 50, "direction": "NEUTRAL", "data_source": "simulated"}

    price = chain_data.get("current_price", 0)
    pc_oi = chain_data.get("put_call_ratio_oi", 1.0)
    pc_vol = chain_data.get("put_call_ratio_vol", 1.0)
    max_pain = chain_data.get("max_pain", price)
    total_call_oi = chain_data.get("total_call_oi", 0)
    total_put_oi = chain_data.get("total_put_oi", 0)
    total_call_vol = chain_data.get("total_call_volume", 0)
    total_put_vol = chain_data.get("total_put_volume", 0)

    score = 50  # Neutral start

    # P/C OI ratio signal (low P/C = bullish, high P/C = bearish)
    if pc_oi < 0.70:
        score += 20
    elif pc_oi < 0.85:
        score += 10
    elif pc_oi > 1.30:
        score -= 20
    elif pc_oi > 1.15:
        score -= 10

    # Volume sentiment
    total_vol = total_call_vol + total_put_vol
    if total_vol > 0:
        call_vol_pct = total_call_vol / total_vol * 100
        if call_vol_pct > 65:
            score += 10
        elif call_vol_pct < 35:
            score -= 10

    # Max pain proximity (price near max pain = neutral expectation)
    if price > 0:
        pain_dist = abs(price - max_pain) / price * 100
        if pain_dist > 5:
            # Price far from max pain = directional bias
            if price > max_pain:
                score -= 5  # Above max pain = bearish
            else:
                score += 5  # Below max pain = bullish

    score = max(0, min(100, score))
    direction = "BUY" if score >= 60 else "SELL" if score <= 40 else "NEUTRAL"

    return {
        "score": round(score, 0),
        "direction": direction,
        "data_source": "deribit",
    }
