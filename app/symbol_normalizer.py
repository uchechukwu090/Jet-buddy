# ==============================================================================
# FILE: app/symbol_normalizer.py
# ==============================================================================
# Symbol normalization for different data providers and asset classes

from enum import Enum
from typing import Dict, Optional

class AssetClass(Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    FX = "fx"
    COMMODITY = "commodity"

class Provider(Enum):
    FINNHUB = "finnhub"
    TWELVEDATA = "twelvedata"
    NEWSDATA = "newsdata"

# Symbol mapping dictionaries for different providers
SYMBOL_MAPPINGS = {
    Provider.FINNHUB: {
        AssetClass.STOCK: {
            # Most stocks use their standard ticker
        },
        AssetClass.CRYPTO: {
            'BTCUSD': 'BINANCE:BTCUSDT',
            'ETHUSD': 'BINANCE:ETHUSDT',
            'ADAUSD': 'BINANCE:ADAUSDT',
            'DOTUSD': 'BINANCE:DOTUSDT',
            'LINKUSD': 'BINANCE:LINKUSDT',
            'SOLUSD': 'BINANCE:SOLUSDT',
            'MATICUSD': 'BINANCE:MATICUSDT',
            'AVAXUSD': 'BINANCE:AVAXUSDT',
        },
        AssetClass.FX: {
            'EURUSD': 'OANDA:EUR_USD',
            'GBPUSD': 'OANDA:GBP_USD',
            'USDJPY': 'OANDA:USD_JPY',
            'USDCHF': 'OANDA:USD_CHF',
            'AUDUSD': 'OANDA:AUD_USD',
            'USDCAD': 'OANDA:USD_CAD',
            'NZDUSD': 'OANDA:NZD_USD',
        }
    },
    Provider.TWELVEDATA: {
        AssetClass.STOCK: {
            # Twelve Data uses standard tickers for stocks
        },
        AssetClass.CRYPTO: {
            'BTCUSD': 'BTC/USD',
            'ETHUSD': 'ETH/USD',
            'ADAUSD': 'ADA/USD',
            'DOTUSD': 'DOT/USD',
            'LINKUSD': 'LINK/USD',
            'SOLUSD': 'SOL/USD',
            'MATICUSD': 'MATIC/USD',
            'AVAXUSD': 'AVAX/USD',
        },
        AssetClass.FX: {
            'EURUSD': 'EUR/USD',
            'GBPUSD': 'GBP/USD',
            'USDJPY': 'USD/JPY',
            'USDCHF': 'USD/CHF',
            'AUDUSD': 'AUD/USD',
            'USDCAD': 'USD/CAD',
            'NZDUSD': 'NZD/USD',
        }
    }
}

# Common crypto symbol variations
CRYPTO_VARIATIONS = {
    'BTC': ['BITCOIN', 'BTCUSD', 'BTCUSDT', 'BTC/USD'],
    'ETH': ['ETHEREUM', 'ETHUSD', 'ETHUSDT', 'ETH/USD'],
    'ADA': ['CARDANO', 'ADAUSD', 'ADAUSDT', 'ADA/USD'],
    'DOT': ['POLKADOT', 'DOTUSD', 'DOTUSDT', 'DOT/USD'],
    'LINK': ['CHAINLINK', 'LINKUSD', 'LINKUSDT', 'LINK/USD'],
    'SOL': ['SOLANA', 'SOLUSD', 'SOLUSDT', 'SOL/USD'],
    'MATIC': ['POLYGON', 'MATICUSD', 'MATICUSDT', 'MATIC/USD'],
    'AVAX': ['AVALANCHE', 'AVAXUSD', 'AVAXUSDT', 'AVAX/USD'],
}

# Common FX pair variations
FX_VARIATIONS = {
    'EURUSD': ['EUR/USD', 'EUR_USD', 'EURUSD'],
    'GBPUSD': ['GBP/USD', 'GBP_USD', 'GBPUSD'],
    'USDJPY': ['USD/JPY', 'USD_JPY', 'USDJPY'],
    'USDCHF': ['USD/CHF', 'USD_CHF', 'USDCHF'],
    'AUDUSD': ['AUD/USD', 'AUD_USD', 'AUDUSD'],
    'USDCAD': ['USD/CAD', 'USD_CAD', 'USDCAD'],
    'NZDUSD': ['NZD/USD', 'NZD_USD', 'NZDUSD'],
}

def normalize_symbol(symbol: str, asset: AssetClass = AssetClass.STOCK, provider: Provider = Provider.FINNHUB) -> str:
    """
    Normalize a symbol for a specific provider and asset class
    
    Args:
        symbol: The symbol to normalize
        asset: The asset class (stock, crypto, fx)
        provider: The data provider
        
    Returns:
        Normalized symbol string
    """
    if not symbol:
        return symbol
    
    symbol = symbol.upper().strip()
    
    # Get provider-specific mappings
    provider_mappings = SYMBOL_MAPPINGS.get(provider, {})
    asset_mappings = provider_mappings.get(asset, {})
    
    # Check direct mapping first
    if symbol in asset_mappings:
        return asset_mappings[symbol]
    
    # For crypto, try to find base symbol and map it
    if asset == AssetClass.CRYPTO:
        for base_crypto, variations in CRYPTO_VARIATIONS.items():
            if symbol in variations or symbol.startswith(base_crypto):
                # Try to map the base crypto + USD
                crypto_usd = base_crypto + 'USD'
                if crypto_usd in asset_mappings:
                    return asset_mappings[crypto_usd]
                # If no mapping found, return normalized form
                if provider == Provider.TWELVEDATA:
                    return f"{base_crypto}/USD"
                elif provider == Provider.FINNHUB:
                    return f"BINANCE:{base_crypto}USDT"
    
    # For FX, try to find the pair
    if asset == AssetClass.FX:
        for base_pair, variations in FX_VARIATIONS.items():
            if symbol in variations:
                if base_pair in asset_mappings:
                    return asset_mappings[base_pair]
                # Return normalized form based on provider
                if provider == Provider.TWELVEDATA:
                    return base_pair[:3] + '/' + base_pair[3:]
                elif provider == Provider.FINNHUB:
                    return f"OANDA:{base_pair[:3]}_{base_pair[3:]}"
    
    # If no specific mapping found, return the symbol as-is for stocks
    # or apply basic formatting for crypto/fx
    if asset == AssetClass.CRYPTO and provider == Provider.TWELVEDATA:
        if '/' not in symbol and 'USD' in symbol:
            base = symbol.replace('USD', '').replace('USDT', '')
            return f"{base}/USD"
    elif asset == AssetClass.CRYPTO and provider == Provider.FINNHUB:
        if '/' not in symbol and 'USD' in symbol:
            base = symbol.replace('USD', '').replace('USDT', '')
            return f"BINANCE:{base}USDT"
    elif asset == AssetClass.FX:
        if len(symbol) == 6 and provider == Provider.TWELVEDATA:
            return f"{symbol[:3]}/{symbol[3:]}"
        elif len(symbol) == 6 and provider == Provider.FINNHUB:
            return f"OANDA:{symbol[:3]}_{symbol[3:]}"
    
    return symbol

def detect_asset_class(symbol: str) -> AssetClass:
    """
    Attempt to detect the asset class based on the symbol format
    
    Args:
        symbol: The symbol to analyze
        
    Returns:
        Detected asset class
    """
    symbol = symbol.upper().strip()
    
    # Check for crypto patterns
    crypto_indicators = ['BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'SOL', 'MATIC', 'AVAX', 'USDT', 'USDC']
    if any(indicator in symbol for indicator in crypto_indicators):
        return AssetClass.CRYPTO
    
    # Check for FX patterns
    fx_patterns = ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
    if len(symbol) == 6 and symbol[:3] in fx_patterns or symbol[3:] in fx_patterns:
        return AssetClass.FX
    
    # Check for common FX pairs
    common_fx = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD']
    if symbol in common_fx:
        return AssetClass.FX
    
    # Default to stock
    return AssetClass.STOCK

def get_display_symbol(symbol: str, asset: AssetClass = AssetClass.STOCK) -> str:
    """
    Get a user-friendly display version of a symbol
    
    Args:
        symbol: The normalized symbol
        asset: The asset class
        
    Returns:
        Display-friendly symbol
    """
    if not symbol:
        return symbol
    
    symbol = symbol.upper()
    
    # Clean up provider prefixes
    if ':' in symbol:
        symbol = symbol.split(':')[1]
    
    # Clean up crypto suffixes
    if asset == AssetClass.CRYPTO:
        symbol = symbol.replace('USDT', 'USD').replace('_USD', 'USD')
        if '/' in symbol:
            return symbol
        elif 'USD' in symbol:
            base = symbol.replace('USD', '')
            return f"{base}/USD"
    
    # Clean up FX formatting
    if asset == AssetClass.FX:
        if '_' in symbol:
            return symbol.replace('_', '/')
        elif len(symbol) == 6 and '/' not in symbol:
            return f"{symbol[:3]}/{symbol[3:]}"
    
    return symbol

def validate_symbol(symbol: str, asset: AssetClass = AssetClass.STOCK) -> bool:
    """
    Validate if a symbol appears to be in the correct format
    
    Args:
        symbol: The symbol to validate
        asset: The asset class
        
    Returns:
        True if symbol appears valid, False otherwise
    """
    if not symbol or len(symbol) < 1:
        return False
    
    symbol = symbol.upper().strip()
    
    if asset == AssetClass.STOCK:
        # Stock symbols should be 1-5 characters, letters only
        return len(symbol) <= 5 and symbol.isalpha()
    
    elif asset == AssetClass.CRYPTO:
        # Crypto symbols can have various formats
        valid_patterns = [
            len(symbol) >= 3 and len(symbol) <= 10,  # Basic length check
            'USD' in symbol or '/' in symbol,         # Should relate to USD
        ]
        return any(valid_patterns)
    
    elif asset == AssetClass.FX:
        # FX pairs should be 6-7 characters or have / separator
        if '/' in symbol:
            parts = symbol.split('/')
            return len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3
        else:
            return len(symbol) == 6 or len(symbol) == 7
    
    return True  # Default to valid for unknown asset classes

# Utility function to get all supported symbols for a provider/asset combination
def get_supported_symbols(provider: Provider, asset: AssetClass) -> list:
    """
    Get list of supported symbols for a provider/asset combination
    
    Args:
        provider: The data provider
        asset: The asset class
        
    Returns:
        List of supported symbol keys
    """
    provider_mappings = SYMBOL_MAPPINGS.get(provider, {})
    asset_mappings = provider_mappings.get(asset, {})
    return list(asset_mappings.keys())
