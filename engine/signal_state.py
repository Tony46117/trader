"""Signal State Manager — Tracks one active signal per pair until SL/TP hit.

Maintains persistent signal state across refreshes:
- Only one signal per pair at a time
- Signal persists until price hits SL (invalidated) or TP1 (validated)
- Once invalidated/validated, a new signal can be generated
"""

import threading
import time
from datetime import datetime


class SignalState:
    """Represents an active signal for a pair."""

    def __init__(self, pair, direction, entry, sl, tp1, tp2, tp3, rr1, score, confidence, verdict):
        self.pair = pair
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp1 = tp1
        self.tp2 = tp2
        self.tp3 = tp3
        self.rr1 = rr1
        self.score = score
        self.confidence = confidence
        self.verdict = verdict
        self.status = "ACTIVE"  # ACTIVE, HIT_SL, HIT_TP1, HIT_TP2, HIT_TP3, MANUAL_CLOSE
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.closed_at = None
        self.pips_result = 0.0

    def to_dict(self):
        return {
            "pair": self.pair,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "rr1": self.rr1,
            "score": self.score,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "status": self.status,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "pips_result": self.pips_result,
        }


class SignalStateManager:
    """Manages active signals for all pairs. Thread-safe singleton."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_signals = {}   # pair -> SignalState
        self._signal_history = {}   # pair -> list of closed SignalState
        self._max_history = 20

    def has_active_signal(self, pair):
        """Check if a pair has an active signal."""
        with self._lock:
            sig = self._active_signals.get(pair)
            return sig is not None and sig.status == "ACTIVE"

    def get_active_signal(self, pair):
        """Get the active signal for a pair, or None."""
        with self._lock:
            sig = self._active_signals.get(pair)
            if sig and sig.status == "ACTIVE":
                return sig.to_dict()
            return None

    def get_all_active_signals(self):
        """Get all active signals across all pairs."""
        with self._lock:
            return {pair: sig.to_dict() for pair, sig in self._active_signals.items() if sig.status == "ACTIVE"}

    def set_active_signal(self, pair, direction, entry, sl, tp1, tp2, tp3, rr1, score, confidence, verdict):
        """Set a new active signal for a pair. Only if no active signal exists."""
        with self._lock:
            existing = self._active_signals.get(pair)
            if existing and existing.status == "ACTIVE":
                return False  # Already have an active signal

            signal = SignalState(pair, direction, entry, sl, tp1, tp2, tp3, rr1, score, confidence, verdict)
            self._active_signals[pair] = signal
            return True

    def check_price_levels(self, pair, current_price, pip_size):
        """Check if current price hits SL or TP for active signal.

        Returns (hit_type, signal_data) or (None, None) if no hit.
        """
        with self._lock:
            sig = self._active_signals.get(pair)
            if not sig or sig.status != "ACTIVE":
                return None, None

            hit_type = None

            if sig.direction == "BUY":
                # Check SL hit (price dropped to/below SL)
                if current_price <= sig.sl:
                    hit_type = "HIT_SL"
                    sig.pips_result = round((sig.sl - sig.entry) / pip_size, 1)
                # Check TP1 hit (price rose to/above TP1)
                elif current_price >= sig.tp1:
                    hit_type = "HIT_TP1"
                    sig.pips_result = round((sig.tp1 - sig.entry) / pip_size, 1)
                # Check TP2
                elif sig.tp2 and current_price >= sig.tp2:
                    hit_type = "HIT_TP2"
                    sig.pips_result = round((sig.tp2 - sig.entry) / pip_size, 1)
                # Check TP3
                elif sig.tp3 and current_price >= sig.tp3:
                    hit_type = "HIT_TP3"
                    sig.pips_result = round((sig.tp3 - sig.entry) / pip_size, 1)

            elif sig.direction == "SELL":
                # Check SL hit (price rose to/above SL)
                if current_price >= sig.sl:
                    hit_type = "HIT_SL"
                    sig.pips_result = round((sig.entry - sig.sl) / pip_size, 1)
                # Check TP1 hit (price dropped to/below TP1)
                elif current_price <= sig.tp1:
                    hit_type = "HIT_TP1"
                    sig.pips_result = round((sig.entry - sig.tp1) / pip_size, 1)
                # Check TP2
                elif sig.tp2 and current_price <= sig.tp2:
                    hit_type = "HIT_TP2"
                    sig.pips_result = round((sig.entry - sig.tp2) / pip_size, 1)
                # Check TP3
                elif sig.tp3 and current_price <= sig.tp3:
                    hit_type = "HIT_TP3"
                    sig.pips_result = round((sig.entry - sig.tp3) / pip_size, 1)

            if hit_type:
                sig.status = hit_type
                sig.closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Move to history
                if pair not in self._signal_history:
                    self._signal_history[pair] = []
                self._signal_history[pair].insert(0, sig)
                # Trim history
                if len(self._signal_history[pair]) > self._max_history:
                    self._signal_history[pair] = self._signal_history[pair][:self._max_history]
                # Remove from active
                del self._active_signals[pair]
                return hit_type, sig.to_dict()

            return None, None

    def close_signal(self, pair, reason="MANUAL_CLOSE"):
        """Manually close an active signal."""
        with self._lock:
            sig = self._active_signals.get(pair)
            if not sig or sig.status != "ACTIVE":
                return None

            sig.status = reason
            sig.closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if pair not in self._signal_history:
                self._signal_history[pair] = []
            self._signal_history[pair].insert(0, sig)
            if len(self._signal_history[pair]) > self._max_history:
                self._signal_history[pair] = self._signal_history[pair][:self._max_history]
            del self._active_signals[pair]
            return sig.to_dict()

    def get_history(self, pair=None, limit=10):
        """Get signal history for a pair or all pairs."""
        with self._lock:
            if pair:
                history = self._signal_history.get(pair, [])
                return [s.to_dict() for s in history[:limit]]
            else:
                result = {}
                for p, hist in self._signal_history.items():
                    result[p] = [s.to_dict() for s in hist[:limit]]
                return result

    def force_new_signal(self, pair):
        """Force-close any active signal to allow a new one."""
        with self._lock:
            sig = self._active_signals.get(pair)
            if sig and sig.status == "ACTIVE":
                sig.status = "FORCE_CLOSED"
                sig.closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if pair not in self._signal_history:
                    self._signal_history[pair] = []
                self._signal_history[pair].insert(0, sig)
                del self._active_signals[pair]
                return True
            return False


# Global singleton
signal_state_manager = SignalStateManager()
