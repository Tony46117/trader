"""
╔══════════════════════════════════════════════════════════╗
║          News Provider — Economic Calendar              ║
╠══════════════════════════════════════════════════════════╣
║  Generates simulated economic events with realistic     ║
║  impact scoring, timing, and directional signals.       ║
║  Integrates with the 5-source fusion signal engine.     ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
import random
from datetime import datetime, timedelta
from collections import defaultdict

from config import PAIRS

# ── Currency → Pair Mapping ─────────────────────────────────────────
CURRENCY_PAIRS = {
    "USD": ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "ETHUSD"],
    "EUR": ["EURUSD"],
    "GBP": ["GBPUSD"],
    "XAU": ["XAUUSD"],
    "BTC": ["BTCUSD"],
    "ETH": ["ETHUSD"],
}

# ── Economic Event Templates ────────────────────────────────────────
EVENT_TEMPLATES = {
    "USD": [
        {"event": "FOMC Interest Rate Decision",    "impact": "HIGH",   "bias": "mixed"},
        {"event": "Non-Farm Employment Change",     "impact": "HIGH",   "bias": "bullish"},
        {"event": "CPI (YoY)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "GDP (QoQ)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "Initial Jobless Claims",          "impact": "HIGH",   "bias": "mixed"},
        {"event": "Retail Sales (MoM)",              "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Industrial Production (MoM)",     "impact": "MEDIUM", "bias": "bullish"},
        {"event": "ISM Manufacturing PMI",           "impact": "HIGH",   "bias": "bullish"},
        {"event": "ISM Services PMI",                "impact": "HIGH",   "bias": "bullish"},
        {"event": "Fed Chair Speech",                "impact": "HIGH",   "bias": "mixed"},
        {"event": "PPI (MoM)",                       "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Consumer Confidence",             "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Durable Goods Orders",            "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Existing Home Sales",             "impact": "LOW",    "bias": "mixed"},
        {"event": "New Home Sales",                  "impact": "LOW",    "bias": "mixed"},
        {"event": "Philadelphia Fed Index",          "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Building Permits",                "impact": "LOW",    "bias": "mixed"},
        {"event": "Trade Balance",                   "impact": "MEDIUM", "bias": "mixed"},
        {"event": "Wholesale Inventories",           "impact": "LOW",    "bias": "mixed"},
        {"event": "Michigan Consumer Sentiment",     "impact": "MEDIUM", "bias": "bullish"},
    ],
    "EUR": [
        {"event": "ECB Interest Rate Decision",      "impact": "HIGH",   "bias": "mixed"},
        {"event": "CPI (YoY)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "GDP (QoQ)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "Employment Change",               "impact": "HIGH",   "bias": "bullish"},
        {"event": "Industrial Production (MoM)",     "impact": "MEDIUM", "bias": "bullish"},
        {"event": "German ZEW Economic Sentiment",   "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Retail Sales (MoM)",              "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Trade Balance",                   "impact": "MEDIUM", "bias": "mixed"},
        {"event": "Current Account",                 "impact": "MEDIUM", "bias": "mixed"},
        {"event": "Consumer Confidence",             "impact": "LOW",    "bias": "bullish"},
        {"event": "ECB President Speech",            "impact": "HIGH",   "bias": "mixed"},
        {"event": "German CPI (MoM)",                "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Sentix Investor Confidence",      "impact": "LOW",    "bias": "bullish"},
    ],
    "GBP": [
        {"event": "BOE Interest Rate Decision",      "impact": "HIGH",   "bias": "mixed"},
        {"event": "CPI (YoY)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "GDP (MoM)",                      "impact": "HIGH",   "bias": "bullish"},
        {"event": "Employment Change (3M/3M)",       "impact": "HIGH",   "bias": "bullish"},
        {"event": "Retail Sales (MoM)",              "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Industrial Production (MoM)",     "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Claimant Count Change",           "impact": "MEDIUM", "bias": "mixed"},
        {"event": "Average Earnings (3M/YoY)",       "impact": "MEDIUM", "bias": "bullish"},
        {"event": "BOE MPC Meeting Minutes",        "impact": "HIGH",   "bias": "mixed"},
        {"event": "Services PMI",                    "impact": "MEDIUM", "bias": "bullish"},
        {"event": "Manufacturing PMI",               "impact": "MEDIUM", "bias": "bullish"},
        {"event": "GfK Consumer Confidence",         "impact": "LOW",    "bias": "bullish"},
        {"event": "BOE Gov Speech",                  "impact": "HIGH",   "bias": "mixed"},
    ],
}


def _generate_events_for_currency(currency, hours_ahead=72):
    """Generate simulated upcoming economic events for a currency."""
    templates = EVENT_TEMPLATES.get(currency, [])
    now = datetime.now()
    events = []
    used_hours = set()

    # Generate 2-5 events per currency in the window
    num_events = random.randint(2, 5)
    templates_sample = random.sample(templates, min(num_events, len(templates)))

    for template in templates_sample:
        # Pick a random hour in the next 72h (avoiding duplicates)
        attempt = 0
        hour_offset = None
        while attempt < 20:
            h = random.randint(2, hours_ahead)
            if h not in used_hours:
                hour_offset = h
                used_hours.add(h)
                break
            attempt += 1

        if hour_offset is None:
            continue

        event_time = now + timedelta(hours=hour_offset)
        # Round to nearest half hour
        mins = event_time.minute
        rounded_mins = 0 if mins < 15 else 30
        event_time = event_time.replace(minute=rounded_mins, second=0, microsecond=0)

        # Generate actual/forecast/previous data
        is_upcoming = event_time > now + timedelta(hours=1)

        impact = template["impact"]
        base_bias = template["bias"]

        # Simulate actual vs forecast
        if is_upcoming:
            direction = base_bias
            actual = "-"
            if base_bias == "bullish":
                forecast = round(np.random.uniform(0.1, 3.0), 1)
                previous = round(np.random.uniform(0.05, 2.5), 1)
            elif base_bias == "bearish":
                forecast = round(np.random.uniform(-3.0, -0.1), 1)
                previous = round(np.random.uniform(-2.5, -0.05), 1)
            else:
                forecast = round(np.random.uniform(-1.0, 1.0), 1)
                previous = round(np.random.uniform(-1.0, 1.0), 1)
            confidence = "high" if impact == "HIGH" else "medium"
            reasoning = f"{template['event']} — {impact} impact event. {base_bias.capitalize()} bias expected."
        else:
            # Generate data as if it was just released
            deviation = np.random.normal(0, 0.5)
            forecast = round(np.random.uniform(-1.0, 3.0), 1)
            actual = round(forecast + deviation, 1)
            previous = round(np.random.uniform(-1.5, 2.5), 1)

            if base_bias == "bullish":
                if actual > forecast:
                    direction = "bullish"
                    reasoning = f"Actual ({actual}) exceeded forecast ({forecast}) — bullish release"
                else:
                    direction = "bearish"
                    reasoning = f"Actual ({actual}) missed forecast ({forecast}) — bearish miss"
            elif base_bias == "bearish":
                if actual < forecast:
                    direction = "bearish"
                    reasoning = f"Actual ({actual}) below forecast ({forecast}) — bearish"
                else:
                    direction = "bullish"
                    reasoning = f"Actual ({actual}) above forecast ({forecast}) — bullish beat"
            else:
                direction = "mixed"
                reasoning = f"Actual ({actual}) vs forecast ({forecast}) — mixed impact"

            confidence = "high" if abs(deviation) > 1.0 else "medium"

        status = "upcoming" if is_upcoming else "live" if abs((event_time - now).total_seconds()) < 7200 else "recent"

        events.append({
            "date": event_time.strftime("%Y-%m-%d"),
            "time": event_time.strftime("%H:%M"),
            "datetime": event_time.strftime("%Y-%m-%d %H:%M"),
            "currency": currency,
            "impact": impact,
            "event": template["event"],
            "actual": str(actual),
            "forecast": str(forecast),
            "previous": str(previous),
            "status": status,
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "affected_pairs": CURRENCY_PAIRS.get(currency, []),
            "timestamp": int(event_time.timestamp()),
        })

    return events


def get_upcoming_events(hours_ahead=72):
    """Get upcoming economic events for all currencies."""
    all_events = []
    for currency in ["USD", "EUR", "GBP"]:
        try:
            events = _generate_events_for_currency(currency, hours_ahead)
            all_events.extend(events)
        except Exception:
            continue

    all_events.sort(key=lambda x: x["timestamp"])
    return all_events


def get_all_news(hours_past=24, hours_ahead=168):
    """Get ALL economic events — recent past + upcoming — for the full News page.

    Includes actual/forecast/previous values for every event.
    """
    all_events = []
    for currency in ["USD", "EUR", "GBP"]:
        try:
            events = _generate_events_for_currency(currency, hours_ahead)
            all_events.extend(events)
        except Exception:
            continue

    # Also generate a few released events (past)
    for currency in ["USD", "EUR", "GBP"]:
        try:
            past_events = _generate_past_events(currency, hours_past)
            all_events.extend(past_events)
        except Exception:
            continue

    all_events.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_events


def _generate_past_events(currency, hours_past=24):
    """Generate recently released events with actual data."""
    templates = EVENT_TEMPLATES.get(currency, [])
    now = datetime.now()
    events = []
    used_hours = set()

    num_events = random.randint(3, 6)
    templates_sample = random.sample(templates, min(num_events, len(templates)))

    for template in templates_sample:
        attempt = 0
        hour_offset = None
        while attempt < 20:
            h = random.randint(-hours_past, -1)
            if h not in used_hours:
                hour_offset = h
                used_hours.add(h)
                break
            attempt += 1

        if hour_offset is None:
            continue

        event_time = now + timedelta(hours=hour_offset)
        mins = event_time.minute
        rounded_mins = 0 if mins < 15 else 30
        event_time = event_time.replace(minute=rounded_mins, second=0, microsecond=0)

        impact = template["impact"]
        base_bias = template["bias"]

        # Generate data as if it was just released
        deviation = np.random.normal(0, 0.5)
        forecast = round(np.random.uniform(-1.0, 3.0), 1)
        actual = round(forecast + deviation, 1)
        previous = round(np.random.uniform(-1.5, 2.5), 1)

        if base_bias == "bullish":
            if actual > forecast:
                direction = "bullish"
                reasoning = f"Actual ({actual}) exceeded forecast ({forecast}) — bullish release"
            else:
                direction = "bearish"
                reasoning = f"Actual ({actual}) missed forecast ({forecast}) — bearish miss"
        elif base_bias == "bearish":
            if actual < forecast:
                direction = "bearish"
                reasoning = f"Actual ({actual}) below forecast ({forecast}) — bearish"
            else:
                direction = "bullish"
                reasoning = f"Actual ({actual}) above forecast ({forecast}) — bullish beat"
        else:
            direction = "mixed"
            reasoning = f"Actual ({actual}) vs forecast ({forecast}) — mixed impact"

        confidence = "high" if abs(deviation) > 1.0 else "medium"
        status = "recent"

        events.append({
            "date": event_time.strftime("%Y-%m-%d"),
            "time": event_time.strftime("%H:%M"),
            "datetime": event_time.strftime("%Y-%m-%d %H:%M"),
            "currency": currency,
            "impact": impact,
            "event": template["event"],
            "actual": str(actual),
            "forecast": str(forecast),
            "previous": str(previous),
            "status": status,
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "affected_pairs": CURRENCY_PAIRS.get(currency, []),
            "timestamp": int(event_time.timestamp()),
        })

    return events


# ── Per-Pair News Signal ─────────────────────────────────────────────

def get_news_signal_for_pair(pair_key):
    """Generate a news signal (0-100) for a specific pair.

    0 = strong SELL from news, 50 = neutral, 100 = strong BUY.
    Weights high/medium impact events by timing and directional confidence.
    """
    # Determine which currencies affect this pair
    affecting_currencies = [
        currency for currency, pairs in CURRENCY_PAIRS.items()
        if pair_key in pairs
    ]
    if not affecting_currencies:
        return {"score": 50, "direction": "NEUTRAL", "events_analyzed": 0, "details": [],
                "note": f"No news tracked for {pair_key}"}

    # Collect relevant events
    all_relevant = []
    for currency in affecting_currencies:
        try:
            all_relevant.extend(_generate_events_for_currency(currency, hours_ahead=168))
        except Exception:
            continue

    if not all_relevant:
        return {"score": 50, "direction": "NEUTRAL", "events_analyzed": 0, "details": [],
                "note": f"No news for {pair_key}"}

    # Score each event
    buy_weight = 0.0
    sell_weight = 0.0
    total_weight = 0.0
    details = []

    for event in all_relevant:
        is_high = event["impact"] == "HIGH"
        base_weight = 3.0 if is_high else 1.5

        status = event["status"]
        timing_mult = 2.0 if status == "live" else 1.0 if status == "upcoming" else 0.5

        direction = event["direction"]
        conf_mult = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(event.get("confidence", "low"), 0.3)

        weight = base_weight * timing_mult
        weighted = weight * conf_mult
        total_weight += weight

        if direction == "bullish":
            buy_weight += weighted
        elif direction == "bearish":
            sell_weight += weighted
        else:
            buy_weight += weighted * 0.5
            sell_weight += weighted * 0.5

        details.append({
            "event": event["event"],
            "currency": event["currency"],
            "impact": event["impact"],
            "direction": direction,
            "confidence": event.get("confidence", "low"),
            "weight": round(weight, 1),
            "datetime": event["datetime"],
        })

    # Normalize to 0-100
    if total_weight > 0:
        bn = buy_weight / total_weight
        sn = sell_weight / total_weight
        raw = (bn / (bn + sn)) * 100 if (bn + sn) > 0 else 50
    else:
        raw = 50

    score = max(0, min(100, raw))
    direction = "BUY" if score >= 60 else "SELL" if score <= 40 else "NEUTRAL"

    details.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "score": round(score, 0),
        "direction": direction,
        "events_analyzed": len(details),
        "details": details[:5],
        "note": f"{len(details)} events for {pair_key}",
    }


def get_all_news_signals():
    """Get news signals for all trading pairs."""
    signals = {}
    for pair_key in PAIRS:
        try:
            signals[pair_key] = get_news_signal_for_pair(pair_key)
        except Exception as e:
            signals[pair_key] = {"score": 50, "direction": "NEUTRAL", "events_analyzed": 0, "details": [],
                                 "error": str(e)}
    return signals
