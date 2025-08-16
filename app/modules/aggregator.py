# ==============================================================================
# FILE: app/modules/aggregator.py
# ==============================================================================
# --- Description:
# Implements the BayesianAggregator using a simple weighted model.
# It fuses the outputs from the trend, sentiment, and structure modules
# into a single directional bias confidence score.

from .tp_engine import generate_tp_prediction
from .sl_engine import generate_sl_level

def aggregate_trade_signal(data: dict) -> dict:
    """
    Aggregates analysis results and generates trade signal with TP and SL levels.
    """
    try:
        bias = data.get('bias', 'neutral')
        structure = data.get('structure', {})
        confidence = data.get('confidence', 0.5)
        entry_price = data.get('entry_price')
        
        # If no entry price provided, try to get from structure or use a default
        if entry_price is None:
            entry_price = structure.get('key_level', structure.get('entry_price', 1.0))
        
        # Prepare data for TP engine
        trend_data = {
            'bias': bias,
            'confidence': confidence,
            'momentum': data.get('momentum', 1.0)
        }
        
        # Ensure structure has required fields
        smc_data = {
            'order_block': structure.get('order_block', entry_price),
            'liquidity_zone': structure.get('liquidity_zone', entry_price),
            'key_level': structure.get('key_level', entry_price)
        }
        
        risk_profile = {
            'entry_price': entry_price,
            'risk_ratio': data.get('risk_ratio', 2.0)
        }
        
        # Generate TP and SL levels
        tp_data = generate_tp_prediction(trend_data, smc_data, risk_profile)
        sl_level = generate_sl_level(entry_price, bias, structure)

        return {
            'symbol': data.get('symbol'),
            'bias': bias,
            'confidence': confidence,
            'entry_price': entry_price,
            'tp_zone': tp_data.get('tp_zone', f"{tp_data.get('tp_level', 'N/A')}"),
            'tp_levels': tp_data.get('levels', [tp_data.get('tp_level', entry_price)]),
            'sl_level': sl_level,
            'tp_data': tp_data  # Include full TP data for debugging
        }
    
    except Exception as e:
        print(f"Error in aggregate_trade_signal: {e}")
        return {
            'symbol': data.get('symbol'),
            'bias': 'neutral',
            'confidence': 0.0,
            'entry_price': 1.0,
            'tp_zone': 'N/A',
            'tp_levels': [],
            'sl_level': 1.0,
            'error': str(e)
        }

def aggregate_signals(trend: dict, sentiment: dict, structure: dict) -> dict:
    """
    Aggregates signals from various modules into a final confidence score.
    
    Output: {'bias_confidence': float, 'final_bias': str}
    """
    try:
        scores = {'bullish': 0, 'bearish': 0}
        weights = {'trend': 0.5, 'sentiment': 0.2, 'structure': 0.3}

        # Map text outputs to numerical scores
        mapping = {'bullish': 1, 'bearish': -1, 'neutral': 0}
        
        # Trend Score
        trend_score = mapping.get(trend.get('trend_direction', 'neutral').lower(), 0)
        trend_confidence = trend.get('confidence', 0)
        # Ensure confidence is between 0 and 1
        if trend_confidence > 1:
            trend_confidence = trend_confidence / 100
        
        if trend_score > 0: 
            scores['bullish'] += trend_confidence * weights['trend']
        elif trend_score < 0: 
            scores['bearish'] += trend_confidence * weights['trend']

        # Sentiment Score
        sentiment_score = mapping.get(sentiment.get('sentiment', 'neutral').lower(), 0)
        sentiment_confidence = sentiment.get('confidence', 0)
        # Ensure confidence is between 0 and 1
        if sentiment_confidence > 1:
            sentiment_confidence = sentiment_confidence / 100
            
        if sentiment_score > 0: 
            scores['bullish'] += sentiment_confidence * weights['sentiment']
        elif sentiment_score < 0: 
            scores['bearish'] += sentiment_confidence * weights['sentiment']

        # Structure Score
        structure_score = mapping.get(structure.get('structure_bias', 'neutral').lower(), 0)
        # Structure confidence is binary (1 if detected, 0 if not)
        structure_confidence = 1.0 if structure_score != 0 else 0.0
        if structure_score > 0: 
            scores['bullish'] += structure_confidence * weights['structure']
        elif structure_score < 0: 
            scores['bearish'] += structure_confidence * weights['structure']

        # Determine final bias and confidence
        if scores['bullish'] > scores['bearish']:
            final_bias = 'bullish'
            confidence = scores['bullish']
        elif scores['bearish'] > scores['bullish']:
            final_bias = 'bearish'
            confidence = scores['bearish']
        else:
            final_bias = 'neutral'
            # Confidence in neutrality is 1 minus the max score
            confidence = 1.0 - max(scores['bullish'], scores['bearish'])

        return {
            'bias_confidence': round(min(confidence, 1.0), 2),  # Cap at 1.0
            'final_bias': final_bias,
            'component_scores': scores  # For debugging
        }

    except Exception as e:
        print(f"Error in aggregate_signals: {e}")
        return {
            'bias_confidence': 0.0, 
            'final_bias': 'neutral', 
            'error': str(e)
        }
