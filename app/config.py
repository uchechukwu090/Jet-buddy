# ==============================================================================
# FILE: app/config.py
# ==============================================================================
# --- Description:
# Manages configuration and securely loads environment variables.

import os
from typing import Dict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Keys
    finnhub_api_key: str
    twelvedata_api_key: str
    newsdata_api_key: str
    openrouter_api_key: str

    # Verified rate limits (free-tier defaults)
    rate_limits: Dict[str, int] = {
        "finnhub": 60,      # 60 calls per minute (free plan)
        "twelvedata": 8,    # 8 credits per minute, 800/day (Basic plan)
        "newsdata": 30,     # 30 credits per 15 min (free users)
        "openrouter": 20,   # 20 requests per minute on free models
    }

    # Email Settings
    smtp_server: str
    smtp_port: int
    smtp_username: str
    sender_email: str
    smtp_password: str

    # DB path
    db_path: str = "jetbuddy.db"

    class Config:
        env_file = ".env"

settings = Settings()
