# ==============================================================================
# FILE: app/modules/smc_engine.py
# ==============================================================================
# --- Description:
# Implements PatternVisionAI and SMC Logic without image analysis.
# It uses OHLCV data to programmatically identify key market structures like
# Breaks of Structure (BOS), Order Blocks (OB), and liquidity zones.

import pandas as pd
import numpy as np

def find_swings(data: pd.DataFrame, n: int = 10):
    """Finds swing highs and lows. n is the window on each side."""
    data['swing_high'] = data['high'].rolling(window=2*n+1, center=True).apply(lambda x: x.argmax() == n, raw=True)
    data['swing_low'] = data['low'].rolling(window=2*n+1, center=True).apply(lambda x: x.argmin() == n, raw=True)
    return data

def analyze_smc_structure(ohlcv_df: pd.DataFrame) -> dict:
    """
    Identifies SMC structures from OHLCV data.
    
    Output: A dictionary with identified structures.
    """
    if ohlcv_df is None or len(ohlcv_df) < 25:
        return {'structure_bias': 'neutral', 'order_block': None, 'bos_detected': False, 'error': 'Not enough data'}

    try:
        df = find_swings(ohlcv_df.copy(), n=5)
        
        # --- Break of Structure (BOS) ---
        last_swing_high = df[df['swing_high'] == 1.0]['high'].iloc[-2] if sum(df['swing_high']) > 1 else None
        last_swing_low = df[df['swing_low'] == 1.0]['low'].iloc[-2] if sum(df['swing_low']) > 1 else None
        current_close = df['close'].iloc[-1]
        
        bos_detected = 'none'
        structure_bias = 'neutral'
        if last_swing_high and current_close > last_swing_high:
            bos_detected = 'bullish'
            structure_bias = 'bullish'
        elif last_swing_low and current_close < last_swing_low:
            bos_detected = 'bearish'
            structure_bias = 'bearish'

        # --- Order Block (OB) Detection (Simplified) ---
        # Look for the last opposite candle before a strong move that created the BOS
        order_block = None
        # Bullish OB: Last down candle before a strong up move
        if bos_detected == 'bullish':
            impulse_start_idx = df.index.get_loc(df[df['high'] > last_swing_high].index[0]) - 5 # Look back 5 candles
            subset = df.iloc[max(0, impulse_start_idx):impulse_start_idx+5]
            down_candles = subset[subset['close'] < subset['open']]
            if not down_candles.empty:
                ob_candle = down_candles.iloc[-1]
                order_block = {'type': 'bullish', 'zone': f"{ob_candle['low']:.4f} -- {ob_candle['high']:.4f}"}
        
        # Bearish OB: Last up candle before a strong down move
        elif bos_detected == 'bearish':
            impulse_start_idx = df.index.get_loc(df[df['low'] < last_swing_low].index[0]) - 5
            subset = df.iloc[max(0, impulse_start_idx):impulse_start_idx+5]
            up_candles = subset[subset['close'] > subset['open']]
            if not up_candles.empty:
                ob_candle = up_candles.iloc[-1]
                order_block = {'type': 'bearish', 'zone': f"{ob_candle['low']:.4f} -- {ob_candle['high']:.4f}"}

        return {
            'structure_bias': structure_bias,
            'bos_detected': bos_detected,
            'order_block': order_block
        }

    except Exception as e:
        print(f"Error in SMC Engine: {e}")
        return {'structure_bias': 'neutral', 'order_block': None, 'bos_detected': 'none', 'error': str(e)}
