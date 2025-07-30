# ==============================================================================
# FILE: app/database.py
# ==============================================================================
# --- Description:
# Manages all SQLite database interactions: cache, watchlist, and API logs.

import sqlite3
import json
import time
from typing import Optional, Dict, Any, List
from app.config import settings
from app.models import WatchlistItem

DB_PATH = "jet_buddy_main.db"

def init_db():
    """ Initializes all required tables in the SQLite database. """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS analysis_cache (symbol TEXT PRIMARY KEY, data TEXT, timestamp REAL)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_symbol TEXT NOT NULL,
                normalized_symbol TEXT NOT NULL,
                email TEXT,
                UNIQUE(normalized_symbol, email)
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS api_usage_log (id INTEGER PRIMARY KEY, api_provider TEXT NOT NULL, timestamp REAL NOT NULL)")
        conn.commit()

def get_email_by_symbol(symbol: str) -> Optional[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM watchlist WHERE normalized_symbol = ?", (symbol,))
        row = cursor.fetchone()
        return row[0] if row else None

def add_to_watchlist(symbol: str, normalized: str, email: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO watchlist (user_symbol, normalized_symbol, email) VALUES (?, ?, ?)",
            (symbol, normalized, email)
        )
        conn.commit()
def remove_from_watchlist(symbol: str, email: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM watchlist WHERE user_symbol = ? AND email = ?",
            (symbol, email)
        )
        conn.commit()

def get_full_watchlist() -> List[WatchlistItem]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_symbol, normalized_symbol, email FROM watchlist")
        rows = cursor.fetchall()

    return [
        WatchlistItem(id=row[0], user_symbol=row[1], normalized_symbol=row[2], email=row[3])
        for row in rows
    ]

def get_unique_symbols_from_watchlist() -> List[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT normalized_symbol FROM watchlist")
        rows = cursor.fetchall()

    return [row[0] for row in rows]

# --- Cache, Watchlist, and API Log functions are unchanged ---
# (Omitted for brevity, they are identical to the previous response)
