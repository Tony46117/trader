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
from engine.deriv_bot import (
    get_deriv_trader,
    get_active_trades,
    get_trade_history,
    get_trade_logs,
    get_account_summary,
    has_active_signal,
    close_trade,
)

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


# ── Page Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", title="Dashboard", pairs=list(PAIRS.keys()), active_page="dashboard")


@app.route("/signals")
def signals():
    return render_template("signals.html", title="Trading Signals", pairs=list(PAIRS.keys()), active_page="signals")


@app.route("/news")
def news():
    return render_template("news.html", title="News Calendar", active_page="news")


@app.route("/analysis")
def analysis():
    return render_template("analysis.html", title="Cross-Asset Analysis", active_page="analysis")


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

            overview[pair_key] = {
                "name": PAIRS[pair_key]["name"],
                "type": PAIRS[pair_key]["type"],
                "price": price_data.get("bid", 0),
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


# ── Deriv Trading Bot Routes ──

@app.route("/trading-bot")
def trading_bot_page():
    return render_template("trading_bot.html", title="Trading Bot", active_page="trading-bot")


@app.route("/api/trading/account")
def api_trading_account():
    try:
        trader = get_deriv_trader()
        info = trader.get_account_info()
        return jsonify({"status": "ok", "data": info})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/trading/trades/active")
def api_trading_active_trades():
    try:
        trades = get_active_trades()
        return jsonify({"status": "ok", "data": trades})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/trading/trades/history")
def api_trading_trade_history():
    try:
        limit = request.args.get("limit", 50, type=int)
        trades = get_trade_history(limit=limit)
        return jsonify({"status": "ok", "data": trades})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/trading/logs")
def api_trading_logs():
    try:
        trade_id = request.args.get("trade_id", type=int)
        limit = request.args.get("limit", 100, type=int)
        logs = get_trade_logs(trade_id=trade_id, limit=limit)
        return jsonify({"status": "ok", "data": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/trading/summary")
def api_trading_summary():
    try:
        summary = get_account_summary()
        return jsonify({"status": "ok", "data": summary})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/trading/close/<int:trade_id>", methods=["POST"])
def api_close_trade(trade_id):
    try:
        data = request.get_json() or {}
        exit_price = data.get("exit_price", 0)
        exit_reason = data.get("exit_reason", "MANUAL")
        close_trade(trade_id, exit_price, exit_reason)
        return jsonify({"status": "ok", "message": f"Trade {trade_id} closed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ── TradingView-style WebSocket endpoint (placeholder) ──

@app.route("/api/tradingview/config")
def api_tradingview_config():
    """TradingView Charting Library config for indicator integration."""
    return jsonify({
        "supported_resolutions": ["1", "5", "15", "30", "60", "240", "1D"],
        "supports_group_request": False,
        "supports_marks": True,
        "supports_timescale_marks": True,
        "supports_time": True,
        "name": "Trading Signals",
    })
    try:
        pair = pair.upper()
        data = get_social_signal(pair)
        return jsonify({"status": "ok", "data": data})
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
