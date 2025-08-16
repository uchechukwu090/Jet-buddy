# ==============================================================================
# FILE: app/database.py - POSTGRES/NEON VERSION
# ==============================================================================
# Database operations using SQLAlchemy with Postgres (Neon)

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for local development (you can use local postgres or sqlite)
    DATABASE_URL = "postgresql://localhost/trading_analysis"
    print("Warning: DATABASE_URL not set, using default local postgres")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Helps with connection drops
    pool_recycle=300,    # Recycle connections every 5 minutes
    echo=False           # Set to True for SQL logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class Watchlist(Base):
    __tablename__ = "watchlist"
    
    symbol = Column(String(20), primary_key=True)
    asset_class = Column(String(10), nullable=False, default="stock")
    added_at = Column(DateTime, default=datetime.utcnow)

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    result_data = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class APICall(Base):
    __tablename__ = "api_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

# Database initialization
def init_db():
    """Create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

# Database session context manager
def get_db_session():
    """Get database session with proper cleanup"""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

# Watchlist operations
def add_to_watchlist(symbol: str, asset_class: str = "stock") -> bool:
    """Add symbol to watchlist"""
    try:
        with SessionLocal() as session:
            # Check if already exists
            existing = session.query(Watchlist).filter_by(symbol=symbol).first()
            if existing:
                return False
            
            watchlist_item = Watchlist(symbol=symbol, asset_class=asset_class)
            session.add(watchlist_item)
            session.commit()
            return True
    except Exception as e:
        print(f"Error adding to watchlist: {e}")
        return False

def get_watchlist() -> List[Dict[str, Any]]:
    """Get all watchlist items"""
    try:
        with SessionLocal() as session:
            items = session.query(Watchlist).order_by(Watchlist.added_at.desc()).all()
            return [
                {
                    "symbol": item.symbol,
                    "asset_class": item.asset_class,
                    "added_at": item.added_at.isoformat()
                }
                for item in items
            ]
    except Exception as e:
        print(f"Error getting watchlist: {e}")
        return []

def remove_from_watchlist(symbol: str) -> bool:
    """Remove symbol from watchlist"""
    try:
        with SessionLocal() as session:
            item = session.query(Watchlist).filter_by(symbol=symbol).first()
            if not item:
                return False
            
            session.delete(item)
            session.commit()
            return True
    except Exception as e:
        print(f"Error removing from watchlist: {e}")
        return False

# Analysis results operations
def save_analysis_result(symbol: str, result_data: Dict[str, Any]) -> bool:
    """Save analysis result"""
    try:
        with SessionLocal() as session:
            analysis = AnalysisResult(
                symbol=symbol,
                result_data=json.dumps(result_data)
            )
            session.add(analysis)
            session.commit()
            return True
    except Exception as e:
        print(f"Error saving analysis result: {e}")
        return False

def get_analysis_history(symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get analysis history for a symbol"""
    try:
        with SessionLocal() as session:
            results = (
                session.query(AnalysisResult)
                .filter_by(symbol=symbol)
                .order_by(AnalysisResult.created_at.desc())
                .limit(limit)
                .all()
            )
            
            return [
                {
                    "id": result.id,
                    "symbol": result.symbol,
                    "data": json.loads(result.result_data),
                    "created_at": result.created_at.isoformat()
                }
                for result in results
            ]
    except Exception as e:
        print(f"Error getting analysis history: {e}")
        return []

# API call tracking operations
def log_api_call(provider: str):
    """Log an API call"""
    try:
        with SessionLocal() as session:
            api_call = APICall(provider=provider)
            session.add(api_call)
            session.commit()
    except Exception as e:
        print(f"Error logging API call: {e}")

def get_api_calls_in_last_minute(provider: str) -> int:
    """Get number of API calls in the last minute for rate limiting"""
    try:
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        
        with SessionLocal() as session:
            count = (
                session.query(APICall)
                .filter(
                    APICall.provider == provider,
                    APICall.timestamp >= one_minute_ago
                )
                .count()
            )
            return count
    except Exception as e:
        print(f"Error getting API call count: {e}")
        return 0

# Cleanup operations
def cleanup_old_data():
    """Clean up old data (run periodically)"""
    try:
        # Remove API call logs older than 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        with SessionLocal() as session:
            deleted = (
                session.query(APICall)
                .filter(APICall.timestamp < cutoff_time)
                .delete()
            )
            session.commit()
            
            if deleted > 0:
                print(f"Cleaned up {deleted} old API call records")
            
    except Exception as e:
        print(f"Error during cleanup: {e}")

# Health check
def check_db_health() -> bool:
    """Check if database is accessible"""
    try:
        with SessionLocal() as session:
            session.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
