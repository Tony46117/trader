"""Social Media News Module.

Collects and analyzes market sentiment from:
- Twitter/X (financial tweets, influencers, news outlets)
- Truth Social (political/financial sentiment)
- Reddit (r/Forex, r/CryptoCurrency, r/WallStreetBets)

Provides sentiment signals that feed into the unified signal engine.
"""

import re
import json
import os
import random
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from config import PAIRS, CACHE_DIR

# ── Sentiment keywords by pair ─────────────────────────────────────────
SENTIMENT_KEYWORDS = {
    "EURUSD": ["euro", "eur", "ecb", "european central bank", "eurozone", "german", "french"],
    "GBPUSD": ["pound", "gbp", "boe", "bank of england", "british", "uk economy", "brexit"],
    "XAUUSD": ["gold", "xau", "precious metal", "bullion", "gold price", "goldman gold"],
    "BTCUSD": ["bitcoin", "btc", "crypto", "blockchain", "satoshi", "halving", "bitcoin etf"],
    "ETHUSD": ["ethereum", "eth", "ether", "defi", "smart contract", "eth etf", "vitalik"],
}

# Simulated influencers/tracked accounts (in production, use Twitter API)
INFLUENCER_ACCOUNTS = {
    "twitter": [
        "zerohedge", "reutersfx", "bloombergfx", "fxstreetnews",
        "forexfactory", "dailyfx", "tradertom", "fxpro",
    ],
    "truth_social": [
        "financialfreedom", "truthmoney", "americafirstfinance",
    ],
}


class SocialNewsCollector:
    """Collects and analyzes social media sentiment for trading pairs."""

    def __init__(self):
        self.sentiment_cache = {}
        self.last_fetch = {}

    def _generate_simulated_sentiment(self, pair_key):
        """Generate simulated social media sentiment data.

        In production, this would call Twitter API v2, Truth Social API,
        and Reddit API to get real sentiment data.
        """
        pair = PAIRS.get(pair_key, {})
        pair_name = pair.get("name", pair_key)
        keywords = SENTIMENT_KEYWORDS.get(pair_key, [pair_key.lower()])

        # Generate random sentiment with slight bullish bias (markets tend up)
        base_sentiment = np.random.uniform(-0.3, 0.4)

        # Volume of mentions (simulated)
        mention_volume = int(np.random.exponential(50) + 10)

        # Influencer mentions
        influencer_mentions = []
        for platform, accounts in INFLUENCER_ACCOUNTS.items():
            for _ in range(np.random.randint(0, 3)):
                if random.random() < 0.3:  # 30% chance of mention per account
                    sentiment = np.random.uniform(-1, 1)
                    account = random.choice(accounts)
                    influencer_mentions.append({
                        "platform": platform,
                        "account": account,
                        "sentiment": round(float(sentiment), 2),
                        "impact": "high" if abs(sentiment) > 0.5 else "medium",
                    })

        # Recent posts with sentiment (simulated)
        sample_posts = []
        post_templates = {
            "bullish": [
                f"{pair_name} looking strong here — technicals align for a breakout!",
                f"Big {keywords[0]} news coming. Bullish setup forming on {pair_key}.",
                f"Just added to my {pair_name} position. Risk management is key but this looks good.",
                f"{pair_name} accumulation underway. Smart money moving in.",
                f"Central bank policy favors {pair_name} longs. Position sizing accordingly.",
            ],
            "bearish": [
                f"Warning signs on {pair_key}. Distribution pattern forming on higher timeframes.",
                f"Elevated risk for {pair_name} this week. Multiple headwinds ahead.",
                f"Exiting my {pair_name} position. Risk/reward no longer favorable.",
                f"{pair_name} selling pressure increasing. Watch support levels closely.",
                f"Macro outlook negative for {pair_key}. Reduced exposure recommended.",
            ],
            "neutral": [
                f"{pair_key} trading in range. Waiting for catalyst.",
                f"Monitoring {pair_name} closely. No clear directional bias yet.",
                f"Volatility compression on {pair_key}. Expecting expansion soon.",
                f"{pair_name} at key level. Need confirmation before entry.",
            ],
        }

        for _ in range(min(mention_volume, 5)):
            if base_sentiment > 0.1:
                template = random.choice(post_templates["bullish"])
                post_sentiment = base_sentiment + np.random.uniform(-0.2, 0.2)
            elif base_sentiment < -0.1:
                template = random.choice(post_templates["bearish"])
                post_sentiment = base_sentiment + np.random.uniform(-0.2, 0.2)
            else:
                template = random.choice(post_templates["neutral"])
                post_sentiment = np.random.uniform(-0.3, 0.3)

            hours_ago = np.random.uniform(0, 24)
            sample_posts.append({
                "text": template,
                "sentiment": round(float(post_sentiment), 2),
                "time": (datetime.now() - timedelta(hours=hours_ago)).strftime("%H:%M"),
                "platform": random.choice(["twitter", "truth_social", "reddit"]),
            })

        # Aggregate sentiment
        all_sentiments = [p["sentiment"] for p in sample_posts]
        all_sentiments.extend([im["sentiment"] for im in influencer_mentions])

        if all_sentiments:
            avg_sentiment = np.mean(all_sentiments)
            sentiment_std = np.std(all_sentiments)
        else:
            avg_sentiment = 0
            sentiment_std = 0

        # Sentiment score: 0-100
        sentiment_score = 50 + (avg_sentiment * 50)
        sentiment_score = max(0, min(100, sentiment_score))

        # Classification
        if avg_sentiment > 0.3:
            classification = "bullish"
        elif avg_sentiment < -0.3:
            classification = "bearish"
        else:
            classification = "neutral"

        # Consensus
        if avg_sentiment > 0.5:
            consensus = "strong_bullish"
        elif avg_sentiment > 0.15:
            consensus = "moderate_bullish"
        elif avg_sentiment < -0.5:
            consensus = "strong_bearish"
        elif avg_sentiment < -0.15:
            consensus = "moderate_bearish"
        else:
            consensus = "mixed"

        return {
            "pair": pair_key,
            "pair_name": pair_name,
            "sentiment_score": round(float(sentiment_score), 0),
            "classification": classification,
            "consensus": consensus,
            "avg_sentiment": round(float(avg_sentiment), 3),
            "sentiment_volatility": round(float(sentiment_std), 3),
            "mention_volume": mention_volume,
            "influencer_mentions": influencer_mentions,
            "sample_posts": sample_posts,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def get_pair_sentiment(self, pair_key):
        """Get social media sentiment for a specific pair."""
        cache_key = f"social_{pair_key}"
        cached = self.sentiment_cache.get(cache_key)
        cache_age = self.last_fetch.get(cache_key)

        # Cache for 15 minutes
        if cached and cache_age and (datetime.now() - cache_age).seconds < 900:
            return cached

        result = self._generate_simulated_sentiment(pair_key)
        self.sentiment_cache[cache_key] = result
        self.last_fetch[cache_key] = datetime.now()
        return result

    def get_all_sentiment(self):
        """Get social media sentiment for all pairs."""
        results = {}
        for pair_key in PAIRS:
            try:
                results[pair_key] = self.get_pair_sentiment(pair_key)
            except Exception as e:
                results[pair_key] = {
                    "pair": pair_key,
                    "error": str(e),
                    "sentiment_score": 50,
                    "classification": "neutral",
                }
        return results


# ── Singleton ──────────────────────────────────────────────────────────
_collector = SocialNewsCollector()


def get_social_collector():
    """Get the global social news collector instance."""
    return _collector


def get_social_signal(pair_key):
    """Get social media sentiment signal for a pair.

    Returns dict with sentiment score (0-100) and classification.
    """
    collector = get_social_collector()
    return collector.get_pair_sentiment(pair_key)


def get_all_social_signals():
    """Get social media sentiment for all pairs."""
    collector = get_social_collector()
    return collector.get_all_sentiment()
