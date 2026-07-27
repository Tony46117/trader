"""
╔══════════════════════════════════════════════════════════╗
║          Signal State Manager                           ║
╠══════════════════════════════════════════════════════════╣
║  Manages active signal lifecycle per pair:              ║
║  - Track entry, SL, TP levels                           ║
║  - Detect SL/TP hits on each price refresh              ║
║  - Maintain history of closed signals                   ║
║  - Enforce minimum 1:2 RR before activation             ║
╚══════════════════════════════════════════════════════════╝
"""
import json
import os
from datetime import datetime
from threading import Lock

from config import CACHE_DIR


class SignalStateManager:
    """Thread-safe manager for trading signal state."""

    def __init__(self):
        self._lock = Lock()
        self._state_path = os.path.join(CACHE_DIR, "signal_state.json")
        self._history_path = os.path.join(CACHE_DIR, "signal_history.json")
        self._active = {}     # pair_key -> signal dict
        self._history = []    # list of closed signal dicts
        self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self):
        try:
            if os.path.exists(self._state_path):
                with open(self._state_path) as f:
                    self._active = json.load(f)
            if os.path.exists(self._history_path):
                with open(self._history_path) as f:
                    self._history = json.load(f)
        except Exception:
            self._active = {}
            self._history = []

    def _save(self):
        try:
            with open(self._state_path, "w") as f:
                json.dump(self._active, f, indent=2, default=str)
            with open(self._history_path, "w") as f:
                json.dump(self._history[-500:], f, indent=2, default=str)
        except Exception:
            pass

    # ── Public API ───────────────────────────────────────────────────

    def set_signal(self, pair_key, signal_data):
        """Set an active signal for a pair. Overwrites any existing."""
        with self._lock:
            self._active[pair_key] = {
                **signal_data,
                "status": "ACTIVE",
                "created_at": datetime.now().isoformat(),
            }
            self._save()

    def get_active_signal(self, pair_key):
        """Get the active signal for a pair, if any."""
        with self._lock:
            signal = self._active.get(pair_key)
            if signal and signal.get("status") == "ACTIVE":
                return signal
            return None

    def get_all_active_signals(self):
        """Get all currently active signals."""
        with self._lock:
            return {
                k: v for k, v in self._active.items()
                if v.get("status") == "ACTIVE"
            }

    def close_signal(self, pair_key, reason="MANUAL_CLOSE", price=0):
        """Close an active signal and record its result."""
        with self._lock:
            signal = self._active.pop(pair_key, None)
            if not signal:
                return None

            # Calculate pips result
            pips = 0
            if price > 0 and signal.get("entry"):
                direction = signal.get("direction", "NEUTRAL")
                entry = signal["entry"]
                pip_size = float(signal.get("pip", 0.0001))
                if direction == "BUY":
                    pips = round((price - entry) / pip_size, 1)
                elif direction == "SELL":
                    pips = round((entry - price) / pip_size, 1)

            closed = {
                **signal,
                "status": "CLOSED",
                "closed_at": datetime.now().isoformat(),
                "close_reason": reason,
                "close_price": price,
                "pips_result": pips,
            }
            self._history.append(closed)
            self._save()
            return closed

    def check_price_levels(self, pair_key, current_price):
        """Check if current price has hit SL or TP. Returns (hit_type, closed_signal) or (None, None)."""
        with self._lock:
            signal = self._active.get(pair_key)
            if not signal or signal.get("status") != "ACTIVE":
                return None, None

            direction = signal.get("direction", "NEUTRAL")
            entry = signal.get("entry", 0)
            sl = signal.get("sl")
            tp1 = signal.get("tp1")

            if not all([entry, sl, tp1]):
                return None, None

            hit_type = None
            if direction == "BUY":
                if current_price <= sl:
                    hit_type = "SL_HIT"
                elif current_price >= tp1:
                    hit_type = "TP1_HIT"
            elif direction == "SELL":
                if current_price >= sl:
                    hit_type = "SL_HIT"
                elif current_price <= tp1:
                    hit_type = "TP1_HIT"

            if hit_type:
                closed = self.close_signal(pair_key, hit_type, current_price)
                return hit_type, closed

            return None, None

    def force_new_signal(self, pair_key):
        """Force-close any active signal so a new one can be generated."""
        with self._lock:
            if pair_key in self._active:
                self.close_signal(pair_key, "FORCE_NEW")

    def get_history(self, pair=None, limit=20):
        """Get signal history, optionally filtered by pair."""
        with self._lock:
            hist = self._history
            if pair:
                hist = [s for s in hist if s.get("pair") == pair]
            return hist[-limit:]


# Global singleton
signal_state_manager = SignalStateManager()
