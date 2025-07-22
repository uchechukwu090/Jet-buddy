# ==============================================================================
# FILE: app/modules/sentiment_engine.py
# ==============================================================================
# --- Description:
# Implements the LLMSentimentMiner. It fetches news headlines and uses an LLM
# via OpenRouter to classify the sentiment for a given trading symbol.

from collections import Counter
from app.modules.data_fetcher import get_news_headlines, get_llm_sentiment

def analyze_sentiment(symbol: str) -> dict:
    """
    Analyzes news sentiment for a symbol.
    
    Output: {'sentiment': str, 'confidence': float}
    """
    try:
        headlines = get_news_headlines(symbol)
        if not headlines:
            return {'sentiment': 'neutral', 'confidence': 1.0, 'reason': 'No headlines found.'}

        sentiments = [get_llm_sentiment(h, symbol) for h in headlines]
        
        if not sentiments:
            return {'sentiment': 'neutral', 'confidence': 1.0, 'reason': 'Sentiment analysis failed.'}

        # Aggregate results
        sentiment_counts = Counter(sentiments)
        dominant_sentiment = sentiment_counts.most_common(1)[0][0]
        
        # Calculate confidence
        confidence = sentiment_counts.most_common(1)[0][1] / len(sentiments)
        
        return {
            'sentiment': dominant_sentiment.lower(),
            'confidence': round(confidence, 2)
        }
    except Exception as e:
        print(f"Error in Sentiment Engine: {e}")
        return {'sentiment': 'neutral', 'confidence': 0.0, 'error': str(e)}
