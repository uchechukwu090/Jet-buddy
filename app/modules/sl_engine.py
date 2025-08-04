def generate_sl_level(entry_price: float, bias: str, structure: dict, risk_ratio: float = 1.5) -> float:
    """
    Generates a stop-loss level based on entry, bias, and structure.
    """
    try:
        key_level = structure.get('key_level', entry_price)
        buffer = abs(entry_price - key_level) / risk_ratio

        if bias == 'bullish':
            sl = entry_price - buffer
        elif bias == 'bearish':
            sl = entry_price + buffer
        else:
            sl = entry_price  # fallback

        return round(sl, 4)

    except Exception as e:
        print(f"SL Engine Error: {e}")
        return entry_price
