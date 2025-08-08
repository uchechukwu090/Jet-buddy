# ==============================================================================
# FILE: app/modules/data_fetcher.py
# ==============================================================================
# --- Description:
# Contains all functions responsible for fetching data from external APIs.
# This modularizes data acquisition and handles API-specific logic and error handling.

import requests
import pandas as pd
from typing import Optional, List, Dict, Union, Tuple
from datetime import datetime, timedelta
from app.config import settings
from app.database import log_api_call, get_api_calls_in_last_minute
from twelvedata import TDClient
from app.symbol_normalizer import normalize_symbol, AssetClass, Provider

# --- Finnhub Fetcher ---
class DataUnavailableError(Exception):
    """Custom exception for when a data provider fails to return valid data."""
    pass

def _get_finnhub_ohlcv(symbol: str, interval: str, count: int) -> pd.DataFrame:
    """Internal function to query Finnhub. Raises DataUnavailableError on failure."""
    api_symbol = symbol.replace('/', '')
    try:
        # Map our standard interval to Finnhub's format
        resolution_map = {'15min': '15', '1h': '60', '1day': 'D'}
        resolution = resolution_map.get(interval, '15')
        
        # Determine if it's a forex or stock symbol for the correct endpoint
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={api_symbol}&resolution={resolution}&count={count}&token={settings.finnhub_api_key}"
        if '/' in symbol:
            url = f"https://finnhub.io/api/v1/forex/candle?symbol={api_symbol}&resolution={resolution}&count={count}&token={settings.finnhub_api_key}"

        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        if data.get('s') != 'ok' or not data.get('c'):
            raise DataUnavailableError(f"Finnhub returned no or invalid data for {symbol}.")

        df = pd.DataFrame(data)
        df.rename(columns={'c': 'close', 'h': 'high', 'l': 'low', 'o': 'open', 'v': 'volume', 't': 'timestamp'}, inplace=True)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        return df.set_index('datetime')
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        raise DataUnavailableError(f"Finnhub API query failed for {symbol}: {e}") from e

def _get_twelvedata_ohlcv(symbol: str, interval: str, output_size: int) -> pd.DataFrame:
    """Internal function to query Twelve Data. Raises DataUnavailableError on failure."""
    try:
        td = TDClient(apikey=settings.twelvedata_api_key)
        ts = td.time_series(symbol=symbol, interval=interval, outputsize=output_size).as_pandas()
        
        if ts is None or ts.empty:
            raise DataUnavailableError(f"Twelve Data returned no data for {symbol}.")
        
        return ts.iloc[::-1]  # Reverse to get chronological order
    except Exception as e:
        raise DataUnavailableError(f"Twelve Data API query failed for {symbol}: {e}") from e

def get_ohlcv_data(
    symbol: str,
    interval: str = "15min",
    output_size: int = 200,
    asset: AssetClass = AssetClass.STOCK,
    provider: Provider = Provider.FINNHUB
) -> Tuple[pd.DataFrame, str]:
    # 1) normalize
    norm = normalize_symbol(symbol, asset=asset, provider=provider)

    # 2) Fetch from primary provider
    calls = get_api_calls_in_last_minute(provider.value)
    if calls < settings.rate_limits[provider]:
        try:
            log_api_call(provider.value)
            if provider == Provider.FINNHUB:
                df = _get_finnhub_ohlcv(norm, interval, output_size)
                return df, "Data from Finnhub"
            # add more providers here…
        except DataUnavailableError:
            pass

    # 3) Fallback (e.g. TwelveData)
    try:
        log_api_call(Provider.TWELVEDATA.value)
        df = _get_twelvedata_ohlcv(
            normalize_symbol(symbol, asset=asset, provider=Provider.TWELVEDATA),
            interval,
            output_size
        )
        return df, "Data from Twelve Data (fallback)"
    except DataUnavailableError:
        return None, "Failed all providers"
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
