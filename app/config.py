# ==============================================================================
# FILE: app/config.py
# ==============================================================================
# --- Description:
# Manages configuration and securely loads environment variables.

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """ Manages application configuration. """
    # API Keys & Limits
    finnhub_api_key: str = os.getenv("FINNHUB_API_KEY")
    twelvedata_api_key: str = os.getenv("TWELVEDATA_API_KEY")
    newsdata_api_key: str = os.getenv("NEWSDATA_API_KEY")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY")
    finnhub_rate_limit: int = 25

    # Email Settings
    smtp_server: str = os.getenv("SMTP_SERVER")
    smtp_port: int = os.getenv("SMTP_PORT")
    smtp_username: str = os.getenv("SMTP_USERNAME")
    sender_email: str = os.getenv("SENDER_EMAIL")
    smtp_password: str = os.getenv("SMTP_PASSWORD")

    class Config:
        env_file = ".env"

settings = Settings()
