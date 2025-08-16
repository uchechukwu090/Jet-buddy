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
    try:
        if len(data) < 2*n+1:
            # If not enough data, use smaller window
            n = max(1, len(data) // 3)
        
        data = data.copy()
        data['swing_high'] = data['high'].rolling(window=2*n+1, center=True).apply(
            lambda x: x.argmax() == n if len(x) == 2*n+1 else False, raw=True
        ).fillna(False)
        
        data['swing_low'] = data['low'].rolling(window=2*n+1, center=True).apply(
            lambda x: x.argmin() == n if len(x) == 2*n+1 else False, raw=True
        ).fillna(False)
        
        return data
    except Exception as e:
        print(f"Error in find_swings: {e}")
        data['swing_high'] = False
        data['swing_low'] = False
        return data

def analyze_smc_structure(ohlcv_df: pd.DataFrame) -> dict:
    """
    Identifies SMC structures from OHLCV data.
    
    Output: A dictionary with identified structures.
    """
    if ohlcv_df is None or len(ohlcv_df) < 25:
        return {
            'structure_bias': 'neutral', 
            'order_block': None, 
            'bos_detected': 'none', 
            'key_level': None,
            'liquidity_zone': None,
            'error': 'Not enough data'
        }

    try:
        df = find_swings(ohlcv_df.copy(), n=5)
        
        # Get current price for reference
        current_close = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1] 
        current_low = df['low'].iloc[-1]
        
        # --- Break of Structure (BOS) Detection ---
        swing_highs = df[df['swing_high'] == True]
        swing_lows = df[df['swing_low'] == True]
        
        bos_detected = 'none'
        structure_bias = 'neutral'
        key_level = current_close
        
        # Check for bullish BOS (price breaking above last significant high)
        if len(swing_highs) >= 2:
            last_swing_high = swing_highs['high'].iloc[-2]  # Second to last swing high
            if current_close > last_swing_high:
                bos_detected = 'bullish'
                structure_bias = 'bullish'
                key_level = last_swing_high
        
        # Check for bearish BOS (price breaking below last significant low)
        if len(swing_lows) >= 2:
            last_swing_low = swing_lows['low'].iloc[-2]  # Second to last swing low
            if current_close < last_swing_low:
                bos_detected = 'bearish'
                structure_bias = 'bearish'
                key_level = last_swing_low
        
        # If both conditions met, use the more recent one
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            last_high_idx = swing_highs.index[-2]
            last_low_idx = swing_lows.index[-2]
            
            if last_high_idx > last_low_idx and current_close > swing_highs['high'].iloc[-2]:
                bos_detected = 'bullish'
                structure_bias = 'bullish'
                key_level = swing_highs['high'].iloc[-2]
            elif last_low_idx > last_high_idx and current_close < swing_lows['low'].iloc[-2]:
                bos_detected = 'bearish'
                structure_bias = 'bearish'
                key_level = swing_lows['low'].iloc[-2]

        # --- Order Block (OB) Detection ---
        order_block = None
        
        try:
            if bos_detected == 'bullish' and len(swing_highs) >= 1:
                # Find the impulse that broke the structure
                break_idx = df.index.get_loc(swing_highs.index[-2]) if len(swing_highs) >= 2 else len(df) - 10
                
                # Look for the last bearish candle before the impulse (simplified OB detection)
                lookback_start = max(0, break_idx - 10)
                lookback_data = df.iloc[lookback_start:break_idx]
                
                # Find bearish candles (close < open)
                bearish_candles = lookback_data[lookback_data['close'] < lookback_data['open']]
                
                if not bearish_candles.empty:
                    ob_candle = bearish_candles.iloc[-1]  # Last bearish candle
                    order_block = {
                        'type': 'bullish',
                        'zone': f"{ob_candle['low']:.4f} -- {ob_candle['high']:.4f}",
                        'level': (ob_candle['low'] + ob_candle['high']) / 2
                    }
            
            elif bos_detected == 'bearish' and len(swing_lows) >= 1:
                # Find the impulse that broke the structure  
                break_idx = df.index.get_loc(swing_lows.index[-2]) if len(swing_lows) >= 2 else len(df) - 10
                
                # Look for the last bullish candle before the impulse
                lookback_start = max(0, break_idx - 10)
                lookback_data = df.iloc[lookback_start:break_idx]
                
                # Find bullish candles (close > open)
                bullish_candles = lookback_data[lookback_data['close'] > lookback_data['open']]
                
                if not bullish_candles.empty:
                    ob_candle = bullish_candles.iloc[-1]  # Last bullish candle
                    order_block = {
                        'type': 'bearish',
                        'zone': f"{ob_candle['low']:.4f} -- {ob_candle['high']:.4f}",
                        'level': (ob_candle['low'] + ob_candle['high']) / 2
                    }
        
        except Exception as ob_error:
            print(f"Error in order block detection: {ob_error}")
            order_block = None

        # --- Liquidity Zone Detection (Simplified) ---
        # Use recent highs/lows as potential liquidity zones
        liquidity_zone = None
        try:
            recent_data = df.tail(20)  # Last 20 candles
            if structure_bias == 'bullish':
                liquidity_zone = recent_data['low'].min()
            elif structure_bias == 'bearish':
                liquidity_zone = recent_data['high'].max()
            else:
                # For neutral, use middle of recent range
                liquidity_zone = (recent_data['high'].max() + recent_data['low'].min()) / 2
        except Exception as lz_error:
            print(f"Error in liquidity zone detection: {lz_error}")
            liquidity_zone = current_close

        return {
            'structure_bias': structure_bias,
            'bos_detected': bos_detected,
            'order_block': order_block,
            'key_level': round(key_level, 4) if key_level else current_close,
            'liquidity_zone': round(liquidity_zone, 4) if liquidity_zone else current_close,
            'swing_highs_count': len(swing_highs),
            'swing_lows_count': len(swing_lows)
        }

    except Exception as e:
        print(f"Error in SMC Structure Analysis: {e}")
        current_close = ohlcv_df['close'].iloc[-1] if len(ohlcv_df) > 0 else 1.0
        return {
            'structure_bias': 'neutral', 
            'order_block': None, 
            'bos_detected': 'none', 
            'key_level': current_close,
            'liquidity_zone': current_close,
            'error': str(e)
        }
