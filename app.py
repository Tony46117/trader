"""Forex Trading Signal Framework — Main Application.

A comprehensive web framework that:
- Collects and analyzes high-quality news data
- Generates live trading signals with entry/SL/TP levels
- Provides cross-asset analysis (DXY, VIX, Yields)
- Delivers high-quality setups with 1:2 minimum RR enforcement
"""

import os
import sys
import time
import threading
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PAIRS, CROSS_ASSETS
from engine.market_data import get_current_prices, get_cross_asset_data
from engine.news_engine import get_all_upcoming_events, get_news_summary, load_news_data, get_all_news_signals
from engine.signal_engine import generate_all_technical_signals
from engine.unified_signal import generate_unified_signal, generate_all_unified_signals, get_top_setups
from engine.cross_asset import get_cross_asset_analysis, get_market_regime
from engine.tick_data import get_tick_signal
from engine.cme_data import get_all_cme_analysis
from engine.social_news import get_all_social_signals, get_social_signal
from engine.signal_state import signal_state_manager

app = Flask(__name__)

# ── In-Memory Cache ────────────────────────────────────────────────

_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 30  # seconds


def cached(ttl=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f.__name__ + str(args) + str(sorted(kwargs.items()))
            ttl_val = ttl or CACHE_TTL
            with _cache_lock:
                if key in _cache:
                    ts, data = _cache[key]
                    if time.time() - ts < ttl_val:
                        return data
            result = f(*args, **kwargs)
            with _cache_lock:
                _cache[key] = (time.time(), result)
            return result
        return wrapper
    return decorator


# ── SPA Route ──────────────────────────────────────────────────────
# Serve the React SPA for all non-API routes

SPA_HTML = None


def load_spa():
    global SPA_HTML
    spa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    try:
        with open(spa_path, "r") as f:
            SPA_HTML = f.read()
        return True
    except Exception as e:
        print(f"⚠️ Could not load SPA: {e}")
        return False


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    """Serve the React SPA for any non-API route."""
    # Skip API routes
    if path.startswith("api/"):
        return jsonify({"status": "error", "message": "Not found"}), 404
    if SPA_HTML is None:
        load_spa()
    return SPA_HTML or "<html><body><h1>Loading...</h1></body></html>"


# ── API Routes ──────────────────────────────────────────────────────

@app.route("/api/market/overview")
@cached(ttl=30)
def api_market_overview():
    try:
        prices = get_current_prices()
        unified = generate_all_unified_signals()

        overview = {}
        for pair_key in PAIRS:
            price_data = prices.get(pair_key, {})
            sig = unified.get(pair_key, {})
            unified_component = sig.get("unified", {})
            current = price_data.get("bid", 0)

            # Check SL/TP hits on each refresh
            pair_info = PAIRS.get(pair_key, {})
            pip_size = pair_info.get("pip", 0.0001)
            if current > 0:
                signal_state_manager.check_price_levels(pair_key, current, pip_size)

            # Re-check active signal after potential hit
            active = signal_state_manager.get_active_signal(pair_key)

            overview[pair_key] = {
                "name": PAIRS[pair_key]["name"],
                "type": PAIRS[pair_key]["type"],
                "price": current,
                "change": price_data.get("change", 0),
                "direction": unified_component.get("direction", "NEUTRAL"),
                "score": unified_component.get("score", 50),
                "verdict": unified_component.get("verdict", ""),
                "confidence": unified_component.get("confidence", "LOW"),
                "agreement": unified_component.get("agreement", ""),
                "entry": sig.get("entry_price"),
                "sl": sig.get("stop_loss"),
                "tp1": sig.get("take_profit_1"),
                "tp2": sig.get("take_profit_2"),
                "rr1": sig.get("risk_reward_1"),
                "timing": sig.get("timing", "WAIT"),
                "setup_valid": sig.get("setup_valid", False),
                "signal_state": sig.get("signal_state", {}),
                "active_signal": active,
            }

        return jsonify({"status": "ok", "data": overview})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/unified")
@cached(ttl=30)
def api_unified_signals():
    try:
        signals = generate_all_unified_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/unified/<pair>")
@cached(ttl=30)
def api_unified_signal_pair(pair):
    try:
        pair = pair.upper()
        if pair not in PAIRS:
            return jsonify({"status": "error", "message": f"Invalid pair: {pair}"})
        signal = generate_unified_signal(pair)
        return jsonify({"status": "ok", "data": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/technical")
@cached(ttl=30)
def api_technical_signals():
    try:
        signals = generate_all_technical_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/news")
@cached(ttl=60)
def api_news_signals():
    try:
        signals = get_all_news_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/setups")
@cached(ttl=30)
def api_trading_setups():
    try:
        min_score = request.args.get("min_score", 55, type=int)
        max_results = request.args.get("max", 5, type=int)
        setups = get_top_setups(min_score=min_score, max_results=max_results)
        return jsonify({"status": "ok", "data": setups})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/news/upcoming")
@cached(ttl=60)
def api_upcoming_news():
    try:
        hours = request.args.get("hours", 72, type=int)
        events = get_all_upcoming_events(hours_ahead=hours)
        return jsonify({"status": "ok", "data": events, "count": len(events)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/news/summary")
@cached(ttl=60)
def api_news_summary():
    try:
        summary = get_news_summary()
        return jsonify({"status": "ok", "data": summary})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/analysis/cross-asset")
@cached(ttl=60)
def api_cross_asset():
    try:
        analysis_data = get_cross_asset_analysis()
        return jsonify({"status": "ok", "data": analysis_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/analysis/regime")
@cached(ttl=60)
def api_market_regime():
    try:
        regime = get_market_regime()
        return jsonify({"status": "ok", "data": regime})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/prices")
@cached(ttl=15)
def api_prices():
    try:
        prices = get_current_prices()
        return jsonify({"status": "ok", "data": prices})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/tick/<pair>")
@cached(ttl=15)
def api_tick_data(pair):
    try:
        pair = pair.upper()
        prices = get_current_prices()
        price = prices.get(pair, {}).get("bid", 0)
        if price == 0:
            return jsonify({"status": "error", "message": f"No price data for {pair}"})
        signal = get_tick_signal(pair, price)
        return jsonify({"status": "ok", "data": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/cme")
@cached(ttl=120)
def api_cme_all():
    try:
        prices = get_current_prices()
        data = get_all_cme_analysis(prices)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/cme/<pair>")
@cached(ttl=120)
def api_cme_pair(pair):
    try:
        pair = pair.upper()
        from engine.cme_data import get_cme_analysis
        prices = get_current_prices()
        price = prices.get(pair, {}).get("bid", 1.0)
        if price == 0:
            price = 1.0
        data = get_cme_analysis(pair, price)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/social")
@cached(ttl=300)
def api_social_all():
    try:
        data = get_all_social_signals()
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/social/<pair>")
@cached(ttl=300)
def api_social_pair(pair):
    try:
        pair = pair.upper()
        data = get_social_signal(pair)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ── Signal State Endpoints ────────────────────────────────────────

@app.route("/api/signals/active")
def api_active_signals():
    try:
        signals = signal_state_manager.get_all_active_signals()
        return jsonify({"status": "ok", "data": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/active/<pair>")
def api_active_signal_pair(pair):
    try:
        pair = pair.upper()
        signal = signal_state_manager.get_active_signal(pair)
        return jsonify({"status": "ok", "data": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/close/<pair>", methods=["POST"])
def api_close_signal(pair):
    try:
        pair = pair.upper()
        data = request.get_json(silent=True) or {}
        reason = data.get("reason", "MANUAL_CLOSE")
        result = signal_state_manager.close_signal(pair, reason)
        if result:
            return jsonify({"status": "ok", "data": result})
        return jsonify({"status": "error", "message": f"No active signal for {pair}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/force/<pair>", methods=["POST"])
def api_force_new_signal(pair):
    try:
        pair = pair.upper()
        signal_state_manager.force_new_signal(pair)
        return jsonify({"status": "ok", "message": f"Force-closed signal for {pair}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/signals/history")
@app.route("/api/signals/history/<pair>")
def api_signal_history(pair=None):
    try:
        if pair:
            pair = pair.upper()
        limit = request.args.get("limit", 10, type=int)
        history = signal_state_manager.get_history(pair, limit)
        return jsonify({"status": "ok", "data": history})
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
║  Min RR: 1:2  •  Cache: 30s  •  5-Source Fusion        ║
║  Features: Live Signals · News · Cross-Asset · CME      ║
╠══════════════════════════════════════════════════════════╣
║  🌐  http://localhost:{port}                               ║
╚══════════════════════════════════════════════════════════╝
""")

    app.run(host="0.0.0.0", port=port, debug=debug)
