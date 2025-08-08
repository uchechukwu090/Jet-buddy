# app/symbol_normalizer.py

from enum import Enum

class AssetClass(str, Enum):
    STOCK  = "stock"
    CRYPTO = "crypto"
    FX     = "fx"

class Provider(str, Enum):
    FINNHUB    = "finnhub"
    TWELVEDATA = "twelvedata"

def normalize_base(symbol: str) -> str:
    """
    Strip whitespace, uppercase, remove spaces.
    """
    return symbol.strip().upper().replace(" ", "")

def normalize_symbol(
    symbol: str,
    asset: AssetClass = AssetClass.STOCK,
    provider: Provider = Provider.FINNHUB
) -> str:
    """
    1) Apply base cleanup.
    2) Route through asset/provider rules.
    3) Raise if combination is unknown.
    """

    base = normalize_base(symbol)

    # FX rules
    if asset == AssetClass.FX:
        if provider == Provider.FINNHUB:
            return f"OANDA:{base.replace('/', '_')}"
        if provider == Provider.TWELVEDATA:
            return base.replace("_", "/")

    # Crypto rules
    if asset == AssetClass.CRYPTO:
        if provider == Provider.FINNHUB:
            return f"BINANCE:{base}"
        if provider == Provider.TWELVEDATA:
            return f"{base}/USD"

    # Stock (and general tickers)
    if asset == AssetClass.STOCK:
        # both providers accept plain tickers
        return base

    # Nothing matched? Bail out loudly
    raise ValueError(
        f"No normalization rule for asset={asset} with provider={provider}"
    )
