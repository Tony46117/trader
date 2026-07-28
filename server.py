"""
╔══════════════════════════════════════════════════════════╗
║                   TRADER v2 — Server                    ║
╠══════════════════════════════════════════════════════════╣
║  Pure Python stdlib HTTP server (no Flask).             ║
║  Serves SPA + RESTful JSON API on a single port.        ║
║  Uses ThreadingHTTPServer for concurrent requests.      ║
╚══════════════════════════════════════════════════════════╝
"""
import os
import sys
import json
import time
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from functools import wraps
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PAIRS, CACHE_TTL, BASE_DIR
from services.market import get_current_prices
from services.signals import (
    generate_all_technical_signals, generate_unified_signal,
    generate_all_unified_signals, get_top_setups,
)
from services.analysis import get_cross_asset_analysis, get_market_regime
from providers.news import get_upcoming_events, get_all_news_signals, get_news_signal_for_pair
from providers.tick import get_tick_signal, get_all_tick_signals
from providers.cme import get_cme_signal, get_all_cme_signals
from providers.social import get_social_signal, get_all_social_signals
from models.state import signal_state_manager


# ── Threaded HTTP Server ──────────────────────────────────────────────

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads."""
    daemon_threads = True
    allow_reuse_address = True


# ── In-Memory Cache (thread-safe) ────────────────────────────────────

_cache = {}
_cache_lock = threading.Lock()


def cached(ttl=None):
    def decorator(f):
        @wraps(f)
        def wrapper(handler, *args, **kwargs):
            # Use only route params (kwargs) as cache key — skip handler instance
            key = f.__name__ + "|" + str(sorted(kwargs.items()))
            ttl_val = ttl or CACHE_TTL
            with _cache_lock:
                if key in _cache and time.time() - _cache[key][0] < ttl_val:
                    return _cache[key][1]
            result = f(handler, *args, **kwargs)
            with _cache_lock:
                _cache[key] = (time.time(), result)
            return result
        return wrapper
    return decorator


# ── Helpers ───────────────────────────────────────────────────────────

def json_response(data, status=200):
    """Return a JSON response."""
    body = json.dumps({"status": "ok", "data": data}, default=str, indent=2).encode("utf-8")
    return (status, {"Content-Type": "application/json; charset=utf-8"}, body)


def json_error(message, status=400):
    body = json.dumps({"status": "error", "message": str(message)}, default=str).encode("utf-8")
    return (status, {"Content-Type": "application/json; charset=utf-8"}, body)


def _load_spa():
    """Load the SPA index.html."""
    spa_path = os.path.join(BASE_DIR, "templates", "index.html")
    try:
        with open(spa_path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<html><body><h1>Trader Loading...</h1></body></html>"


_SPA_HTML = _load_spa()

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json",
}


def serve_static(handler, path):
    """Serve a static file from the static/ directory."""
    # Strip query string (e.g. ?v=3)
    if "?" in path:
        path = path.split("?")[0]
    static_dir = os.path.join(BASE_DIR, "static")
    filepath = os.path.normpath(os.path.join(static_dir, path))
    # Prevent path traversal
    if not filepath.startswith(os.path.normpath(static_dir)):
        return False
    if not os.path.isfile(filepath):
        return False

    _, ext = os.path.splitext(filepath)
    content_type = MIME_TYPES.get(ext, "application/octet-stream")

    try:
        with open(filepath, "rb") as f:
            data = f.read()
        handler._send_response(200, {"Content-Type": content_type}, data)
        return True
    except Exception:
        return False


# ── Route Table ───────────────────────────────────────────────────────
# Each entry: (method, path_pattern, handler_function)
# path_pattern can have <param> placeholders

def _match_route(method, path):
    """Match a request against the route table. Returns (handler, kwargs) or None."""
    parsed = urllib.parse.urlparse(path)
    clean_path = parsed.path.rstrip("/") or "/"
    query = urllib.parse.parse_qs(parsed.query)

    for route_method, route_pattern, handler in ROUTES:
        if route_method != method:
            continue

        # Split both into segments
        route_parts = route_pattern.strip("/").split("/") if route_pattern.strip("/") else []
        path_parts = clean_path.strip("/").split("/") if clean_path.strip("/") else []

        if len(route_parts) != len(path_parts):
            continue

        kwargs = {}
        match = True
        for rp, pp in zip(route_parts, path_parts):
            if rp.startswith("<") and rp.endswith(">"):
                kwargs[rp[1:-1]] = pp
            elif rp != pp:
                match = False
                break

        if match:
            return handler, kwargs, query

    return None, None, None


# ── Trader Request Handler ────────────────────────────────────────────

class TraderHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Trader API + SPA."""

    # Suppress default logging (we do our own)
    def log_message(self, format, *args):
        print(f"  {self.client_address[0]} - - [{datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] \"{args[0]}\" {args[1]} {args[2] if len(args) > 2 else '-'}")

    def _send_response(self, status, headers, body):
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            return self.rfile.read(content_length)
        return b""

    def do_OPTIONS(self):
        self._send_response(204, {}, b"")

    def do_GET(self):
        try:
            self._handle_request("GET")
        except Exception as e:
            print(f"  ⚠️  GET {self.path} — ERROR: {e}")
            status, headers, body = json_error(f"Internal server error: {e}", 500)
            self._send_response(status, headers, body)

    def do_POST(self):
        try:
            self._handle_request("POST")
        except Exception as e:
            print(f"  ⚠️  POST {self.path} — ERROR: {e}")
            status, headers, body = json_error(f"Internal server error: {e}", 500)
            self._send_response(status, headers, body)

    def _handle_request(self, method):
        path = self.path

        # ── Static files ──
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            if serve_static(self, rel_path):
                return
            self._send_response(*json_error("File not found", 404))
            return

        # ── API routes ──
        if path == "/api" or path.startswith("/api/"):
            handler, kwargs, query = _match_route(method, path)
            if handler:
                result = handler(self, **(kwargs or {}), **(query or {}))
                self._send_response(*result)
                return
            self._send_response(*json_error("Route not found", 404))
            return

        # ── SPA fallback ──
        html = _SPA_HTML.encode("utf-8")
        self._send_response(200, {"Content-Type": "text/html; charset=utf-8"}, html)


# ══════════════════════════════════════════════════════════════════════
#  API Route Handlers
# ══════════════════════════════════════════════════════════════════════


# ── Prices ──────────────────────────────────────────────────────────

@cached(ttl=15)
def _api_prices(handler, **kwargs):
    return json_response(get_current_prices())


# ── Market Overview ─────────────────────────────────────────────────

@cached(ttl=30)
def _api_market_overview(handler, **kwargs):
    prices = get_current_prices()
    unified = generate_all_unified_signals()
    overview = {}

    for pair_key in PAIRS:
        price_data = prices.get(pair_key, {})
        sig = unified.get(pair_key, {})
        uni = sig.get("unified", {}) if isinstance(sig, dict) else {}
        current = price_data.get("bid", 0)

        pair_info = PAIRS.get(pair_key, {})
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

    return json_response(overview)


# ── Unified Signals ─────────────────────────────────────────────────

@cached(ttl=30)
def _api_unified_signals(handler, **kwargs):
    return json_response(generate_all_unified_signals())


def _api_unified_signal_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    if pair not in PAIRS:
        return json_error(f"Invalid pair: {pair}", 404)
    return json_response(generate_unified_signal(pair))


# ── Technical Signals ───────────────────────────────────────────────

@cached(ttl=30)
def _api_technical_signals(handler, **kwargs):
    return json_response(generate_all_technical_signals())


# ── Top Setups ──────────────────────────────────────────────────────

@cached(ttl=30)
def _api_trading_setups(handler, min_score=None, max=None, **kwargs):
    min_score = int(min_score[0]) if min_score and isinstance(min_score, list) else (min_score or 55)
    max_results = int(max[0]) if max and isinstance(max, list) else (max or 5)
    if isinstance(min_score, str):
        min_score = int(min_score)
    if isinstance(max_results, str):
        max_results = int(max_results)
    return json_response(get_top_setups(min_score=int(min_score), max_results=int(max_results)))


# ── Active Signals ──────────────────────────────────────────────────

def _api_active_signals(handler, **kwargs):
    return json_response(signal_state_manager.get_all_active_signals())


def _api_active_signal_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    return json_response(signal_state_manager.get_active_signal(pair))


# ── Close Signal ────────────────────────────────────────────────────

def _api_close_signal(handler, pair=None, **kwargs):
    pair = pair.upper()
    try:
        body = handler._read_body()
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    reason = data.get("reason", "MANUAL_CLOSE")
    result = signal_state_manager.close_signal(pair, reason)
    if result:
        return json_response(result)
    return json_error(f"No active signal for {pair}", 404)


# ── Force New Signal ────────────────────────────────────────────────

def _api_force_new_signal(handler, pair=None, **kwargs):
    pair = pair.upper()
    signal_state_manager.force_new_signal(pair)
    return json_response({"message": f"Force-closed signal for {pair}"})


# ── Signal History ──────────────────────────────────────────────────

def _api_signal_history(handler, pair=None, limit=None, **kwargs):
    if pair:
        pair = pair.upper()
    limit = int(limit[0]) if limit and isinstance(limit, list) else (limit or 10)
    if isinstance(limit, str):
        limit = int(limit)
    return json_response(signal_state_manager.get_history(pair, int(limit)))


# ── Tick Signals ────────────────────────────────────────────────────

@cached(ttl=30)
def _api_tick_all(handler, **kwargs):
    prices = get_current_prices()
    return json_response(get_all_tick_signals(prices))


@cached(ttl=30)
def _api_tick_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    if pair not in PAIRS:
        return json_error(f"Invalid pair: {pair}", 404)
    prices = get_current_prices()
    price = prices.get(pair, {}).get("bid", 1.0)
    return json_response(get_tick_signal(pair, price))


# ── CME Signals ─────────────────────────────────────────────────────

@cached(ttl=60)
def _api_cme_all(handler, **kwargs):
    prices = get_current_prices()
    return json_response(get_all_cme_signals(prices))


@cached(ttl=60)
def _api_cme_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    if pair not in PAIRS:
        return json_error(f"Invalid pair: {pair}", 404)
    prices = get_current_prices()
    price = prices.get(pair, {}).get("bid", 1.0)
    return json_response(get_cme_signal(pair, price))


# ── Social Signals ──────────────────────────────────────────────────

@cached(ttl=120)
def _api_social_all(handler, **kwargs):
    return json_response(get_all_social_signals())


@cached(ttl=120)
def _api_social_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    if pair not in PAIRS:
        return json_error(f"Invalid pair: {pair}", 404)
    return json_response(get_social_signal(pair))


# ── News ────────────────────────────────────────────────────────────

@cached(ttl=60)
def _api_upcoming_news(handler, hours=None, **kwargs):
    hours = int(hours[0]) if hours and isinstance(hours, list) else (hours or 72)
    if isinstance(hours, str):
        hours = int(hours)
    events = get_upcoming_events(hours_ahead=int(hours))
    return json_response(events)


@cached(ttl=60)
def _api_news_signals(handler, **kwargs):
    return json_response(get_all_news_signals())


@cached(ttl=60)
def _api_news_signal_pair(handler, pair=None, **kwargs):
    pair = pair.upper()
    if pair not in PAIRS:
        return json_error(f"Invalid pair: {pair}", 404)
    return json_response(get_news_signal_for_pair(pair))


# ── Analysis ────────────────────────────────────────────────────────

@cached(ttl=60)
def _api_cross_asset(handler, **kwargs):
    return json_response(get_cross_asset_analysis())


@cached(ttl=60)
def _api_market_regime(handler, **kwargs):
    return json_response(get_market_regime())


# ══════════════════════════════════════════════════════════════════════
#  Route Table
# ══════════════════════════════════════════════════════════════════════

ROUTES = [
    # Prices
    ("GET", "/api/prices", _api_prices),

    # Market overview
    ("GET", "/api/market/overview", _api_market_overview),

    # Unified signals
    ("GET", "/api/signals/unified", _api_unified_signals),
    ("GET", "/api/signals/unified/<pair>", _api_unified_signal_pair),

    # Technical signals
    ("GET", "/api/signals/technical", _api_technical_signals),

    # Top setups
    ("GET", "/api/signals/setups", _api_trading_setups),

    # Active signals
    ("GET", "/api/signals/active", _api_active_signals),
    ("GET", "/api/signals/active/<pair>", _api_active_signal_pair),

    # Close / force signals
    ("POST", "/api/signals/close/<pair>", _api_close_signal),
    ("POST", "/api/signals/force/<pair>", _api_force_new_signal),

    # Signal history
    ("GET", "/api/signals/history", _api_signal_history),
    ("GET", "/api/signals/history/<pair>", _api_signal_history),

    # Tick signals
    ("GET", "/api/tick", _api_tick_all),
    ("GET", "/api/tick/<pair>", _api_tick_pair),

    # CME signals
    ("GET", "/api/cme", _api_cme_all),
    ("GET", "/api/cme/<pair>", _api_cme_pair),

    # Social signals
    ("GET", "/api/social", _api_social_all),
    ("GET", "/api/social/<pair>", _api_social_pair),

    # News
    ("GET", "/api/news/upcoming", _api_upcoming_news),
    ("GET", "/api/news/signals", _api_news_signals),
    ("GET", "/api/news/signals/<pair>", _api_news_signal_pair),

    # Analysis
    ("GET", "/api/analysis/cross-asset", _api_cross_asset),
    ("GET", "/api/analysis/regime", _api_market_regime),
]


# ── Helpers from app.py that are still needed ──────────────────────────

def _check_cpp():
    """Check and print C++ indicator status."""
    try:
        from services.indicators import _INDICATORS_CPP
        if _INDICATORS_CPP:
            print("  ⚡ C++ indicators: ACCELERATED")
        else:
            print("  ⚡ C++ indicators: pure Python")
    except Exception:
        print("  ⚡ C++ indicators: pure Python")


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Clean stale signal state
    signal_state_manager.reset()

    server = ThreadedHTTPServer(("0.0.0.0", port), TraderHandler)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                   TRADER v2                             ║
║          Forex Trading Signal Framework                 ║
╠══════════════════════════════════════════════════════════╣
║  Pairs: EURUSD, GBPUSD, XAUUSD, BTCUSD, ETHUSD         ║
║  Min RR: 1:2  •  Cache: {str(CACHE_TTL)+'s':>7}  •  5-Source Fusion        ║
║  Features: Live Prices · Signals · Analysis · CME       ║
║  Server:  Pure stdlib (no Flask)                       ║
╠══════════════════════════════════════════════════════════╣
║  🌐  http://localhost:{port}                               ║
╚══════════════════════════════════════════════════════════╝
""")

    _check_cpp()
    print(f"  🚀  Server started on port {port} (Ctrl+C to stop)")
    print(f"  📋  Logs:\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  🛑  Server stopped.")
        server.server_close()
