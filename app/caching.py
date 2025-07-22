# ==============================================================================
# FILE: app/caching.py
# ==============================================================================
# --- Description:
# A simple caching mechanism using Python's built-in SQLite3.
# This is lightweight, serverless, and ideal for the Render free tier,
# avoiding the need for a separate Redis instance.

import sqlite3
import json
import time
from typing import Optional, Dict, Any

DB_PATH = "jet_buddy_cache.db"

def init_cache():
    """Initializes the SQLite database and creates the cache table if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                symbol TEXT PRIMARY KEY,
                data TEXT,
                timestamp REAL
            )
        """)
        conn.commit()

def set_cached_analysis(symbol: str, data: Dict[str, Any]):
    """Stores the analysis result for a given symbol in the cache."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO analysis_cache (symbol, data, timestamp) VALUES (?, ?, ?)",
            (symbol.upper(), json.dumps(data), time.time())
        )
        conn.commit()

def get_cached_analysis(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest analysis result for a symbol from the cache."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM analysis_cache WHERE symbol = ?", (symbol.upper(),))
        result = cursor.fetchone()
        return json.loads(result[0]) if result else None
