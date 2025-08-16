# ==============================================================================
# FILE: main.py
# ==============================================================================
# Main API entry point for JetBuddy trading analysis system

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
from datetime import datetime

# Import your modules
from app.modules.aggregator import aggregate_signals, aggregate_trade_signal
from app.modules.trend_engine import analyze_trend
from app.modules.sentiment_engine import analyze_sentiment
from app.modules.smc_engine import analyze_smc_structure
from app.modules.time_engine import estimate_time_and_volatility
from app.modules.risk_engine import get_position_size
from app.modules.data_fetcher import get_ohlcv_data
from app.symbol_normalizer import normalize_symbol, AssetClass, Provider, detect_asset_class
from app.database import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    cache_analysis_result, get_cached_analysis,
    cleanup_old_api_calls, cleanup_expired_cache
)
from app.config import settings

app = FastAPI(
    title="JetBuddy Trading Analysis API",
    description="Advanced multi-engine trading signal analysis system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class AnalysisRequest(BaseModel):
    interval: str = "15min"
    asset_class: str = "stock"
    risk_tier: str = "medium"

class WatchlistItem(BaseModel):
    symbol: str
    asset_class: str = "stock"

class WatchlistRemove(BaseModel):
    symbol: str

# Background task to cleanup old data
def cleanup_background():
    cleanup_old_api_calls()
    cleanup_expired_cache()

@app.on_event("startup")
async def startup_event():
    print("JetBuddy API starting up...")
    cleanup_background()

@app.get("/")
async def root():
    return {
        "message": "JetBuddy Trading Analysis API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/watchlist")
async def get_watchlist_items():
    """Get all watchlist items"""
    try:
        watchlist = get_watchlist()
        return watchlist
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/watchlist/add")
async def add_watchlist_item(item: WatchlistItem):
    """Add item to watchlist"""
    try:
        success = add_to_watchlist(item.symbol.upper(), item.asset_class)
        if success:
            return {"message": f"Added {item.symbol} to watchlist", "success": True}
        else:
            raise HTTPException(status_code=400, detail="Failed to add to watchlist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/watchlist/remove")
async def remove_watchlist_item(item: WatchlistRemove):
    """Remove item from watchlist"""
    try:
        success = remove_from_watchlist(item.symbol.upper())
        if success:
            return {"message": f"Removed {item.symbol} from watchlist", "success": True}
        else:
            raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sentiment/{symbol}")
async def get_sentiment(symbol: str):
    """Get sentiment analysis for a symbol"""
    try:
        sentiment = analyze_sentiment(symbol.upper())
        return sentiment
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")

@app.post("/analyze/force-run/{symbol}")
async def force_analysis(
    symbol: str, 
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """Force run complete analysis for a symbol"""
    try:
        symbol = symbol.upper()
        
        # Check cache first
        cache_key = f"{symbol}_{request.interval}_{request.asset_class}"
        cached_result = get_cached_analysis(symbol, request.interval, request.asset_class)
        
        if cached_result:
            try:
                return json.loads(cached_result)
            except:
                pass  # If cache is corrupted, continue with fresh analysis
        
        # Detect asset class if auto
        asset_class_enum = AssetClass(request.asset_class)
        if request.asset_class == "auto":
            asset_class_enum = detect_asset_class(symbol)
        
        # Get OHLCV data
        ohlcv_data, data_source = get_ohlcv_data(
            symbol=symbol,
            interval=request.interval,
            output_size=200,
            asset=asset_class_enum,
            provider=Provider.FINNHUB
        )
        
        if ohlcv_data is None:
            raise HTTPException(status_code=404, detail="Unable to fetch market data for symbol")
        
        # Run all analysis engines
        trend_analysis = analyze_trend(ohlcv_data)
        sentiment_analysis = analyze_sentiment(symbol)
        smc_analysis = analyze_smc_structure(ohlcv_data)
        
        # Aggregate signals
        aggregated = aggregate_signals(trend_analysis, sentiment_analysis, smc_analysis)
        
        # Get time and volatility estimates
        time_analysis = estimate_time_and_volatility(ohlcv_data, None)
        
        # Get risk management recommendations
        risk_analysis = get_position_size(
            aggregated['bias_confidence'], 
            time_analysis.get('volatility', 'moderate'),
            request.risk_tier
        )
        
        # Prepare trade signal data
        trade_data = {
            'symbol': symbol,
            'bias': aggregated['final_bias'],
            'confidence': aggregated['bias_confidence'],
            'structure': smc_analysis,
            'momentum': 1.0,
            'risk_ratio': 2.0
        }
        
        # Generate trade signal with TP/SL
        trade_signal = aggregate_trade_signal(trade_data)
        
        # Compile final result
        result = {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'data_source': data_source,
            'bias': aggregated['final_bias'],
            'confidence': aggregated['bias_confidence'],
            'entry_price': ohlcv_data['close'].iloc[-1],
            'tp_zone': trade_signal.get('tp_zone'),
            'tp_levels': trade_signal.get('tp_levels', []),
            'sl_level': trade_signal.get('sl_level'),
            'trend': trend_analysis,
            'sentiment': sentiment_analysis,
            'structure': smc_analysis,
            'time': time_analysis,
            'risk': risk_analysis,
            'aggregated_scores': aggregated.get('component_scores', {}),
            'interval': request.interval,
            'asset_class': request.asset_class
        }
        
        # Cache the result
        background_tasks.add_task(
            cache_analysis_result,
            symbol, 
            request.interval, 
            request.asset_class, 
            json.dumps(result),
            15  # 15 minutes TTL
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Analysis error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/analyze/{symbol}")
async def get_analysis(
    symbol: str,
    interval: str = "15min",
    asset_class: str = "stock",
    risk_tier: str = "medium"
):
    """Get cached analysis or return basic info"""
    try:
        cached_result = get_cached_analysis(symbol.upper(), interval, asset_class)
        if cached_result:
            return json.loads(cached_result)
        else:
            return {
                "message": "No cached analysis found. Use /analyze/force-run/{symbol} to generate new analysis.",
                "symbol": symbol.upper(),
                "cached": False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/symbols/supported/{provider}/{asset_class}")
async def get_supported_symbols(provider: str, asset_class: str):
    """Get supported symbols for a provider and asset class combination"""
    try:
        from app.symbol_normalizer import get_supported_symbols
        
        provider_enum = Provider(provider.lower())
        asset_enum = AssetClass(asset_class.lower())
        
        symbols = get_supported_symbols(provider_enum, asset_enum)
        return {"symbols": symbols, "count": len(symbols)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid provider or asset class: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/maintenance/cleanup")
async def manual_cleanup(background_tasks: BackgroundTasks):
    """Manually trigger cleanup of old data"""
    background_tasks.add_task(cleanup_background)
    return {"message": "Cleanup task queued"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
