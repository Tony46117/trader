"""News Engine — Processes Forex Factory news data and generates buy/sell direction signals.

For each high/medium impact event, we analyze:
- Actual vs Forecast vs Previous
- Market expectations (deviation from forecast)
- Historical impact patterns
- Pair-specific relevance scoring
"""

import csv
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict

from config import NEWS_DIR, PAIRS

# ── News → Pair mapping ──────────────────────────────────────────────
# Maps currency to affected trading pairs
CURRENCY_PAIRS = {
    "USD": ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "ETHUSD"],
    "EUR": ["EURUSD"],
    "GBP": ["GBPUSD"],
    "XAU": ["XAUUSD"],
    "BTC": ["BTCUSD"],
    "ETH": ["ETHUSD"],
}

# ── News relevance scoring ──────────────────────────────────────────
HIGH_IMPACT_KEYWORDS = {
    "USD": [
        "FOMC", "Non-Farm", "Employment", "CPI", "GDP", "Federal Funds Rate",
        "Interest Rate Decision", "Retail Sales", "Initial Claims", "ISM",
        "PPI", "Consumer Confidence", "Existing Home Sales", "New Home Sales",
        "Durable Goods", "Industrial Production", "Philadelphia Fed",
    ],
    "EUR": [
        "ECB", "Interest Rate Decision", "CPI", "GDP", "Employment Change",
        "Industrial Production", "Retail Sales", "German", "ZEW", "Sentix",
        "Trade Balance", "Current Account",
    ],
    "GBP": [
        "BOE", "Interest Rate Decision", "CPI", "GDP", "Employment Change",
        "Retail Sales", "Industrial Production", "Claimant Count", "ILO",
        "Average Earnings", "Services PMI", "Manufacturing PMI",
    ],
}

# Keywords that indicate market expectations direction
BULLISH_KEYWORDS = ["above", "exceeds", "higher", "strong", "expansion", "increase", "surplus", "surplus"]
BEARISH_KEYWORDS = ["below", "misses", "lower", "weak", "contraction", "decrease", "deficit", "shortfall"]


def load_news_data(currency="USD"):
    """Load news CSV data for a specific currency."""
    filepath = os.path.join(NEWS_DIR, f"forex_factory_{currency.lower()}_news_2025_2026.csv")
    if not os.path.exists(filepath):
        # Try alternate locations
        alt_paths = [
            f"/home/muchacho/Desktop/forex_factory_{currency.lower()}_news_2025_2026.csv",
            f"/home/muchacho/Documents/forex_factory_{currency.lower()}_news_2025_2026.csv",
        ]
        for ap in alt_paths:
            if os.path.exists(ap):
                filepath = ap
                break

    if not os.path.exists(filepath):
        return []

    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_upcoming_events(currency="USD", hours_ahead=48):
    """Get upcoming high/medium impact events within a time window."""
    rows = load_news_data(currency)
    now = datetime.now()
    upcoming = []

    for row in rows:
        try:
            date_str = row.get("Date", "")
            time_str = row.get("Time", "")

            # Parse date
            event_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
            if not event_date:
                continue

            # Parse time (handle formats like "12:30am", "8:30am", "All Day")
            time_lower = time_str.lower().strip()
            if "all day" in time_lower or "day" in time_lower:
                event_datetime = event_date.replace(hour=12, minute=0)
            else:
                try:
                    # Handle 12-hour format
                    is_pm = "pm" in time_lower
                    is_am = "am" in time_lower
                    time_clean = time_lower.replace("am", "").replace("pm", "").strip()
                    parts = time_clean.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0

                    if is_pm and hour != 12:
                        hour += 12
                    elif is_am and hour == 12:
                        hour = 0

                    event_datetime = event_date.replace(hour=hour, minute=minute)
                except (ValueError, IndexError):
                    event_datetime = event_date.replace(hour=12, minute=0)

            # Check if within window
            if event_datetime < now - timedelta(hours=2):
                continue
            if event_datetime > now + timedelta(hours=hours_ahead):
                continue

            # Determine impact level
            impact = row.get("Impact", "")
            if "High" not in impact and "Medium" not in impact and "Red" not in impact and "Orange" not in impact:
                continue

            # Determine status (before, during, or after release)
            if event_datetime > now:
                status = "upcoming"
            elif abs((event_datetime - now).total_seconds()) < 7200:  # within 2 hours
                status = "live"
            else:
                status = "recent"

            # Generate buy/sell direction signal
            direction, confidence, reasoning = analyze_news_event(row, currency)

            upcoming.append({
                "date": date_str,
                "time": time_str,
                "datetime": event_datetime.strftime("%Y-%m-%d %H:%M"),
                "currency": row.get("Currency", currency),
                "impact": impact,
                "event": row.get("Event", ""),
                "actual": row.get("Actual", ""),
                "forecast": row.get("Forecast", ""),
                "previous": row.get("Previous", ""),
                "status": status,
                "direction": direction,
                "confidence": confidence,
                "reasoning": reasoning,
                "affected_pairs": CURRENCY_PAIRS.get(currency, []),
                "timestamp": int(event_datetime.timestamp()),
            })

        except Exception as e:
            continue

    # Sort by datetime
    upcoming.sort(key=lambda x: x["timestamp"])
    return upcoming


def analyze_news_event(row, currency):
    """Analyze a news event and determine buy/sell direction.

    Uses Actual vs Forecast deviation, previous values, and event type.
    """
    actual = row.get("Actual", "").strip()
    forecast = row.get("Forecast", "").strip()
    previous = row.get("Previous", "").strip()
    event_name = row.get("Event", "").strip()
    impact = row.get("Impact", "")

    is_high = "red" in impact.lower() or "high" in impact.lower()

    # If no actual data yet (upcoming event)
    if not actual or actual == "-":
        # Use event type to determine bias
        if is_high:
            confidence = "high"
        else:
            confidence = "medium"

        # Determine bias from event type
        event_lower = event_name.lower()

        # Inflation-related events
        if any(w in event_lower for w in ["cpi", "inflation", "ppi", "core", "price index"]):
            # Higher inflation = rate hikes = generally bullish for currency
            return "bullish", confidence, "Inflation data — higher readings typically bullish for currency. Monitor release."

        # Employment-related
        if any(w in event_lower for w in ["non-farm", "employment", "jobless", "payroll", "unemployment"]):
            return "mixed", confidence, "Employment data — strong jobs = bullish for currency. Watch NFP specifically."

        # Central bank
        if any(w in event_lower for w in ["fomc", "fed", "ecb", "boe", "interest rate", "monetary policy"]):
            return "mixed", confidence, "Central bank decision — watch rate change and forward guidance."

        # GDP
        if "gdp" in event_lower:
            return "bullish", confidence, "GDP data — stronger economy = bullish for currency."

        # Retail
        if "retail" in event_lower:
            return "bullish", confidence, "Consumer spending — higher retail = bullish for currency."

        # Confidence / sentiment
        if any(w in event_lower for w in ["confidence", "sentiment", "sentix", "zew"]):
            return "bullish", confidence, "Confidence data — improving sentiment = bullish tailwind."

        # Trade
        if any(w in event_lower for w in ["trade", "current account"]):
            return "mixed", confidence, "Trade data — surplus = bullish, deficit = bearish."

        # Housing
        if any(w in event_lower for w in ["housing", "home"]):
            return "mixed", confidence, "Housing data — strong housing market = bullish economic signal."

        # Manufacturing / Industrial
        if any(w in event_lower for w in ["manufacturing", "industrial", "ism", "production"]):
            return "mixed", confidence, "Industrial data — expansion = bullish, contraction = bearish."

        return "mixed", "low", "Event pending — wait for release for direction signal."

    # We have actual data — compare with forecast
    try:
        # Try to extract numeric values
        actual_val = parse_numeric(actual)
        forecast_val = parse_numeric(forecast) if forecast and forecast != "-" else None
        previous_val = parse_numeric(previous) if previous and previous != "-" else None

        if actual_val is not None and forecast_val is not None:
            deviation = ((actual_val - forecast_val) / abs(forecast_val)) * 100 if forecast_val != 0 else 0

            # Determine direction based on event type
            event_lower = event_name.lower()

            # For most economic indicators, higher than forecast = bullish
            higher_is_bullish = True
            if any(w in event_lower for w in ["unemployment", "jobless", "claims"]):
                higher_is_bullish = False  # Higher unemployment = bearish
            if any(w in event_lower for w in ["stock"]):
                higher_is_bullish = True

            if higher_is_bullish:
                if deviation > 2:
                    direction = "bullish"
                    reasoning = f"Actual ({actual}) significantly exceeded forecast ({forecast}) by {deviation:.1f}%"
                elif deviation < -2:
                    direction = "bearish"
                    reasoning = f"Actual ({actual}) missed forecast ({forecast}) by {abs(deviation):.1f}%"
                else:
                    direction = "mixed"
                    reasoning = f"Actual ({actual}) close to forecast ({forecast}) — {abs(deviation):.1f}% deviation"
            else:
                if deviation < -2:
                    direction = "bullish"
                    reasoning = f"Unemployment/claims lower than forecast — bullish signal"
                elif deviation > 2:
                    direction = "bearish"
                    reasoning = f"Unemployment/claims higher than forecast — bearish signal"
                else:
                    direction = "mixed"
                    reasoning = f"Actual ({actual}) in line with expectations ({forecast})"

            confidence = "high" if abs(deviation) > 5 else "medium"
            return direction, confidence, reasoning

    except (ValueError, TypeError):
        pass

    # Fallback: check if actual beats previous
    if previous and previous != "-":
        return "mixed", "low", f"Actual: {actual}, Previous: {previous}. Impact depends on context."

    return "mixed", "low", "Release occurred — monitor price action for market reaction."


def parse_numeric(value):
    """Parse numeric value from string, handling K/B/M suffixes."""
    if not value:
        return None
    value = value.strip().replace(",", "").replace("%", "").replace("$", "").replace("€", "£", "")
    value = value.replace("−", "-").replace("+", "").strip()

    try:
        if "K" in value:
            return float(value.replace("K", "")) * 1000
        elif "M" in value:
            return float(value.replace("M", "")) * 1000000
        elif "B" in value:
            return float(value.replace("B", "")) * 1000000000
        elif "T" in value:
            return float(value.replace("T", "")) * 1000000000000
        else:
            return float(value)
    except ValueError:
        return None


def get_all_upcoming_events(hours_ahead=72):
    """Get upcoming events for all currencies."""
    all_events = []
    for currency in ["USD", "EUR", "GBP"]:
        try:
            events = get_upcoming_events(currency, hours_ahead)
            all_events.extend(events)
        except Exception as e:
            print(f"⚠️ News load error for {currency}: {e}")
            continue

    # Sort by timestamp
    all_events.sort(key=lambda x: x["timestamp"])
    return all_events


def get_news_summary():
    """Get summary statistics for news calendar."""
    currencies = ["USD", "EUR", "GBP"]
    summary = {}

    for currency in currencies:
        rows = load_news_data(currency)
        total = len(rows)
        high = sum(1 for r in rows if "red" in r.get("Impact", "").lower() or "high" in r.get("Impact", "").lower())
        medium = sum(1 for r in rows if "orange" in r.get("Impact", "").lower() or "medium" in r.get("Impact", "").lower())

        # Upcoming in next 24h
        upcoming_24h = get_upcoming_events(currency, hours_ahead=24)

        summary[currency] = {
            "total": total,
            "high": high,
            "medium": medium,
            "upcoming_24h": len(upcoming_24h),
        }

    return summary


# ── Per-Pair News Signal Aggregation ─────────────────────────────────

def get_news_signal_for_pair(pair_key):
    """Aggregate news events affecting a specific pair and generate a news signal score 0-100.

    0 = strong SELL from news, 50 = neutral, 100 = strong BUY from news.
    Uses upcoming/recent high & medium impact events weighted by:
    - Impact level (high > medium)
    - Timing (live > upcoming > recent)
    - Direction confidence
    """
    # Determine which currencies affect this pair
    affecting_currencies = []
    for currency, pairs in CURRENCY_PAIRS.items():
        if pair_key in pairs:
            affecting_currencies.append(currency)

    if not affecting_currencies:
        return {
            "score": 50,
            "direction": "NEUTRAL",
            "events_analyzed": 0,
            "details": [],
            "note": f"No news data tracked for {pair_key}",
        }

    # Collect all relevant upcoming/recent events
    all_relevant = []
    for currency in affecting_currencies:
        try:
            events = get_upcoming_events(currency, hours_ahead=168)  # 7 days
            for event in events:
                all_relevant.append(event)
        except Exception:
            continue

    if not all_relevant:
        return {
            "score": 50,
            "direction": "NEUTRAL",
            "events_analyzed": 0,
            "details": [],
            "note": f"No upcoming news affecting {pair_key}",
        }

    # Score each event
    buy_weight = 0.0
    sell_weight = 0.0
    total_weight = 0.0
    details = []

    for event in all_relevant:
        # Base weight by impact
        is_high = "high" in event.get("impact", "").lower() or "red" in event.get("impact", "").lower()
        base_weight = 3.0 if is_high else 1.5

        # Timing multiplier
        status = event.get("status", "upcoming")
        if status == "live":
            timing_mult = 2.0
        elif status == "upcoming":
            timing_mult = 1.0
        else:
            timing_mult = 0.5

        # Direction and confidence
        direction = event.get("direction", "mixed")
        confidence = event.get("confidence", "low")
        conf_mult = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(confidence, 0.3)

        weight = base_weight * timing_mult
        weighted_val = weight * conf_mult
        total_weight += weight

        if direction == "bullish":
            buy_weight += weighted_val
        elif direction == "bearish":
            sell_weight += weighted_val
        else:
            # Mixed — split evenly
            buy_weight += weighted_val * 0.5
            sell_weight += weighted_val * 0.5

        details.append({
            "event": event.get("event", ""),
            "currency": event.get("currency", ""),
            "impact": event.get("impact", ""),
            "direction": direction,
            "confidence": confidence,
            "weight": round(weight, 1),
            "datetime": event.get("datetime", ""),
        })

    # Calculate score 0-100
    if total_weight > 0:
        buy_norm = buy_weight / total_weight
        sell_norm = sell_weight / total_weight
        raw_score = (buy_norm / (buy_norm + sell_norm)) * 100 if (buy_norm + sell_norm) > 0 else 50
    else:
        raw_score = 50

    score = max(0, min(100, raw_score))

    if score >= 60:
        direction = "BUY"
    elif score <= 40:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    # Sort details by weight (most important first)
    details.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "score": round(score, 0),
        "direction": direction,
        "events_analyzed": len(details),
        "details": details[:5],  # Top 5 most impactful
        "note": f"{len(details)} events analyzed for {pair_key}" if details else f"No news for {pair_key}",
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
