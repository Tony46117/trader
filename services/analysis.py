"""
╔══════════════════════════════════════════════════════════╗
║          Cross-Asset Analysis & Market Regime           ║
╠══════════════════════════════════════════════════════════╣
║  Analyzes correlations between forex pairs and:         ║
║  - DXY (US Dollar Index)                                ║
║  - VIX (Volatility Index)                               ║
║  - US Treasury Yields (5Y, 10Y, 30Y)                    ║
║  - Gold (XAUUSD)                                        ║
║  Determines market regime (risk-on/risk-off/sideways).  ║
╚══════════════════════════════════════════════════════════╝
"""
from datetime import datetime
import numpy as np
from config import PAIRS, CROSS_ASSETS
from services.market import get_cross_asset_data


def get_cross_asset_analysis():
    """Get cross-asset analysis with correlations and implications."""
    cross = get_cross_asset_data()
    analysis = {}

    # DXY Analysis
    dxy = cross.get("DXY", {})
    dxy_val = dxy.get("value", 0)
    dxy_trend = dxy.get("trend", "neutral")
    analysis["dxy"] = {
        "value": dxy_val,
        "change": dxy.get("change", 0),
        "trend": dxy_trend,
        "implication": "USD weakening — bullish for EURUSD, GBPUSD, XAUUSD" if dxy_trend == "bearish" else "USD strengthening — bearish for EURUSD, GBPUSD",
        "strength": "strong" if abs(dxy.get("change", 0)) > 0.5 else "moderate" if abs(dxy.get("change", 0)) > 0.2 else "weak",
    }

    # VIX Analysis
    vix = cross.get("VIX", {})
    vix_val = vix.get("value", 15)
    vix_trend = vix.get("trend", "neutral")
    if vix_val < 14:
        vix_regime = "low volatility"
    elif vix_val < 20:
        vix_regime = "normal"
    elif vix_val < 30:
        vix_regime = "elevated"
    else:
        vix_regime = "high stress"
    analysis["vix"] = {
        "value": vix_val,
        "change": vix.get("change", 0),
        "regime": vix_regime,
        "trend": vix_trend,
        "implication": "Risk-on environment favorable" if vix_val < 20 else "Caution — elevated volatility",
    }

    # Yield Analysis
    yield_data = {}
    for key in ["US5Y", "US10Y", "US30Y"]:
        y = cross.get(key, {})
        yield_data[key] = {"value": y.get("value", 0), "change": y.get("change", 0), "trend": y.get("trend", "neutral")}

    us10y = yield_data.get("US10Y", {})
    us10y_val = us10y.get("value", 4.0)
    yield_curve = "inverted" if any(
        yield_data.get(k, {}).get("value", 0) and yield_data.get(k, {}).get("value", 0) > us10y_val
        for k in ["US5Y"] if k in yield_data
    ) else "normal"

    analysis["yields"] = {
        **yield_data,
        "curve": yield_curve,
        "implication": "Yield curve normal — positive growth outlook" if yield_curve == "normal" else "Yield curve inverted — recession signal",
    }

    return analysis


def get_market_regime():
    """Determine the current market regime (risk-on/risk-off/sideways)."""
    cross = get_cross_asset_data()

    vix_val = cross.get("VIX", {}).get("value", 15)
    dxy_trend = cross.get("DXY", {}).get("trend", "neutral")
    us10y_val = cross.get("US10Y", {}).get("value", 4.0)

    vix_signal = vix_val < 18  # Low vol = risk-on
    dxy_signal = dxy_trend == "bearish"  # Falling USD = risk-on for risk assets

    risk_score = sum([vix_signal, dxy_signal])

    if risk_score >= 2:
        regime = "RISK_ON"
        description = "Risk-on environment. Favorable for equities and risk currencies."
    elif risk_score >= 1:
        regime = "MIXED"
        description = "Mixed signals. Selective positioning recommended."
    else:
        regime = "RISK_OFF"
        description = "Risk-off environment. Favor safe havens and capital preservation."

    return {
        "regime": regime,
        "description": description,
        "vix": vix_val,
        "dxy_trend": dxy_trend,
        "us10y": us10y_val,
        "risk_score": risk_score,
        "updated": datetime.now().strftime("%H:%M:%S"),
    }
