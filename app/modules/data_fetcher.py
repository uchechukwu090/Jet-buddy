# ==============================================================================
# FILE: app/modules/data_fetcher.py
# ==============================================================================
# --- Description:
# Fetches OHLCV, headlines, and sentiment from external APIs.
# Includes per-provider symbol normalization and fallback logic.
# ==============================================================================

import requests
import pandas as pd
from typing import Optional, List, Tuple
from datetime import datetime
from app.config import settings
from app.database import log_api_call, get_api_calls_in_last_minute
from app.symbol_normalizer import normalize_symbol, AssetClass, Provider
from twelvedata import TDClient

# --- Custom exception for broken or missing data ---
class DataUnavailableError(Exception):
    pass

# --- Finnhub handler ---
def _get_finnhub_ohlcv(symbol: str, interval: str, count: int, asset: AssetClass) -> pd.DataFrame:
    resolution_map = {'15min': '15', '1h': '60', '1day': 'D'}
    resolution = resolution_map.get(interval, '15')
    base_url = "https://finnhub.io/api/v1"

    # Choose correct endpoint
    if asset == AssetClass.CRYPTO:
        endpoint = "crypto/candle"
    elif asset == AssetClass.FX:
        endpoint = "forex/candle"
    else:
        endpoint = "stock/candle"

    url = f"{base_url}/{endpoint}?symbol={symbol}&resolution={resolution}&count={count}&token={settings.finnhub_api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get('s') != 'ok' or not data.get('c'):
            raise DataUnavailableError(f"Finnhub returned no/invalid data for {symbol}")

        df = pd.DataFrame(data)
        df.rename(columns={
            'c': 'close', 'h': 'high', 'l': 'low', 'o': 'open',
            'v': 'volume', 't': 'timestamp'
        }, inplace=True)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        return df.set_index('datetime')

    except (requests.RequestException, ValueError, KeyError) as e:
        raise DataUnavailableError(f"Finnhub API error for {symbol}: {e}") from e

# --- Twelve Data handler ---
def _get_twelvedata_ohlcv(symbol: str, interval: str, output_size: int) -> pd.DataFrame:
    try:
        td = TDClient(apikey=settings.twelvedata_api_key)
        ts = td.time_series(symbol=symbol, interval=interval, outputsize=output_size).as_pandas()

        if ts is None or ts.empty:
            raise DataUnavailableError(f"Twelve Data returned no data for {symbol}")

        return ts.iloc[::-1]
    except Exception as e:
        raise DataUnavailableError(f"Twelve Data error for {symbol}: {e}") from e

# --- Main data fetcher with fallback ---
def get_ohlcv_data(
    symbol: str,
    interval: str = "15min",
    output_size: int = 200,
    asset: AssetClass = AssetClass.STOCK,
    provider: Provider = Provider.FINNHUB
) -> Tuple[pd.DataFrame, str]:

    # Normalize for primary provider
    norm = normalize_symbol(symbol, asset=asset, provider=provider)

    # Try Primary
    calls = get_api_calls_in_last_minute(provider.value)
    if calls < settings.rate_limits.get(provider.value, 60):
        try:
            log_api_call(provider.value)
            if provider == Provider.FINNHUB:
                df = _get_finnhub_ohlcv(norm, interval, output_size, asset)
                return df, "Data from Finnhub"
            elif provider == Provider.TWELVEDATA:
                td_norm = normalize_symbol(symbol, asset=asset, provider=Provider.TWELVEDATA)
                df = _get_twelvedata_ohlcv(td_norm, interval, output_size)
                return df, "Data from Twelve Data"
        except DataUnavailableError:
            pass

    # Fallback to Twelve Data
    try:
        log_api_call(Provider.TWELVEDATA.value)
        td_norm = normalize_symbol(symbol, asset=asset, provider=Provider.TWELVEDATA)
        df = _get_twelvedata_ohlcv(td_norm, interval, output_size)
        return df, "Data from Twelve Data (fallback)"
    except DataUnavailableError:
        return None, "Failed to fetch data from all providers."

# --- Newsdata.io ---
def get_news_headlines(symbol: str) -> list:
    try:
        url = f"https://newsdata.io/api/1/news?apikey={settings.newsdata_api_key}&q={symbol}&language=en&category=business"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return [article['title'] for article in data.get('results', [])[:10]]
        return []
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        return []

# --- OpenRouter LLM sentiment ---
def get_llm_sentiment(headline: str, symbol: str) -> str:
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": "mistralai/mistral-7b-instruct:free",
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
        print(f"OpenRouter sentiment error: {e}")
        # Fallback
        headline_lower = headline.lower()
        if any(word in headline_lower for word in ['up', 'rises', 'beats', 'gains', 'strong', 'upgrade', 'optimistic']):
            return "Bullish"
        if any(word in headline_lower for word in ['down', 'falls', 'misses', 'losses', 'weak', 'downgrade', 'panic']):
            return "Bearish"
        return "Neutral"
