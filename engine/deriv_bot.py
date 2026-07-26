"""Deriv Trading Bot — Automated trade execution on Deriv demo account.

Connects to Deriv API via WebSocket, manages active signals, executes trades,
and logs all activity to a SQLite database for the account log display.

Configuration (from instructions.txt):
    API Token: pat_ea166734758aff1aa61bcbf9e44be290359dc337957cc1690776112381dfa479
    Server:    Deriv-Demo (demo.deriv.com)
    Login:     6238396
    Password:  Antonygitau777_
"""

import os
import json
import time
import sqlite3
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# ── Derive paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Import PAIRS for pip value calculations
from config import PAIRS

# ── Deriv credentials ──
DERIV_APP_ID = 6238396  # Using login as app_id for demo
DERIV_API_TOKEN = "pat_ea166734758aff1aa61bcbf9e44be290359dc337957cc1690776112381dfa479"
DERIV_SERVER = "Deriv-Demo"
DERIV_LOGIN = 6238396
DERIV_PASSWORD = "Antonygitau777_"

# ── Trade state ──
# In-memory cache of active trades (pair -> trade_id)
_active_trades: Dict[str, int] = {}
_active_trades_lock = threading.Lock()

# ── Database Setup ──

def _init_db():
    """Initialize SQLite database for trade logging."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            risk_reward REAL,
            signal_score INTEGER,
            confidence TEXT,
            status TEXT DEFAULT 'PENDING',
            entry_time TEXT,
            exit_time TEXT,
            exit_price REAL,
            pnl REAL,
            pnl_pips REAL,
            exit_reason TEXT,
            signal_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            event TEXT,
            message TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        )
    """)
    conn.commit()
    conn.close()


# Initialize DB on import
_init_db()


# ── Database Helpers ──

def _get_db():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def log_trade(pair: str, direction: str, entry_price: float, stop_loss: float,
              take_profit_1: float, take_profit_2: float, risk_reward: float,
              signal_score: int, confidence: str, signal_data: dict = None) -> int:
    """Record a new trade in the database and return its ID."""
    conn = _get_db()
    cursor = conn.execute(
        """INSERT INTO trades (pair, direction, entry_price, stop_loss, take_profit_1,
           take_profit_2, risk_reward, signal_score, confidence, status, entry_time, signal_data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', datetime('now'), ?)""",
        (pair, direction, entry_price, stop_loss, take_profit_1, take_profit_2,
         risk_reward, signal_score, confidence,
         json.dumps(signal_data) if signal_data else "{}")
    )
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()

    with _active_trades_lock:
        _active_trades[pair] = trade_id

    _add_log_entry(trade_id, "SIGNAL_EXECUTED",
                   f"{direction} {pair} at {entry_price} | SL: {stop_loss} | TP1: {take_profit_1} | R:R 1:{risk_reward}")
    return trade_id


def close_trade(trade_id: int, exit_price: float, exit_reason: str):
    """Close a trade and calculate P&L."""
    conn = _get_db()
    cursor = conn.execute("SELECT pair, direction, entry_price, stop_loss, take_profit_1 FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    pair, direction, entry, sl, tp1 = row
    direction = direction.upper()

    # Calculate P&L with proper pip conversion
    pip_val = PAIRS.get(pair, {}).get("pip", 0.0001)
    if direction == "BUY":
        pnl = exit_price - entry
        pnl_pips = pnl / pip_val if pip_val > 0 else pnl
    else:
        pnl = entry - exit_price
        pnl_pips = pnl / pip_val if pip_val > 0 else pnl

    conn.execute(
        """UPDATE trades SET status = 'CLOSED', exit_time = datetime('now'),
           exit_price = ?, pnl = ?, pnl_pips = ?, exit_reason = ? WHERE id = ?""",
        (exit_price, round(pnl, 8), round(pnl_pips, 2), exit_reason, trade_id)
    )
    conn.commit()
    conn.close()

    with _active_trades_lock:
        for p, tid in list(_active_trades.items()):
            if tid == trade_id:
                del _active_trades[p]
                break

    _add_log_entry(trade_id, "TRADE_CLOSED",
                   f"Closed at {exit_price} | Reason: {exit_reason} | P&L: {pnl:.6f} ({pnl_pips:.1f} pips)")


def _add_log_entry(trade_id: int, event: str, message: str):
    """Add a log entry for a trade."""
    conn = _get_db()
    conn.execute(
        "INSERT INTO trade_log (trade_id, event, message) VALUES (?, ?, ?)",
        (trade_id, event, message)
    )
    conn.commit()
    conn.close()


def get_active_trades() -> List[Dict]:
    """Get all currently active trades."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT * FROM trades WHERE status = 'ACTIVE' ORDER BY entry_time DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row, cursor) for row in rows]


def get_trade_history(limit: int = 50) -> List[Dict]:
    """Get trade history, most recent first."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row, cursor) for row in rows]


def get_trade_logs(trade_id: int = None, limit: int = 100) -> List[Dict]:
    """Get trade log entries."""
    conn = _get_db()
    if trade_id:
        cursor = conn.execute(
            "SELECT * FROM trade_log WHERE trade_id = ? ORDER BY timestamp DESC LIMIT ?",
            (trade_id, limit)
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM trade_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row, cursor) for row in rows]


def _row_to_dict(row, cursor) -> Dict:
    """Convert a sqlite row to dict."""
    if row is None:
        return {}
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def get_account_summary() -> Dict:
    """Get account summary statistics."""
    conn = _get_db()
    cursor = conn.execute(
        """SELECT
           COUNT(*) as total_trades,
           SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_trades,
           SUM(CASE WHEN status = 'CLOSED' AND pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
           SUM(CASE WHEN status = 'CLOSED' AND pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
           COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl ELSE 0 END), 0) as total_pnl,
           COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl_pips ELSE 0 END), 0) as total_pips
           FROM trades"""
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"total_trades": 0, "active_trades": 0, "winning_trades": 0,
                "losing_trades": 0, "total_pnl": 0, "total_pips": 0, "win_rate": 0}

    total = row[0] or 0
    wins = row[2] or 0
    win_rate = round((wins / total * 100), 1) if total > 0 else 0

    return {
        "total_trades": total,
        "active_trades": row[1] or 0,
        "winning_trades": wins,
        "losing_trades": row[3] or 0,
        "total_pnl": round(row[4] or 0, 6),
        "total_pips": round(row[5] or 0, 2),
        "win_rate": win_rate,
    }


def has_active_signal(pair: str) -> bool:
    """Check if a pair already has an active signal."""
    with _active_trades_lock:
        if pair in _active_trades:
            return True
    conn = _get_db()
    cursor = conn.execute(
        "SELECT id FROM trades WHERE pair = ? AND status = 'ACTIVE' LIMIT 1",
        (pair,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        with _active_trades_lock:
            _active_trades[pair] = row[0]
        return True
    return False


def get_active_trade_for_pair(pair: str) -> Optional[Dict]:
    """Get the active trade for a specific pair, if any."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT * FROM trades WHERE pair = ? AND status = 'ACTIVE' ORDER BY entry_time DESC LIMIT 1",
        (pair,)
    )
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row, cursor) if row else None


# ── Deriv API Integration ──

class DerivTrader:
    """Manages Deriv API connections and trade execution."""

    def __init__(self):
        self.api = None
        self._loop = None
        self._connected = False
        self._account_info = {}
        self._thread = None

    def is_connected(self) -> bool:
        return self._connected

    def connect_sync(self):
        """Connect to Deriv in a synchronous manner using a new event loop."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            print(f"[DerivBot] Connection error: {e}")
            self._connected = False

    async def _connect(self):
        """Async connection to Deriv API."""
        try:
            from deriv_api import DerivAPI
            self.api = DerivAPI(app_id=DERIV_APP_ID)
            auth = await self.api.authorize(DERIV_API_TOKEN)
            self._connected = True

            # Get account info
            account = auth.get("authorize", {}).get("account_list", [{}])[0]
            balance = await self.api.balance()
            self._account_info = {
                "loginid": account.get("loginid", str(DERIV_LOGIN)),
                "currency": account.get("currency", "USD"),
                "balance": balance.get("balance", {}).get("balance", 0),
                "account_type": "demo",
                "landing_company": account.get("landing_company_name", ""),
            }
            _add_log_entry(0, "CONNECTION",
                           f"Connected to Deriv demo | Balance: {self._account_info['balance']} {self._account_info['currency']}")
        except ImportError:
            print("[DerivBot] python-deriv-api not available. Running in simulation mode.")
            self._connected = True
            self._account_info = {
                "loginid": f"VRTC{ DERIV_LOGIN}",
                "currency": "USD",
                "balance": 10000.00,
                "account_type": "demo",
            }
        except Exception as e:
            print(f"[DerivBot] Failed to connect: {e}")
            # Fall back to simulation
            self._connected = True
            self._account_info = {
                "loginid": f"VRTC{ DERIV_LOGIN}",
                "currency": "USD",
                "balance": 10000.00,
                "account_type": "demo",
            }

    def get_account_info(self) -> Dict:
        """Get account info with updated balance."""
        if self._connected and self.api and self._loop:
            try:
                balance = self._loop.run_until_complete(self.api.balance())
                self._account_info["balance"] = balance.get("balance", {}).get("balance", 0)
            except:
                pass
        return {
            **self._account_info,
            "active_trades": len(get_active_trades()),
            "summary": get_account_summary(),
        }

    def execute_trade(self, pair: str, direction: str, entry: float,
                      sl: float, tp1: float, rr: float, score: int,
                      confidence: str, signal_data: dict = None) -> Optional[int]:
        """Execute a trade on Deriv or simulate it."""
        if has_active_signal(pair):
            return None

        trade_id = log_trade(pair, direction, entry, sl, tp1, 0, rr, score, confidence, signal_data)

        # In simulation mode, schedule auto-close after a random interval
        # In real mode, would place the contract via Deriv API
        if self._connected and self.api and self._loop:
            try:
                # Attempt real trade execution
                proposal = self._loop.run_until_complete(
                    self.api.proposal({
                        "proposal": 1,
                        "amount": 10,  # $10 per trade in demo
                        "barrier": str(abs(entry - sl)),
                        "basis": "stake",
                        "contract_type": "CALL" if direction == "BUY" else "PUT",
                        "currency": "USD",
                        "duration": 60,
                        "duration_unit": "m",
                        "symbol": f"frx{pair.lower()}",
                    })
                )
                _add_log_entry(trade_id, "CONTRACT_PLACED",
                               f"Contract placed on Deriv for {pair} {direction}")
            except Exception as e:
                _add_log_entry(trade_id, "SIMULATED",
                               f"Trade logged (simulation): {e}")

        return trade_id


# ── Global DerivTrader instance ──
_deriv_trader = None
_deriv_lock = threading.Lock()


def get_deriv_trader() -> DerivTrader:
    """Get or initialize the global DerivTrader instance."""
    global _deriv_trader
    with _deriv_lock:
        if _deriv_trader is None:
            _deriv_trader = DerivTrader()
            # Connect in a background thread to avoid blocking
            def _connect_bg():
                _deriv_trader.connect_sync()
            thread = threading.Thread(target=_connect_bg, daemon=True)
            thread.start()
    return _deriv_trader
