# ==============================================================================
# FILE: app/modules/data_fetcher.py
# ==============================================================================
# --- Description:
# Contains all functions responsible for fetching data from external APIs.
# This modularizes data acquisition and handles API-specific logic and error handling.

import requests
import pandas as pd
from datetime import datetime, timedelta
from app.config import settings

# --- Finnhub Fetcher ---
def get_finnhub_ohlcv(symbol: str, resolution: str = '15', count: int = 200) -> Optional[pd.DataFrame]:
    """
    Fetches OHLCV data from Finnhub.
    Resolutions: 1, 5, 15, 30, 60, D, W, M.
    """
    try:
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=30)).timestamp()) # Fetch enough data

        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution={resolution}&from={start_time}&to={end_time}&token={settings.finnhub_api_key}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get('s') != 'ok' or not data.get('c'):
            print(f"Finnhub Error: No data for {symbol}")
            return None

        df = pd.DataFrame(data)
        df.rename(columns={'c': 'close', 'h': 'high', 'l': 'low', 'o': 'open', 'v': 'volume', 't': 'timestamp'}, inplace=True)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        return df.set_index('datetime').tail(count)
    except Exception as e:
        print(f"Error fetching Finnhub data for {symbol}: {e}")
        return None

# --- Newsdata.io Fetcher ---
def get_news_headlines(symbol: str) -> list:
    """Fetches recent news headlines related to a financial symbol."""
    try:
        # Note: Newsdata.io uses 'q' for query, which can include company names or tickers.
        url = f"https://newsdata.io/api/1/news?apikey={settings.newsdata_api_key}&q={symbol}&language=en&category=business"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            return [article['title'] for article in data.get('results', [])[:10]] # Get top 10 headlines
        return []
    except Exception as e:
        print(f"Error fetching news from Newsdata.io for {symbol}: {e}")
        return []

# --- OpenRouter LLM Caller ---
def get_llm_sentiment(headline: str, symbol: str) -> str:
    """
    Uses OpenRouter to classify a headline's sentiment.
    Falls back to simple keyword matching if API fails.
    """
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
            },
            json={
                "model": "mistralai/mistral-7b-instruct:free", # Using a capable free model
                "messages": [
                    {"role": "user", "content": f"Classify this headline for {symbol} as exactly one word: Bullish, Bearish, or Neutral. Headline: '{headline}'"}
                ]
            }
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].lower()
        
        if "bullish" in content:
            return "Bullish"
        if "bearish" in content:
            return "Bearish"
        return "Neutral"
    except Exception as e:
        print(f"OpenRouter API Error: {e}. Falling back to keyword analysis.")
        # Fallback logic
        headline_lower = headline.lower()
        bullish_keywords = ['up', 'rises', 'beats', 'gains', 'strong', 'upgrade', 'optimistic']
        bearish_keywords = ['down', 'falls', 'misses', 'losses', 'weak', 'downgrade', 'panic']
        if any(word in headline_lower for word in bullish_keywords):
            return "Bullish"
        if any(word in headline_lower for word in bearish_keywords):
            return "Bearish"
        return "Neutral"
