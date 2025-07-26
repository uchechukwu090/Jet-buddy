# ==============================================================================
# FILE: app/config.py
# ==============================================================================
# --- Description:
# Manages configuration and securely loads environment variables.

import os
from pydantic_settings import BaseSettings
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """ Manages application configuration. """
    # API Keys & Limits
    finnhub_api_key: str
    twelvedata_api_key: str
    newsdata_api_key: str 
    openrouter_api_key: str
    finnhub_rate_limit: int = 25

    # Email Settings
    smtp_server: str =
    smtp_port: int =
    smtp_username: str
    sender_email: str
    smtp_password:

    class Config:
        env_file = ".env"

settings = Settings()
