# ==============================================================================
# FILE: app/modules/trend_engine.py
# ==============================================================================
# --- Description:
# Implements the WaveletKalmanEngine for trend detection.
# It denoises price data with a Wavelet Transform and then smooths it
# with a Kalman Filter to identify the underlying trend.

import numpy as np
import pandas as pd
import pywt

# Try to import Kalman Filter, fallback to simple moving average if not available
try:
    from pykalman import KalmanFilter
    KALMAN_AVAILABLE = True
except ImportError:
    print("Warning: pykalman not available, using fallback smoothing")
    KALMAN_AVAILABLE = False

def simple_kalman_filter(data):
    """
    Simple alternative to Kalman Filter using exponential moving average
    """
    smoothed = np.zeros_like(data)
    smoothed[0] = data[0]
    alpha = 0.1  # Smoothing factor
    
    for i in range(1, len(data)):
        smoothed[i] = alpha * data[i] + (1 - alpha) * smoothed[i-1]
    
    return smoothed.reshape(-1, 1)

def analyze_trend(ohlcv_df: pd.DataFrame) -> dict:
    """
    Applies Wavelet Denoising and a Kalman Filter to determine price trend.
    
    Output: {'trend_direction': str, 'confidence': float}
    """
    if ohlcv_df is None or len(ohlcv_df) < 20:
        return {
            'trend_direction': 'neutral', 
            'confidence': 0.0, 
            'error': 'Not enough data for trend analysis'
        }

    try:
        close_prices = ohlcv_df['close'].values
        
        if len(close_prices) < 10:
            return {
                'trend_direction': 'neutral', 
                'confidence': 0.0, 
                'error': 'Insufficient data points'
            }

        # 1. Discrete Wavelet Transform (DWT) for denoising
        try:
            # Ensure data length is suitable for wavelet transform
            if len(close_prices) < 8:
                denoised_prices = close_prices
            else:
                coeffs = pywt.wavedec(close_prices, 'db4', level=2)
                # Zero out the high-frequency detail coefficients
                coeffs[1:] = [np.zeros_like(c) for c in coeffs[1:]]
                denoised_prices = pywt.waverec(coeffs, 'db4')
                # Ensure denoised prices match length of original
                denoised_prices = denoised_prices[:len(close_prices)]
        except Exception as e:
            print(f"Wavelet transform error: {e}, using original prices")
            denoised_prices = close_prices

        # 2. Kalman Filter or fallback smoothing
        try:
            if KALMAN_AVAILABLE:
                kf = KalmanFilter(initial_state_mean=denoised_prices[0], n_dim_obs=1)
                (smoothed_state_means, _) = kf.filter(denoised_prices)
            else:
                smoothed_state_means = simple_kalman_filter(denoised_prices)
        except Exception as e:
            print(f"Kalman filter error: {e}, using simple moving average")
            # Fallback to simple moving average
            window = min(5, len(denoised_prices))
            smoothed_data = pd.Series(denoised_prices).rolling(window=window, center=True).mean().fillna(method='bfill').fillna(method='ffill')
            smoothed_state_means = smoothed_data.values.reshape(-1, 1)
        
        # 3. Determine trend from the slope of the smoothed line
        # Use the last 5 data points to determine the recent trend direction
        last_points_count = min(5, len(smoothed_state_means))
        last_points = smoothed_state_means[-last_points_count:].flatten()
        
        if len(last_points) < 2:
            return {
                'trend_direction': 'neutral', 
                'confidence': 0.0, 
                'error': 'Insufficient smoothed data points'
            }
        
        slope = np.polyfit(range(len(last_points)), last_points, 1)[0]

        # Normalize slope to get a confidence score (heuristic)
        price_range = np.ptp(close_prices)
        if price_range == 0:
            return {
                'trend_direction': 'neutral', 
                'confidence': 0.0, 
                'error': 'No price movement detected'
            }
        
        normalized_slope = slope / (price_range / len(close_prices))
        confidence = min(abs(normalized_slope) * 10, 1.0)

        # Calculate threshold based on average price change
        price_changes = np.diff(close_prices)
        avg_change = np.mean(np.abs(price_changes)) if len(price_changes) > 0 else 0.01
        threshold = 0.05 * avg_change

        # Classify trend
        if slope > threshold:
            trend = 'bullish'
        elif slope < -threshold:
            trend = 'bearish'
        else:
            trend = 'neutral'
            confidence = 1.0 - confidence  # Confidence in neutrality

        return {
            'trend_direction': trend, 
            'confidence': round(confidence, 2),
            'slope': round(slope, 6),
            'threshold': round(threshold, 6)
        }

    except Exception as e:
        print(f"Error in WaveletKalmanEngine: {e}")
        return {
            'trend_direction': 'neutral', 
            'confidence': 0.0, 
            'error': str(e)
        }
