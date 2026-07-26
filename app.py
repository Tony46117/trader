"""Forex Trading Signal Framework — Main Application.

A comprehensive web framework that:
- Collects and analyzes high-quality news data
- Generates live trading signals with entry/SL/TP levels
- Provides cross-asset analysis (DXY, VIX, Yields)
- Delivers high-quality setups with snappy precision
"""

import os
import sys
import json
from datetime import datetime

from flask import Flask, render_template, jsonify, request

# Ensure project root is in path for robust imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PAIRS, CROSS_ASSETS
from engine.market_data import get_current_prices, get_cross_asset_data
from engine.news_engine import get_all_upcoming_events, get_news_summary, load_news_data, get_all_news_signals
from engine.signal_engine import generate_all_technical_signals
from engine.unified_signal import generate_unified_signal, generate_all_unified_signals, get_top_setups
from engine.cross_asset import get_cross_asset_analysis, get_market_regime

app = Flask(__name__)


# ── Routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Main dashboard with market overview, signals, and news."""
    return render_template(
        "index.html",
        title="Dashboard",
        pairs=list(PAIRS.keys()),
        active_page="dashboard",
    )


@app.route("/signals")
def signals():
    """Detailed trading signals page."""
    return render_template(
        "signals.html",
        title="Trading Signals",
        pairs=list(PAIRS.keys()),
        active_page="signals",
    )


@app.route("/news")
def news():
    """News calendar page."""
    return render_template(
        "news.html",
        title="News Calendar",
        active_page="news",
    )


@app.route("/analysis")
def analysis():
    """Cross-asset analysis page."""
    return render_template(
        "analysis.html",
        title="Cross-Asset Analysis",
        active_page="analysis",
    )


# ── API Routes ──────────────────────────────────────────────────────

@app.route("/api/market/overview")
def api_market_overview():
    """API: Get market overview with prices and signals."""
    try:
        from engine.market_data import get_current_prices
        prices = get_current_prices()
        unified = generate_all_unified_signals()

        overview = {}
        for pair_key in PAIRS:
            price_data = prices.get(pair_key, {})
            sig = unified.get(pair_key, {})
            unified_component = sig.get("unified", {})

            overview[pair_key] = {
                "name": PAIRS[pair_key]["name"],
                "type": PAIRS[pair_key]["type"],
                "price": price_data.get("bid", 0),
                "change": price_data.get("change", 0),
                # Unified signal
                "direction": unified_component.get("direction", "NEUTRAL"),
                "score": unified_component.get("score", 50),
                "verdict": unified_component.get("verdict", ""),
                "confidence": unified_component.get("confidence", "LOW"),
                "agreement": unified_component.get("agreement", ""),
                "entry": sig.get("entry_price"),
                "sl": sig.get("stop_loss"),
                "tp1": sig.get("take_profit_1"),
                "tp2": sig.get("take_profit_2"),
                "timing": sig.get("timing", "WAIT"),
            }

        return jsonify({"status": "ok", "data": overview})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/unified")
def api_unified_signals():
    """API: Get unified signals (technical + news combined) for all pairs."""
    try:
        signals = generate_all_unified_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/unified/<pair>")
def api_unified_signal_pair(pair):
    """API: Get unified signal for a specific pair."""
    try:
        pair = pair.upper()
        if pair not in PAIRS:
            return jsonify({"status": "error", "message": f"Invalid pair: {pair}"})
        signal = generate_unified_signal(pair)
        return jsonify({"status": "ok", "data": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/technical")
def api_technical_signals():
    """API: Get technical-only signals."""
    try:
        signals = generate_all_technical_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/news")
def api_news_signals():
    """API: Get news-only signals for each pair."""
    try:
        signals = get_all_news_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/setups")
def api_trading_setups():
    """API: Get top unified trading setups (high confidence)."""
    try:
        min_score = request.args.get("min_score", 60, type=int)
        max_results = request.args.get("max", 5, type=int)
        setups = get_top_setups(min_score=min_score, max_results=max_results)
        return jsonify({"status": "ok", "data": setups})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/news/upcoming")
def api_upcoming_news():
    """API: Get upcoming news events."""
    try:
        hours = request.args.get("hours", 72, type=int)
        events = get_all_upcoming_events(hours_ahead=hours)
        return jsonify({
            "status": "ok",
            "data": events,
            "count": len(events),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/news/summary")
def api_news_summary():
    """API: Get news summary statistics."""
    try:
        summary = get_news_summary()
        return jsonify({"status": "ok", "data": summary})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/analysis/cross-asset")
def api_cross_asset():
    """API: Get cross-asset analysis."""
    try:
        analysis_data = get_cross_asset_analysis()
        return jsonify({"status": "ok", "data": analysis_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/analysis/regime")
def api_market_regime():
    """API: Get current market regime assessment."""
    try:
        regime = get_market_regime()
        return jsonify({"status": "ok", "data": regime})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/prices")
def api_prices():
    """API: Get current prices only."""
    try:
        prices = get_current_prices()
        return jsonify({"status": "ok", "data": prices})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ── Error Handlers ──────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Route not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          FOREX TRADING SIGNAL FRAMEWORK                 ║
╠══════════════════════════════════════════════════════════╣
║  Pairs: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD         ║
║  Features: Live Signals • News Calendar • Cross-Asset   ║
║  Framework: Flask + Pandas + TA-Lib + yfinance          ║
╠══════════════════════════════════════════════════════════╣
║  🌐  http://localhost:{port}                               ║
╚══════════════════════════════════════════════════════════╝
""")

    app.run(host="0.0.0.0", port=port, debug=debug)
