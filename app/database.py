# ==============================================================================
# FILE: app/database.py
# ==============================================================================
# --- Description:
# Manages all PostgreSQL database interactions: cache, watchlist, and API logs.

import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List
from app.config import settings
from app.models import WatchlistItem

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
def init_db():
    """Initializes all required tables in the PostgreSQL database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                symbol TEXT PRIMARY KEY,
                data TEXT,
                timestamp REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id SERIAL PRIMARY KEY,
                user_symbol TEXT NOT NULL,
                normalized_symbol TEXT NOT NULL,
                email TEXT,
                UNIQUE(normalized_symbol, email)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_log (
                id SERIAL PRIMARY KEY,
                api_provider TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()

def get_emails_for_symbol(symbol: str) -> List[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM watchlist WHERE normalized_symbol = %s", (symbol,))
        rows = cursor.fetchall()
        return [row["email"] for row in rows]

def add_to_watchlist(symbol: str, normalized: str, email: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO watchlist (user_symbol, normalized_symbol, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (normalized_symbol, email) DO NOTHING
        """, (symbol, normalized, email))
        conn.commit()

def remove_from_watchlist(symbol: str, email: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE user_symbol = %s AND email = %s", (symbol, email))
        conn.commit()

def get_full_watchlist() -> List[WatchlistItem]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_symbol, normalized_symbol, email FROM watchlist")
        rows = cursor.fetchall()
        return [
            WatchlistItem(
                id=row["id"],
                user_symbol=row["user_symbol"],
                normalized_symbol=row["normalized_symbol"],
                email=row["email"]
            )
            for row in rows
        ]

def get_unique_symbols_from_watchlist() -> List[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT normalized_symbol FROM watchlist")
        rows = cursor.fetchall()
        return [row["normalized_symbol"] for row in rows]

def log_api_call(api_provider: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO api_usage_log (api_provider, timestamp) VALUES (%s, %s)",
            (api_provider, time.time())
        )
        conn.commit()

def get_api_calls_in_last_minute(api_provider: str) -> int:
    one_minute_ago = time.time() - 60
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM api_usage_log WHERE api_provider = %s AND timestamp > %s",
            (api_provider, one_minute_ago)
        )
        result = cursor.fetchone()
        return result["count"] if result else 0
