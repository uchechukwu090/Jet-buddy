# ==============================================================================
# FILE: app/database.py
# ==============================================================================
# Database operations for API call logging and rate limiting

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading

# Thread-safe database connection
_local = threading.local()

def get_db_connection():
    """Get thread-local database connection"""
    if not hasattr(_local, 'connection'):
        db_path = os.getenv('DB_PATH', 'jetbuddy.db')
        _local.connection = sqlite3.connect(db_path, check_same_thread=False)
        _local.connection.row_factory = sqlite3.Row
        init_database(_local.connection)
    return _local.connection

def init_database(conn: sqlite3.Connection):
    """Initialize database tables"""
    cursor = conn.cursor()
    
    # API calls logging table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            endpoint TEXT,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
    ''')
    
    # Watchlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            asset_class TEXT DEFAULT 'stock',
            added_at DATETIME NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Analysis results cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            interval_type TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            analysis_data TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_calls_provider_timestamp ON api_calls(provider, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_cache_lookup ON analysis_cache(symbol, interval_type, asset_class, expires_at)')
    
    conn.commit()

def log_api_call(provider: str, endpoint: str = None, success: bool = True, error_message: str = None):
    """Log an API call for rate limiting purposes"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_calls (provider, timestamp, endpoint, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (provider, datetime.utcnow(), endpoint, success, error_message))
        
        conn.commit()
    except Exception as e:
        print(f"Error logging API call: {e}")

def get_api_calls_in_last_minute(provider: str) -> int:
    """Get the number of API calls made in the last minute for a provider"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM api_calls
            WHERE provider = ? AND timestamp > ?
        ''', (provider, one_minute_ago))
        
        result = cursor.fetchone()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error getting API call count: {e}")
        return 0

def cleanup_old_api_calls():
    """Clean up API call logs older than 24 hours"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        cursor.execute('''
            DELETE FROM api_calls
            WHERE timestamp < ?
        ''', (twenty_four_hours_ago,))
        
        conn.commit()
        print(f"Cleaned up {cursor.rowcount} old API call records")
    except Exception as e:
        print(f"Error cleaning up API calls: {e}")

def add_to_watchlist(symbol: str, asset_class: str = 'stock') -> bool:
    """Add a symbol to the watchlist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO watchlist (symbol, asset_class, added_at, is_active)
            VALUES (?, ?, ?, TRUE)
        ''', (symbol.upper(), asset_class, datetime.utcnow()))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding to watchlist: {e}")
        return False

def remove_from_watchlist(symbol: str) -> bool:
    """Remove a symbol from the watchlist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE watchlist 
            SET is_active = FALSE
            WHERE symbol = ?
        ''', (symbol.upper(),))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error removing from watchlist: {e}")
        return False

def get_watchlist() -> List[Dict]:
    """Get all active watchlist items"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, asset_class, added_at
            FROM watchlist
            WHERE is_active = TRUE
            ORDER BY added_at DESC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting watchlist: {e}")
        return []

def cache_analysis_result(symbol: str, interval_type: str, asset_class: str, analysis_data: str, ttl_minutes: int = 15):
    """Cache analysis result with TTL"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        
        cursor.execute('''
            INSERT OR REPLACE INTO analysis_cache 
            (symbol, interval_type, asset_class, analysis_data, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol.upper(), interval_type, asset_class, analysis_data, datetime.utcnow(), expires_at))
        
        conn.commit()
    except Exception as e:
        print(f"Error caching analysis: {e}")

def get_cached_analysis(symbol: str, interval_type: str, asset_class: str) -> Optional[str]:
    """Get cached analysis result if not expired"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT analysis_data
            FROM analysis_cache
            WHERE symbol = ? AND interval_type = ? AND asset_class = ? 
            AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (symbol.upper(), interval_type, asset_class, datetime.utcnow()))
        
        result = cursor.fetchone()
        return result['analysis_data'] if result else None
    except Exception as e:
        print(f"Error getting cached analysis: {e}")
        return None

def cleanup_expired_cache():
    """Clean up expired cache entries"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM analysis_cache
            WHERE expires_at < ?
        ''', (datetime.utcnow(),))
        
        conn.commit()
        print(f"Cleaned up {cursor.rowcount} expired cache entries")
    except Exception as e:
        print(f"Error cleaning up cache: {e}")

# Initialize database on import
try:
    init_database(get_db_connection())
except Exception as e:
    print(f"Error initializing database: {e}")
