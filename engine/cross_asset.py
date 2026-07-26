"""Cross-Asset Analysis Engine.

Analyzes correlations and impact of:
- DXY (US Dollar Index)
- VIX (Volatility Index)
- US Yield Curve (2Y, 5Y, 10Y, 30Y)
- US Treasuries
on the trading pairs.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from config import CROSS_ASSETS, PAIRS
from engine.market_data import get_cross_asset_data, fetch_yahoo_data


def get_cross_asset_analysis():
    """Get comprehensive cross-asset analysis with correlations."""
    data = get_cross_asset_data()

    # Calculate yield curve spread
    yield_analysis = {}
    if "US2Y" in data and "US10Y" in data:
        us2y = data["US2Y"].get("value", 0)
        us10y = data["US10Y"].get("value", 0)
        spread_2_10 = us10y - us2y

        yield_analysis = {
            "2y_yield": us2y,
            "10y_yield": us10y,
            "30y_yield": data.get("US30Y", {}).get("value", 0),
            "spread_2_10": round(spread_2_10, 3),
            "yield_curve_status": "normal" if spread_2_10 > 0 else "inverted",
            "inverted": spread_2_10 < 0,
            "inversion_depth": round(abs(spread_2_10), 3) if spread_2_10 < 0 else 0,
        }

    # VIX analysis
    vix_analysis = {}
    if "VIX" in data:
        vix = data["VIX"].get("value", 0)
        vix_analysis = {
            "value": vix,
            "change": data["VIX"].get("change", 0),
            "regime": (
                "extreme_fear" if vix > 30
                else "fear" if vix > 20
                else "neutral" if vix > 12
                else "complacency"
            ),
            "risk_on": vix < 15,
        }

    # DXY analysis
    dxy_analysis = {}
    if "DXY" in data:
        dxy = data["DXY"].get("value", 0)
        dxy_change = data["DXY"].get("change", 0)
        dxy_analysis = {
            "value": dxy,
            "change": dxy_change,
            "trend": data["DXY"].get("trend", "neutral"),
            "strength": (
                "very_strong" if dxy > 105
                else "strong" if dxy > 100
                else "neutral" if dxy > 95
                else "weak"
            ),
        }

    # Pair correlation with DXY
    correlations = analyze_correlations()

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dxy": dxy_analysis,
        "vix": vix_analysis,
        "yields": yield_analysis,
        "correlations": correlations,
    }


def analyze_correlations():
    """Analyze correlation between cross-assets and trading pairs."""
    correlations = {}

    # Get historical data for analysis
    try:
        # Fetch DXY and VIX data for correlation
        dxy_df = fetch_yahoo_data("DX-Y.NYB", period="1mo", interval="1h")
        vix_df = fetch_yahoo_data("^VIX", period="1mo", interval="1h")
        tnx_df = fetch_yahoo_data("^TNX", period="1mo", interval="1h")

        if not dxy_df.empty:
            dxy_close = dxy_df["Close"]

            # Profile for each pair
            for pair_key, info in PAIRS.items():
                pair_df = fetch_yahoo_data(info.get("yahoo", ""),
                                            period="1mo", interval="1h") if info.get("yahoo") else pd.DataFrame()

                if not pair_df.empty and not dxy_df.empty:
                    pair_close = pair_df["Close"]

                    # Align indices
                    common_idx = pair_close.index.intersection(dxy_close.index)
                    if len(common_idx) > 10:
                        pair_aligned = pair_close.loc[common_idx]
                        dxy_aligned = dxy_close.loc[common_idx]

                        # Compute correlation
                        corr = pair_aligned.corr(dxy_aligned)

                        # Classify correlation strength
                        abs_corr = abs(corr)
                        if abs_corr > 0.7:
                            strength = "strong"
                        elif abs_corr > 0.4:
                            strength = "moderate"
                        elif abs_corr > 0.2:
                            strength = "weak"
                        else:
                            strength = "none"

                        correlations[pair_key] = {
                            "dxy_correlation": round(float(corr), 3),
                            "relationship": "inverse" if corr < -0.3 else "direct" if corr > 0.3 else "neutral",
                            "strength": strength,
                        }

                # If no yahoo data available (crypto), use estimated correlations
                if pair_key not in correlations:
                    # General estimated correlations
                    if pair_key == "XAUUSD":
                        correlations[pair_key] = {
                            "dxy_correlation": -0.75,
                            "relationship": "inverse",
                            "strength": "strong",
                            "estimated": True,
                            "note": "Gold typically inversely correlated with DXY",
                        }
                    elif pair_key in ["BTCUSD", "ETHUSD"]:
                        correlations[pair_key] = {
                            "dxy_correlation": -0.30,
                            "relationship": "inverse",
                            "strength": "weak",
                            "estimated": True,
                            "note": "Crypto has weak inverse correlation with USD",
                        }

    except Exception as e:
        # Use estimated correlations if API fails
        correlations = {
            "EURUSD": {"dxy_correlation": -0.85, "relationship": "inverse", "strength": "strong", "estimated": True},
            "GBPUSD": {"dxy_correlation": -0.80, "relationship": "inverse", "strength": "strong", "estimated": True},
            "XAUUSD": {"dxy_correlation": -0.75, "relationship": "inverse", "strength": "strong", "estimated": True},
            "BTCUSD": {"dxy_correlation": -0.30, "relationship": "inverse", "strength": "weak", "estimated": True},
            "ETHUSD": {"dxy_correlation": -0.25, "relationship": "inverse", "strength": "weak", "estimated": True},
        }

    return correlations


def get_market_regime():
    """Assess current market regime based on cross-asset data."""
    analysis = get_cross_asset_analysis()
    dxy = analysis.get("dxy", {})
    vix = analysis.get("vix", {})
    yields_data = analysis.get("yields", {})

    regime_signals = []

    # VIX regime
    vix_val = vix.get("value", 15)
    if vix_val > 30:
        regime_signals.append({
            "type": "risk_off",
            "severity": "extreme",
            "message": f"VIX at {vix_val:.1f} — Extreme fear. Consider reducing risky positions.",
        })
    elif vix_val > 20:
        regime_signals.append({
            "type": "risk_off",
            "severity": "moderate",
            "message": f"VIX at {vix_val:.1f} — Elevated fear. Hedge positions.",
        })
    elif vix_val < 12:
        regime_signals.append({
            "type": "risk_on",
            "severity": "high",
            "message": f"VIX at {vix_val:.1f} — Complacency. Trend-following favorable.",
        })

    # Yield curve
    if yields_data.get("inverted"):
        regime_signals.append({
            "type": "warning",
            "severity": "high",
            "message": f"Yield curve inverted ({yields_data.get('spread_2_10', 0):.2f}%). Recession signal — caution on risk assets.",
        })

    # DXY direction
    dxy_change = dxy.get("change", 0)
    if abs(dxy_change) > 1:
        direction = "strengthening" if dxy_change > 0 else "weakening"
        regime_signals.append({
            "type": "dxy",
            "severity": "moderate",
            "message": f"Dollar {direction} ({dxy_change:+.2f}%). Impacts all USD pairs.",
        })

    # Overall regime
    if vix_val > 25 and yields_data.get("inverted"):
        overall_regime = "DEFENSIVE"
        regime_color = "red"
    elif vix_val < 15 and not yields_data.get("inverted"):
        overall_regime = "RISK-ON"
        regime_color = "green"
    else:
        overall_regime = "NEUTRAL"
        regime_color = "yellow"

    return {
        "regime": overall_regime,
        "regime_color": regime_color,
        "signals": regime_signals,
        "vix": vix_val,
        "dxy_value": dxy.get("value", 0),
        "yield_spread": yields_data.get("spread_2_10", 0),
    }
