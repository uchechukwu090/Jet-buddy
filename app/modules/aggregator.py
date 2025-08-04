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
    bias = data.get('bias')
    structure = data.get('structure')
    confidence = data.get('confidence', 50)
    entry_price = data.get('entry_price', structure.get('key_level', 1.0))

    tp_data = generate_tp_prediction(bias, structure, confidence)
    sl_level = generate_sl_level(entry_price, bias, structure)

    return {
        'symbol': data.get('symbol'),
        'bias': bias,
        'confidence': confidence,
        'entry_price': entry_price,
        'tp_zone': tp_data['tp_zone'],
        'tp_levels': tp_data['levels'],
        'sl_level': sl_level
    }

def aggregate_signals(trend: dict, sentiment: dict, structure: dict) -> dict:
    """
    Aggregates signals from various modules into a final confidence score.
    
    Output: {'bias_confidence': float, 'final_bias': str}
    """
    scores = {'bullish': 0, 'bearish': 0}
    weights = {'trend': 0.5, 'sentiment': 0.2, 'structure': 0.3}

    # Map text outputs to numerical scores
    mapping = {'bullish': 1, 'bearish': -1, 'neutral': 0}
    
    try:
        # Trend Score
        trend_score = mapping.get(trend.get('trend_direction', 'neutral'), 0)
        trend_confidence = trend.get('confidence', 0)
        if trend_score > 0: scores['bullish'] += trend_confidence * weights['trend']
        if trend_score < 0: scores['bearish'] += trend_confidence * weights['trend']

        # Sentiment Score
        sentiment_score = mapping.get(sentiment.get('sentiment', 'neutral'), 0)
        sentiment_confidence = sentiment.get('confidence', 0)
        if sentiment_score > 0: scores['bullish'] += sentiment_confidence * weights['sentiment']
        if sentiment_score < 0: scores['bearish'] += sentiment_confidence * weights['sentiment']

        # Structure Score
        structure_score = mapping.get(structure.get('structure_bias', 'neutral'), 0)
        # Structure confidence is binary (1 if detected, 0 if not)
        structure_confidence = 1.0 if structure_score != 0 else 0.0
        if structure_score > 0: scores['bullish'] += structure_confidence * weights['structure']
        if structure_score < 0: scores['bearish'] += structure_confidence * weights['structure']

        # Determine final bias and confidence
        if scores['bullish'] > scores['bearish']:
            final_bias = 'bullish'
            # Confidence is the score of the winning bias
            confidence = scores['bullish']
        elif scores['bearish'] > scores['bullish']:
            final_bias = 'bearish'
            confidence = scores['bearish']
        else:
            final_bias = 'neutral'
            # Confidence in neutrality is 1 minus the max score
            confidence = 1.0 - max(scores['bullish'], scores['bearish'])

        return {'bias_confidence': round(confidence, 2), 'final_bias': final_bias}

    except Exception as e:
        print(f"Error in Aggregator: {e}")
        return {'bias_confidence': 0.0, 'final_bias': 'neutral', 'error': str(e)}
