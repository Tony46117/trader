"""
╔══════════════════════════════════════════════════════════╗
║                   TRADER v2                             ║
║          Forex Trading Signal Framework                 ║
╠══════════════════════════════════════════════════════════╣
║  A comprehensive trading framework that:                ║
║  - Collects live market data (Yahoo + Crypto)           ║
║  - Generates trading signals with 5-source fusion       ║
║  - Enforces minimum 1:2 risk-reward on all setups       ║
║  - Provides cross-asset & market regime analysis        ║
║  - Tracks active signals with SL/TP hit detection       ║
╠══════════════════════════════════════════════════════════╣
║  Pairs: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD         ║
║  Cache: 30s  |  Min RR: 1:2  |  5-Source Fusion        ║
╚══════════════════════════════════════════════════════════╝
"""
import os
import sys
import time
import threading
from functools import wraps
from datetime import datetime

from flask import Flask, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PAIRS, CACHE_TTL
from services.market import get_current_prices, get_cross_asset_data
from services.signals import (
    generate_all_technical_signals, generate_unified_signal,
    generate_all_unified_signals, get_top_setups,
)
from services.analysis import get_cross_asset_analysis, get_market_regime
from providers.news import get_upcoming_events, get_all_news_signals, get_news_signal_for_pair
from models.state import signal_state_manager

app = Flask(__name__, static_url_path="/static", static_folder="static")

# ── Caching ─────────────────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()


def cached(ttl=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f.__name__ + str(args) + str(sorted(kwargs.items()))
            ttl_val = ttl or CACHE_TTL
            with _cache_lock:
                if key in _cache and time.time() - _cache[key][0] < ttl_val:
                    return _cache[key][1]
            result = f(*args, **kwargs)
            with _cache_lock:
                _cache[key] = (time.time(), result)
            return result
        return wrapper
    return decorator


# ── SPA Serving ─────────────────────────────────────────────────────
_SPA_HTML = None


def _load_spa():
    global _SPA_HTML
    spa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    try:
        with open(spa_path) as f:
            _SPA_HTML = f.read()
        return True
    except Exception:
        _SPA_HTML = "<html><body><h1>Trader Loading...</h1></body></html>"
        return False


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if path.startswith("api/"):
        return jsonify({"status": "error", "message": "Not found"}), 404
    if path.startswith("static/"):
        return app.send_static_file(path[8:]) if os.path.exists(os.path.join("static", path[8:])) else ("Not found", 404)
    if _SPA_HTML is None:
        _load_spa()
    return _SPA_HTML


# ── Market Data API ─────────────────────────────────────────────────

@app.route("/api/prices")
@cached(ttl=15)
def api_prices():
    return jsonify({"status": "ok", "data": get_current_prices()})


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
            uni = sig.get("unified", {}) if isinstance(sig, dict) else {}
            current = price_data.get("bid", 0)

            pair_info = PAIRS.get(pair_key, {})
            pip_size = pair_info.get("pip", 0.0001)
            if current > 0:
                signal_state_manager.check_price_levels(pair_key, current)

            active = signal_state_manager.get_active_signal(pair_key)

            overview[pair_key] = {
                "name": pair_info.get("name", pair_key),
                "type": pair_info.get("type", "unknown"),
                "price": current,
                "change": price_data.get("change", 0),
                "direction": uni.get("direction", "NEUTRAL"),
                "score": uni.get("score", 50),
                "verdict": uni.get("verdict", ""),
                "confidence": uni.get("confidence", "LOW"),
                "agreement": uni.get("agreement", ""),
                "entry": sig.get("entry_price") or sig.get("entry"),
                "sl": sig.get("stop_loss") or sig.get("sl"),
                "tp1": sig.get("take_profit_1") or sig.get("tp1"),
                "tp2": sig.get("take_profit_2") or sig.get("tp2"),
                "rr1": sig.get("risk_reward_1") or sig.get("rr1"),
                "timing": sig.get("timing", "WAIT"),
                "setup_valid": sig.get("setup_valid", False),
                "signal_state": sig.get("signal_state", {}),
                "active_signal": active,
            }

        return jsonify({"status": "ok", "data": overview})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ── Signals API ─────────────────────────────────────────────────────

@app.route("/api/signals/unified")
@cached(ttl=30)
def api_unified_signals():
    return jsonify({"status": "ok", "data": generate_all_unified_signals()})


@app.route("/api/signals/unified/<pair>")
@cached(ttl=30)
def api_unified_signal_pair(pair):
    pair = pair.upper()
    if pair not in PAIRS:
        return jsonify({"status": "error", "message": f"Invalid pair: {pair}"}), 404
    return jsonify({"status": "ok", "data": generate_unified_signal(pair)})


@app.route("/api/signals/technical")
@cached(ttl=30)
def api_technical_signals():
    return jsonify({"status": "ok", "data": generate_all_technical_signals()})


@app.route("/api/signals/setups")
@cached(ttl=30)
def api_trading_setups():
    min_score = request.args.get("min_score", 55, type=int)
    max_results = request.args.get("max", 5, type=int)
    return jsonify({"status": "ok", "data": get_top_setups(min_score=min_score, max_results=max_results)})


# ── Signal State API ────────────────────────────────────────────────

@app.route("/api/signals/active")
def api_active_signals():
    return jsonify({"status": "ok", "data": signal_state_manager.get_all_active_signals()})


@app.route("/api/signals/active/<pair>")
def api_active_signal_pair(pair):
    pair = pair.upper()
    return jsonify({"status": "ok", "data": signal_state_manager.get_active_signal(pair)})


@app.route("/api/signals/close/<pair>", methods=["POST"])
def api_close_signal(pair):
    pair = pair.upper()
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "MANUAL_CLOSE")
    result = signal_state_manager.close_signal(pair, reason)
    if result:
        return jsonify({"status": "ok", "data": result})
    return jsonify({"status": "error", "message": f"No active signal for {pair}"}), 404


@app.route("/api/signals/force/<pair>", methods=["POST"])
def api_force_new_signal(pair):
    pair = pair.upper()
    signal_state_manager.force_new_signal(pair)
    return jsonify({"status": "ok", "message": f"Force-closed signal for {pair}"})


@app.route("/api/signals/history")
@app.route("/api/signals/history/<pair>")
def api_signal_history(pair=None):
    if pair:
        pair = pair.upper()
    limit = request.args.get("limit", 10, type=int)
    return jsonify({"status": "ok", "data": signal_state_manager.get_history(pair, limit)})


# ── News API ────────────────────────────────────────────────────────

@app.route("/api/news/upcoming")
@cached(ttl=60)
def api_upcoming_news():
    hours = request.args.get("hours", 72, type=int)
    events = get_upcoming_events(hours_ahead=hours)
    return jsonify({"status": "ok", "data": events, "count": len(events)})


@app.route("/api/news/signals")
@cached(ttl=60)
def api_news_signals():
    signals = get_all_news_signals()
    return jsonify({"status": "ok", "data": signals})


@app.route("/api/news/signals/<pair>")
@cached(ttl=60)
def api_news_signal_pair(pair):
    pair = pair.upper()
    if pair not in PAIRS:
        return jsonify({"status": "error", "message": f"Invalid pair: {pair}"}), 404
    signal = get_news_signal_for_pair(pair)
    return jsonify({"status": "ok", "data": signal})


# ── Analysis API ────────────────────────────────────────────────────

@app.route("/api/analysis/cross-asset")
@cached(ttl=60)
def api_cross_asset():
    return jsonify({"status": "ok", "data": get_cross_asset_analysis()})


@app.route("/api/analysis/regime")
@cached(ttl=60)
def api_market_regime():
    return jsonify({"status": "ok", "data": get_market_regime()})


# ── C++ Status Check ───────────────────────────────────────────────

def _check_cpp():
    """Check and print C++ indicator status."""
    try:
        from services.indicators import _INDICATORS_CPP
        if _INDICATORS_CPP:
            print("  ⚡ C++ indicators: ACCELERATED")
        else:
            print("  ⚡ C++ indicators: pure Python (install python3.12-devel & recompile for speed)")
    except Exception:
        print("  ⚡ C++ indicators: pure Python")


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
║                   TRADER v2                             ║
║          Forex Trading Signal Framework                 ║
╠══════════════════════════════════════════════════════════╣
║  Pairs: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD         ║
║  Min RR: 1:2  •  Cache: {str(CACHE_TTL)+'s':>7}  •  5-Source Fusion        ║
║  Features: Live Prices · Signals · Analysis · CME       ║
╠══════════════════════════════════════════════════════════╣
║  🌐  http://localhost:{port}                               ║
╚══════════════════════════════════════════════════════════╝
""")

    _check_cpp()

    app.run(host="0.0.0.0", port=port, debug=debug)
