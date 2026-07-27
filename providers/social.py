"""
╔══════════════════════════════════════════════════════════╗
║          Social Sentiment Provider                      ║
╠══════════════════════════════════════════════════════════╣
║  Simulates social media sentiment analysis from         ║
║  Twitter/X, Truth Social, and Reddit.                   ║
║  Returns sentiment score 0-100 per pair.               ║
╚══════════════════════════════════════════════════════════╝
"""
import numpy as np
from datetime import datetime
from config import PAIRS

SENTIMENT_KEYWORDS = {
    "EURUSD": ["euro", "eur", "ecb", "eurozone", "german"],
    "GBPUSD": ["pound", "gbp", "boe", "uk economy", "brexit"],
    "XAUUSD": ["gold", "xau", "bullion", "gold price"],
    "BTCUSD": ["bitcoin", "btc", "crypto", "blockchain", "halving"],
    "ETHUSD": ["ethereum", "eth", "defi", "smart contract", "vitalik"],
}

INFLUENCER_ACCOUNTS = [
    "zerohedge", "reutersfx", "bloombergfx", "fxstreetnews",
    "forexfactory", "dailyfx", "tradertom",
]


def get_social_signal(pair_key):
    """Generate social media sentiment signal (0-100)."""
    pair = PAIRS.get(pair_key, {})
    pair_name = pair.get("name", pair_key)
    keywords = SENTIMENT_KEYWORDS.get(pair_key, [pair_key.lower()])

    seed = abs(hash(pair_key + datetime.now().strftime("%Y%m%d%H"))) % 2**32
    np.random.seed(seed)

    # Generate sentiment with slight bullish bias
    base_sentiment = np.random.uniform(-0.3, 0.4)
    mention_volume = int(np.random.exponential(50) + 10)

    # Influencer mentions
    influencer_count = sum(1 for _ in range(5) if np.random.random() < 0.3)
    influence_sentiment = np.random.uniform(-1, 1) * 0.5 if influencer_count > 0 else 0

    # Sample posts based on sentiment
    posts = []
    templates = {
        "bullish": [
            f"{pair_name} looking strong — technicals align!",
            f"Big opportunity on {pair_key}. Position sizing accordingly.",
            f"Accumulation phase on {pair_name}. Smart money flowing in.",
        ],
        "bearish": [
            f"Warning signs on {pair_key}. Distribution forming.",
            f"Exiting {pair_name} — risk/reward no longer favorable.",
            f"{pair_name} under selling pressure. Support levels critical.",
        ],
        "neutral": [
            f"{pair_key} ranging. Waiting for catalyst.",
            f"Monitoring {pair_name} at key level. Need confirmation.",
            f"Volatility compression on {pair_key}. Expecting breakout soon.",
        ],
    }

    for _ in range(min(mention_volume, 4)):
        if base_sentiment > 0.1:
            t = np.random.choice(templates["bullish"])
        elif base_sentiment < -0.1:
            t = np.random.choice(templates["bearish"])
        else:
            t = np.random.choice(templates["neutral"])
        posts.append({"text": t, "platform": np.random.choice(["twitter", "reddit", "truth"])})

    # Aggregate
    avg_sentiment = (base_sentiment + influence_sentiment) / 2
    sentiment_score = 50 + (avg_sentiment * 50)
    sentiment_score = max(0, min(100, sentiment_score))

    classification = "bullish" if avg_sentiment > 0.3 else "bearish" if avg_sentiment < -0.3 else "neutral"
    direction = "BUY" if sentiment_score >= 60 else "SELL" if sentiment_score <= 40 else "NEUTRAL"

    return {
        "score": round(sentiment_score, 0),
        "direction": direction,
        "classification": classification,
        "mention_volume": mention_volume,
        "influencer_mentions": influencer_count,
        "avg_sentiment": round(float(avg_sentiment), 3),
        "sample_posts": posts,
    }


def get_all_social_signals():
    signals = {}
    for pair_key in PAIRS:
        try:
            signals[pair_key] = get_social_signal(pair_key)
        except Exception as e:
            signals[pair_key] = {"score": 50, "direction": "NEUTRAL", "error": str(e)}
    return signals
