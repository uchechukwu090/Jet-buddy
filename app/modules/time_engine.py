# ==============================================================================
# FILE: app/modules/time_engine.py
# ==============================================================================
# --- Description:
# Implements the TimeEstimationModule. It calculates candle velocity to estimate
# time to reach certain price zones, like an entry or a take-profit level.

import numpy as np

def estimate_time_and_volatility(ohlcv_df: pd.DataFrame, entry_zone: Optional[str]) -> dict:
    """
    Estimates time to entry/TP and assesses volatility.
    
    Output: Dictionary with time estimates and volatility level.
    """
    if ohlcv_df is None or len(ohlcv_df) < 10:
        return {
            'estimated_entry_time': 'N/A', 
            'tp_eta': 'N/A', 
            'best_entry_zone': entry_zone or 'N/A', 
            'volatility': 'unknown'
        }

    try:
        # Calculate candle velocity (average body size per candle)
        avg_candle_size = (ohlcv_df['high'] - ohlcv_df['low']).mean()
        if avg_candle_size == 0:
            return {
                'estimated_entry_time': 'N/A', 'tp_eta': 'N/A', 
                'best_entry_zone': entry_zone or 'N/A', 'volatility': 'low'
            }

        # Estimate time to entry
        entry_time_str = "N/A"
        if entry_zone and entry_zone != 'N/A':
            zone_prices = [float(p.strip()) for p in entry_zone.split('--')]
            entry_price = np.mean(zone_prices)
            current_price = ohlcv_df['close'].iloc[-1]
            distance_to_entry = abs(current_price - entry_price)
            
            candles_to_entry = distance_to_entry / avg_candle_size
            # Assuming 15-min candles from data fetcher
            minutes_to_entry = candles_to_entry * 15
            
            if minutes_to_entry < 60:
                entry_time_str = f"in ~{int(minutes_to_entry)} minutes"
            else:
                entry_time_str = f"in ~{minutes_to_entry/60:.1f} hours"

        # Estimate time to a hypothetical TP (e.g., 2x the entry distance)
        tp_eta_str = "N/A"
        if entry_zone and entry_zone != 'N/A':
            distance_to_tp = 2 * abs(float(entry_zone.split('--')[0]) - ohlcv_df['close'].iloc[-1])
            candles_to_tp = distance_to_tp / avg_candle_size
            minutes_to_tp = candles_to_tp * 15
            tp_eta_str = f"within {minutes_to_tp/60:.1f} hours"

        # Assess volatility based on ATR (Average True Range)
        tr = pd.DataFrame()
        tr['h-l'] = ohlcv_df['high'] - ohlcv_df['low']
        tr['h-pc'] = abs(ohlcv_df['high'] - ohlcv_df['close'].shift())
        tr['l-pc'] = abs(ohlcv_df['low'] - ohlcv_df['close'].shift())
        atr = tr[['h-l', 'h-pc', 'l-pc']].max(axis=1).rolling(14).mean().iloc[-1]
        
        relative_atr = atr / ohlcv_df['close'].iloc[-1]
        if relative_atr > 0.005: # > 0.5% of price
            volatility = 'high'
        elif relative_atr > 0.002: # > 0.2% of price
            volatility = 'moderate'
        else:
            volatility = 'low'

        return {
            "estimated_entry_time": entry_time_str,
            "tp_eta": tp_eta_str,
            "best_entry_zone": entry_zone or 'N/A',
            "volatility": volatility
        }

    except Exception as e:
        print(f"Error in Time Engine: {e}")
        return {
            'estimated_entry_time': 'Error', 'tp_eta': 'Error', 
            'best_entry_zone': entry_zone or 'N/A', 'volatility': 'unknown', 'error': str(e)
        }
