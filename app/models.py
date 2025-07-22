# ==============================================================================
# FILE: app/models.py
# ==============================================================================
# --- Description:
# Pydantic models for API request/response and data structures.

from pydantic import BaseModel, EmailStr
from typing import Optional, List

class AnalysisOutput(BaseModel):
    trend_direction: str
    sentiment: str
    bias_confidence: float
    predicted_tp: Optional[float] = None
    tp_confidence: Optional[float] = None
    entry_zone: str
    estimated_entry_time: str
    tp_eta: str
    risk_profile: str
    suggested_lot_size: float
    status: str = "ok"
    notes: Optional[str] = None
    error_message: Optional[str] = None

class WatchlistAddItem(BaseModel):
    symbol: str
    email: Optional[EmailStr] = None

class WatchlistItem(BaseModel):
    id: int
    user_symbol: str
    normalized_symbol: str
    email: Optional[EmailStr] = None

    class Config:
        from_attributes = True
