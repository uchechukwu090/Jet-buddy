# ==============================================================================
# FILE: app/database.py
# ==============================================================================
# --- Description:
# Manages all SQLite database interactions: cache, watchlist, and API logs.

import sqlite3
import json
import time
from typing import Optional, Dict, Any, List
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

# --- Cache, Watchlist, and API Log functions are unchanged ---
# (Omitted for brevity, they are identical to the previous response)
