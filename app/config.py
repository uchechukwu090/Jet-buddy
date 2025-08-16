# ==============================================================================
# FILE: app/config.py
# ==============================================================================
# Configuration settings for the JetBuddy trading analysis system

import os
from typing import Dict

class Settings:
    def __init__(self):
        # API Keys
        self.finnhub_api_key = os.getenv('FINNHUB_API_KEY', '')
        self.twelvedata_api_key = os.getenv('TWELVEDATA_API_KEY', '')
        self.newsdata_api_key = os.getenv('NEWSDATA_API_KEY', '')
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY', '')
        
        # Rate Limits (requests per minute)
        self.rate_limits = {
            'finnhub': 60,
            'twelvedata': 800,  # Free tier limit
            'newsdata': 200,
            'openrouter': 100
        }
        
        # Database settings
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///jetbuddy.db')
        
        # Default analysis parameters
        self.default_interval = '15min'
        self.default_output_size = 200
        self.default_risk_tier = 'medium'
        
        # SMC Analysis settings
        self.smc_swing_window = 5
        self.min_data_points = 25
        
        # Sentiment analysis settings
        self.max_headlines = 10
        self.sentiment_model = "mistralai/mistral-7b-instruct:free"
        
        # Risk management settings
        self.default_risk_ratio = 2.0
        self.position_size_tiers = {
            'conservative': 0.01,
            'medium': 0.10,
            'aggressive': 1.00
        }
        
        # Time analysis settings
        self.candle_interval_minutes = {
            '15min': 15,
            '1h': 60,
            '1day': 1440
        }

    def get_rate_limit(self, provider: str) -> int:
        return self.rate_limits.get(provider, 60)
    
    def get_position_size(self, tier: str) -> float:
        return self.position_size_tiers.get(tier, 0.10)
    
    def get_candle_minutes(self, interval: str) -> int:
        return self.candle_interval_minutes.get(interval, 15)

# Global settings instance
settings = Settings()
