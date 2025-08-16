# ==============================================================================
# FILE: app/config.py - POSTGRES VERSION
# ==============================================================================
# Configuration settings for the trading analysis API

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings"""
    
    # Database Configuration (Neon/Postgres)
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/trading_analysis")
    
    # API Keys
    finnhub_api_key: str = os.getenv("FINNHUB_API_KEY", "")
    twelvedata_api_key: str = os.getenv("TWELVEDATA_API_KEY", "")
    newsdata_api_key: str = os.getenv("NEWSDATA_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    
    # Rate Limits (calls per minute)
    rate_limits = {
        "finnhub": 60,
        "twelvedata": 8,  # Free tier limit
        "newsdata": 200,
        "openrouter": 100
    }
    
    # Application Settings
    app_name: str = "Trading Analysis API"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS Settings
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://your-frontend-domain.com"  # Update with your frontend domain
    ]
    
    def __init__(self):
        # Validate required API keys
        missing_keys = []
        if not self.finnhub_api_key:
            missing_keys.append("FINNHUB_API_KEY")
        if not self.twelvedata_api_key:
            missing_keys.append("TWELVEDATA_API_KEY")
        
        if missing_keys:
            print(f"Warning: Missing API keys: {', '.join(missing_keys)}")
        
        # Validate database URL
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        
        print(f"Database URL configured: {self.database_url[:30]}...")

# Create global settings instance
settings = Settings()
