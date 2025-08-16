# ==============================================================================
# FILE: app/symbol_normalizer.py - ENHANCED VERSION
# ==============================================================================

from enum import Enum
import re

class AssetClass(Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    FX = "fx"

class Provider(Enum):
    FINNHUB = "finnhub"
    TWELVEDATA = "twelvedata"

def detect_asset_class(symbol: str) -> AssetClass:
    """
    ENHANCED: Auto-detect asset class from symbol patterns
    """
    symbol = symbol.upper().strip()
    
    # Crypto patterns
    crypto_patterns = [
        r'^BTC', r'^ETH', r'^ADA', r'^DOT', r'^SOL', r'^AVAX', r'^MATIC',
        r'^LTC', r'^XRP', r'^DOGE', r'^SHIB', r'^UNI', r'^LINK', r'^BCH',
        r'USD$', r'USDT$', r'USDC$', r'BTC$', r'ETH$',  # Ends with common crypto
        r'/', r'-'  # Contains separators common in crypto pairs
    ]
    
    # Forex patterns
    forex_patterns = [
        r'^(EUR|GBP|JPY|CHF|AUD|NZD|CAD|USD)(USD|EUR|GBP|JPY|CHF|AUD|NZD|CAD)$',
        r'^USD(EUR|GBP|JPY|CHF|AUD|NZD|CAD)$',
        r'^(EUR|GBP|AUD|NZD|CAD)(USD)$'
    ]
    
    # Check crypto patterns
    for pattern in crypto_patterns:
        if re.search(pattern, symbol):
            return AssetClass.CRYPTO
    
    # Check forex patterns
    for pattern in forex_patterns:
        if re.search(pattern, symbol):
            return AssetClass.FX
    
    # Default to stock
    return AssetClass.STOCK

def normalize_symbol(symbol: str, asset: AssetClass, provider: Provider) -> str:
    """
    ENHANCED: Normalize symbol for different providers and asset classes
    """
    symbol = symbol.upper().strip()
    
    if provider == Provider.FINNHUB:
        if asset == AssetClass.CRYPTO:
            # Finnhub crypto: BINANCE:BTCUSDT
            if '/' in symbol:
                base, quote = symbol.split('/')
                return f"BINANCE:{base}{quote}"
            elif '-' in symbol:
                base, quote = symbol.split('-')
                return f"BINANCE:{base}{quote}"
            else:
                return f"BINANCE:{symbol}"
        
        elif asset == AssetClass.FX:
            # Finnhub forex: OANDA:EUR_USD
            if len(symbol) == 6:  # EURUSD -> EUR_USD
                return f"OANDA:{symbol[:3]}_{symbol[3:]}"
            elif '/' in symbol:  # EUR/USD -> EUR_USD
                return f"OANDA:{symbol.replace('/', '_')}"
            else:
                return f"OANDA:{symbol}"
        
        else:  # Stock
            return symbol
    
    elif provider == Provider.TWELVEDATA:
        if asset == AssetClass.CRYPTO:
            # Twelve Data crypto: BTC/USD
            if 'USDT' in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USD"
            elif not ('/' in symbol or '-' in symbol):
                return f"{symbol}/USD"
            else:
                return symbol.replace('-', '/')
        
        elif asset == AssetClass.FX:
            # Twelve Data forex: EUR/USD
            if len(symbol) == 6:  # EURUSD -> EUR/USD
                return f"{symbol[:3]}/{symbol[3:]}"
            elif '_' in symbol:  # EUR_USD -> EUR/USD
                return symbol.replace('_', '/')
            else:
                return symbol
        
        else:  # Stock
            return symbol
    
    return symbol

# Common symbol mappings for better compatibility
SYMBOL_MAPPINGS = {
    # Crypto common mappings
    'BITCOIN': 'BTC',
    'ETHEREUM': 'ETH',
    'BTCUSD': 'BTC/USD',
    'ETHUSD': 'ETH/USD',
    
    # Forex common mappings
    'EURUSD': 'EUR/USD',
    'GBPUSD': 'GBP/USD',
    'USDJPY': 'USD/JPY',
    'AUDUSD': 'AUD/USD',
    'USDCAD': 'USD/CAD',
    'USDCHF': 'USD/CHF',
    'NZDUSD': 'NZD/USD',
}

def apply_symbol_mapping(symbol: str) -> str:
    """Apply common symbol mappings"""
    symbol_upper = symbol.upper()
    return SYMBOL_MAPPINGS.get(symbol_upper, symbol)
