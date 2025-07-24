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
from pykalman import KalmanFilter

def analyze_trend(ohlcv_df: pd.DataFrame) -> dict:
    """
    Applies Wavelet Denoising and a Kalman Filter to determine price trend.
    
    Output: {'trend_direction': str, 'confidence': float}
    """
    if ohlcv_df is None or len(ohlcv_df) < 20:
        return {'trend_direction': 'neutral', 'confidence': 0.0, 'error': 'Not enough data for trend analysis'}

    try:
        close_prices = ohlcv_df['close'].values

        # 1. Discrete Wavelet Transform (DWT) for denoising
        coeffs = pywt.wavedec(close_prices, 'db4', level=2)
        # Zero out the high-frequency detail coefficients
        coeffs[1:] = [np.zeros_like(c) for c in coeffs[1:]]
        denoised_prices = pywt.waverec(coeffs, 'db4')

        # Ensure denoised prices match length of original
        denoised_prices = denoised_prices[:len(close_prices)]

        # 2. Kalman Filter for smoothing
        kf = KalmanFilter(initial_state_mean=denoised_prices[0], n_dim_obs=1)
        (smoothed_state_means, _) = kf.filter(denoised_prices)
        
        # 3. Determine trend from the slope of the smoothed line
        # Use the last 5 data points to determine the recent trend direction
        last_points = smoothed_state_means[-5:].flatten()
        slope = np.polyfit(range(len(last_points)), last_points, 1)[0]

        # Normalize slope to get a confidence score (heuristic)
        price_range = np.ptp(close_prices)
        normalized_slope = slope / (price_range / len(close_prices)) if price_range > 0 else 0
        confidence = min(abs(normalized_slope) * 10, 1.0)

        # Classify trend
        if slope > 0.05 * np.mean(np.diff(close_prices)): # Threshold to avoid flat noise
            trend = 'bullish'
        elif slope < -0.05 * np.mean(np.diff(close_prices)):
            trend = 'bearish'
        else:
            trend = 'neutral'
            confidence = 1.0 - confidence # Confidence in neutrality

        return {'trend_direction': trend, 'confidence': round(confidence, 2)}

    except Exception as e:
        print(f"Error in WaveletKalmanEngine: {e}")
        return {'trend_direction': 'neutral', 'confidence': 0.0, 'error': str(e)}
