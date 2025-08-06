# ==============================================================================
# FILE: app/caching.py
# ==============================================================================
# --- Description:
# A caching mechanism using PostgreSQL via Neon.

import json
import time
from typing import Optional, Dict, Any
from app.database import get_connection

def init_cache():
    """Initializes the PostgreSQL cache table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            symbol TEXT PRIMARY KEY,
            data TEXT,
            timestamp REAL
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def set_cached_analysis(symbol: str, data: Dict[str, Any]):
    """Stores the analysis result for a given symbol in the cache."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analysis_cache (symbol, data, timestamp) VALUES (%s, %s, %s) "
        "ON CONFLICT (symbol) DO UPDATE SET data = EXCLUDED.data, timestamp = EXCLUDED.timestamp",
        (symbol.upper(), json.dumps(data), time.time())
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_cached_analysis(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest analysis result for a symbol from the cache."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM analysis_cache WHERE symbol = %s", (symbol.upper(),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return json.loads(result[0]) if result else None
