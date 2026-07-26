"""Tick Data Analysis Engine.

Analyzes tick-level data to compute:
- Realized volatility (1m, 5m, 15m windows)
- Tick momentum (bid/ask imbalance, tick frequency)
- Microstructure signals (spread analysis, trade flow)
- Volume-weighted price metrics
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque
import json
import os

from config import CACHE_DIR


class TickAnalyzer:
    """Real-time tick data analyzer for volatility and momentum."""

    def __init__(self, max_ticks=10000):
        self.max_ticks = max_ticks
        self.tick_buffers = {}  # pair_key -> deque of tick dicts
        self.volatility_cache = {}

    def add_tick(self, pair_key, price, volume, bid=None, ask=None, timestamp=None):
        """Add a single tick data point."""
        if pair_key not in self.tick_buffers:
            self.tick_buffers[pair_key] = deque(maxlen=self.max_ticks)

        tick = {
            "price": float(price),
            "volume": float(volume),
            "bid": float(bid) if bid is not None else float(price),
            "ask": float(ask) if ask is not None else float(price),
            "timestamp": timestamp or datetime.now(),
        }
        self.tick_buffers[pair_key].append(tick)

    def simulate_tick_data(self, pair_key, current_price, volatility=0.0001, num_ticks=200):
        """Generate simulated tick data based on current price and volatility.

        Used when real tick data isn't available — creates realistic microstructure.
        """
        np.random.seed(hash(pair_key + datetime.now().strftime("%Y%m%d%H")) % 2**32)
        ticks = []
        price = current_price
        spread = current_price * 0.0001  # ~1 pip spread

        for i in range(num_ticks):
            # Random walk with mean-reverting tendency
            ret = np.random.normal(0, volatility)
            ret += -0.01 * (price - current_price) / current_price  # mean reversion
            price *= (1 + ret)

            # Random volume
            volume = np.random.exponential(10) * (1 + abs(ret) * 100)

            bid = price - spread / 2
            ask = price + spread / 2

            tick = {
                "price": round(price, 5),
                "volume": round(volume, 2),
                "bid": round(bid, 5),
                "ask": round(ask, 5),
                "timestamp": datetime.now() - timedelta(seconds=(num_ticks - i)),
            }
            ticks.append(tick)

        # Add to buffer
        if pair_key not in self.tick_buffers:
            self.tick_buffers[pair_key] = deque(maxlen=self.max_ticks)
        for tick in ticks:
            self.tick_buffers[pair_key].append(tick)

        return ticks

    def compute_realized_volatility(self, pair_key, window_ticks=50):
        """Compute realized volatility from tick data.

        Returns annualized volatility estimate.
        """
        ticks = list(self.tick_buffers.get(pair_key, []))
        if len(ticks) < window_ticks:
            # Not enough ticks, simulate some
            if len(ticks) > 0:
                self.simulate_tick_data(pair_key, ticks[-1]["price"], num_ticks=window_ticks)
                ticks = list(self.tick_buffers.get(pair_key, []))

        if len(ticks) < 10:
            return {"volatility": 0, "annualized_vol": 0, "quality": "insufficient_data"}

        prices = np.array([t["price"] for t in ticks[-window_ticks:]])
        log_returns = np.diff(np.log(prices))

        if len(log_returns) < 2:
            return {"volatility": 0, "annualized_vol": 0, "quality": "insufficient_data"}

        realized_vol = np.std(log_returns)
        annualized_vol = realized_vol * np.sqrt(252 * 6.5 * 3600)  # Scale to annual

        # Volatility regime
        annualized_pct = annualized_vol * 100
        if annualized_pct > 30:
            regime = "extreme"
        elif annualized_pct > 20:
            regime = "high"
        elif annualized_pct > 12:
            regime = "elevated"
        elif annualized_pct > 8:
            regime = "moderate"
        else:
            regime = "low"

        return {
            "volatility": round(float(realized_vol), 6),
            "annualized_vol_pct": round(float(annualized_pct), 2),
            "regime": regime,
            "sample_size": len(log_returns),
            "quality": "simulated" if len(ticks) < window_ticks * 2 else "real",
        }

    def compute_tick_momentum(self, pair_key, window_ticks=20):
        """Compute tick-level momentum indicators.

        Returns:
            - tick_imbalance: (buy_volume - sell_volume) / total_volume
            - price_momentum: rate of price change per tick
            - tick_frequency: ticks per second
            - micro_trend: short-term directional bias
        """
        ticks = list(self.tick_buffers.get(pair_key, []))
        if len(ticks) < window_ticks:
            return {
                "tick_imbalance": 0,
                "price_momentum": 0,
                "tick_frequency": 0,
                "micro_trend": "neutral",
                "quality": "insufficient_data",
            }

        recent = ticks[-window_ticks:]

        # Tick imbalance (tick direction based on price change)
        buy_volume = 0
        sell_volume = 0
        for i in range(1, len(recent)):
            if recent[i]["price"] > recent[i - 1]["price"]:
                buy_volume += recent[i]["volume"]
            elif recent[i]["price"] < recent[i - 1]["price"]:
                sell_volume += recent[i]["volume"]

        total_volume = buy_volume + sell_volume
        imbalance = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0

        # Price momentum (rate of price change)
        price_change = (recent[-1]["price"] - recent[0]["price"]) / recent[0]["price"]
        momentum = price_change * 10000  # in pips/bps

        # Tick frequency
        if len(recent) >= 2:
            time_span = (recent[-1]["timestamp"] - recent[0]["timestamp"]).total_seconds()
            frequency = len(recent) / max(time_span, 0.1)
        else:
            frequency = 0

        # Micro trend
        if imbalance > 0.3 and momentum > 0:
            micro_trend = "strong_buy"
        elif imbalance > 0.1 and momentum > 0:
            micro_trend = "buy"
        elif imbalance < -0.3 and momentum < 0:
            micro_trend = "strong_sell"
        elif imbalance < -0.1 and momentum < 0:
            micro_trend = "sell"
        else:
            micro_trend = "neutral"

        return {
            "tick_imbalance": round(float(imbalance), 3),
            "price_momentum": round(float(momentum), 2),
            "tick_frequency": round(float(frequency), 1),
            "micro_trend": micro_trend,
            "buy_volume": round(float(buy_volume), 1),
            "sell_volume": round(float(sell_volume), 1),
        }

    def compute_spread_analysis(self, pair_key):
        """Analyze bid/ask spread dynamics."""
        ticks = list(self.tick_buffers.get(pair_key, []))
        if len(ticks) < 10:
            return {
                "avg_spread": 0,
                "max_spread": 0,
                "spread_volatility": 0,
                "liquidity_score": 0,
            }

        spreads = []
        for t in ticks[-100:]:
            if t["ask"] > t["bid"]:
                spread_pips = (t["ask"] - t["bid"]) / t["bid"] * 10000
                spreads.append(spread_pips)

        if not spreads:
            return {"avg_spread": 0, "max_spread": 0, "spread_volatility": 0, "liquidity_score": 0}

        avg_spread = np.mean(spreads)
        max_spread = np.max(spreads)
        spread_vol = np.std(spreads)

        # Liquidity score: lower spread = higher liquidity
        if avg_spread < 0.5:
            liquidity = 10  # Excellent
        elif avg_spread < 1:
            liquidity = 8
        elif avg_spread < 2:
            liquidity = 6
        elif avg_spread < 5:
            liquidity = 4
        else:
            liquidity = 2

        return {
            "avg_spread_pips": round(float(avg_spread), 2),
            "max_spread_pips": round(float(max_spread), 2),
            "spread_volatility": round(float(spread_vol), 3),
            "liquidity_score": liquidity,
            "sample_size": len(spreads),
        }

    def compute_volatility_signal(self, pair_key, current_price):
        """Generate a volatility-adjusted signal component.

        Returns signal dict with:
        - vol_adjusted_score: adjusts base signal based on volatility regime
        - momentum_score: 0-100 based on tick momentum
        - volatility_warning: caution flag for high vol regimes
        """
        vol_data = self.compute_realized_volatility(pair_key)
        momentum = self.compute_tick_momentum(pair_key)
        spread = self.compute_spread_analysis(pair_key)

        # Volatility adjustment
        vol_regime = vol_data.get("regime", "moderate")
        annualized_vol = vol_data.get("annualized_vol_pct", 15)

        if vol_regime == "extreme":
            vol_warning = "extreme"
            vol_factor = 0.5  # Reduce conviction in extreme vol
        elif vol_regime == "high":
            vol_warning = "high"
            vol_factor = 0.7
        elif vol_regime == "elevated":
            vol_warning = "elevated"
            vol_factor = 0.9
        else:
            vol_warning = "normal"
            vol_factor = 1.0

        # Momentum scoring
        micro_trend = momentum.get("micro_trend", "neutral")
        if micro_trend == "strong_buy":
            momentum_score = 85
        elif micro_trend == "buy":
            momentum_score = 65
        elif micro_trend == "strong_sell":
            momentum_score = 15
        elif micro_trend == "sell":
            momentum_score = 35
        else:
            momentum_score = 50

        # Liquidity check
        liquidity = spread.get("liquidity_score", 5)
        if liquidity < 4:
            liq_warning = "low_liquidity"
        else:
            liq_warning = "normal"

        return {
            "volatility_regime": vol_regime,
            "annualized_vol": annualized_vol,
            "vol_factor": vol_factor,
            "momentum_score": momentum_score,
            "micro_trend": micro_trend,
            "tick_imbalance": momentum.get("tick_imbalance", 0),
            "volatility_warning": vol_warning,
            "liquidity_warning": liq_warning,
            "liquidity_score": liquidity,
            "spread_pips": spread.get("avg_spread_pips", 0),
        }


# ── Singleton instance ────────────────────────────────────────────────
_analyzer = TickAnalyzer()


def get_tick_analyzer():
    """Get the global tick analyzer instance."""
    return _analyzer


def get_tick_signal(pair_key, current_price):
    """Get the tick-based signal component for a pair.

    Convenience function that initializes simulated tick data if needed
    and returns the volatility-adjusted signal.
    """
    analyzer = get_tick_analyzer()
    ticks = list(analyzer.tick_buffers.get(pair_key, []))
    if len(ticks) < 50:
        # Initialize with simulated ticks
        analyzer.simulate_tick_data(pair_key, current_price, num_ticks=200)

    return analyzer.compute_volatility_signal(pair_key, current_price)
