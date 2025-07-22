# ==============================================================================
# FILE: app/symbol_normalizer.py
# ==============================================================================
# --- Description:
# [ADJUSTMENT 2 - Implemented] Normalizes user-provided asset symbols
# into formats compatible with financial data APIs.

SYMBOL_MAP = {
    # Forex
    "eurusd": "EUR/USD", "gbpusd": "GBP/USD", "usdjpy": "USD/JPY", "audusd": "AUD/USD",
    # Crypto
    "btc": "BTC/USD", "eth": "ETH/USD",
    # Stocks / Tickers
    "apple": "AAPL", "google": "GOOGL", "tesla": "TSLA", "amazon": "AMZN",
}

def normalize_symbol(user_input: str) -> str:
    """ Normalizes a user-friendly symbol into a standard API format. """
    clean_input = user_input.lower().strip()
    if clean_input in SYMBOL_MAP:
        return SYMBOL_MAP[clean_input]
    if len(clean_input) == 6 and clean_input.isalpha():
        return f"{clean_input[:3]}/{clean_input[3:]}".upper()
    if 'usd' in clean_input and len(clean_input) > 3:
        base = clean_input.replace('usd', '')
        return f"{base}/USD".upper()
    return user_input.upper()
