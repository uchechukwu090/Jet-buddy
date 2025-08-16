# ==============================================================================
# FILE: main.py - FIXED VERSION
# ==============================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
from datetime import datetime

# Import your modules
from app.modules.data_fetcher import get_ohlcv_data
from app.modules.trend_engine import analyze_trend
from app.modules.sentiment_engine import analyze_sentiment
from app.modules.smc_engine import analyze_smc_structure
from app.modules.aggregator import aggregate_signals, aggregate_trade_signal
from app.modules.time_engine import estimate_time_and_volatility
from app.modules.risk_engine import get_position_size
from app.symbol_normalizer import AssetClass, Provider, detect_asset_class
from app.database import (
    init_db, add_to_watchlist, get_watchlist, remove_from_watchlist,
    save_analysis_result, get_analysis_history
)

app = FastAPI(title="Trading Analysis API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

# Pydantic models
class AnalysisRequest(BaseModel):
    symbol: str
    asset_class: str = "auto"  # Changed default to "auto"
    interval: str = "15min"
    provider: str = "finnhub"

class WatchlistRequest(BaseModel):
    symbol: str
    asset_class: str = "auto"  # Changed default to "auto"

# Routes
@app.get("/")
async def root():
    return {"message": "Trading Analysis API is running"}

@app.post("/analyze/force-run")
async def force_analysis(request: AnalysisRequest):
    """
    FIXED: Force-run analysis with proper asset detection and symbol normalization
    """
    try:
        symbol = request.symbol.upper()
        
        # FIX #4: Auto-detect asset class if set to "auto"
        if request.asset_class == "auto":
            asset_class_enum = detect_asset_class(symbol)
        else:
            asset_class_enum = AssetClass(request.asset_class)
        
        provider_enum = Provider(request.provider)
        
        # FIX #3: Pass original symbol to get_ohlcv_data so each provider gets fresh normalization
        ohlcv_df, data_source = get_ohlcv_data(
            symbol=symbol,  # Use original symbol, not pre-normalized
            interval=request.interval,
            asset=asset_class_enum,
            provider=provider_enum
        )
        
        if ohlcv_df is None:
            raise HTTPException(status_code=404, detail=f"Could not fetch data for {symbol}")
        
        # Run all analyses
        trend_result = analyze_trend(ohlcv_df)
        sentiment_result = analyze_sentiment(symbol)
        structure_result = analyze_smc_structure(ohlcv_df)
        
        # Aggregate results
        aggregated = aggregate_signals(trend_result, sentiment_result, structure_result)
        
        # Generate trade signal
        trade_data = {
            'symbol': symbol,
            'bias': aggregated['final_bias'],
            'structure': structure_result,
            'confidence': aggregated['bias_confidence'],
            'entry_price': ohlcv_df['close'].iloc[-1]
        }
        trade_signal = aggregate_trade_signal(trade_data)
        
        # Time and risk analysis
        entry_zone = structure_result.get('order_block', {}).get('zone') if structure_result.get('order_block') else None
        time_analysis = estimate_time_and_volatility(ohlcv_df, entry_zone)
        risk_analysis = get_position_size(
            aggregated['bias_confidence'], 
            time_analysis['volatility']
        )
        
        # Prepare response
        response = {
            "symbol": symbol,
            "asset_class": asset_class_enum.value,
            "data_source": data_source,
            "timestamp": datetime.now().isoformat(),
            "trend_analysis": trend_result,
            "sentiment_analysis": sentiment_result,
            "structure_analysis": structure_result,
            "aggregated_signals": aggregated,
            "trade_signal": trade_signal,
            "time_analysis": time_analysis,
            "risk_analysis": risk_analysis
        }
        
        # Save to database
        save_analysis_result(symbol, response)
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/analyze/{symbol}")
async def quick_analysis(symbol: str, asset_class: str = "auto"):
    """
    FIXED: Quick analysis with auto asset detection
    """
    try:
        symbol = symbol.upper()
        
        # Auto-detect asset class if set to "auto"
        if asset_class == "auto":
            asset_class_enum = detect_asset_class(symbol)
        else:
            asset_class_enum = AssetClass(asset_class)
        
        # Use original symbol for fresh normalization
        ohlcv_df, data_source = get_ohlcv_data(
            symbol=symbol,
            asset=asset_class_enum,
            provider=Provider.FINNHUB
        )
        
        if ohlcv_df is None:
            raise HTTPException(status_code=404, detail=f"Could not fetch data for {symbol}")
        
        # Quick trend analysis only
        trend_result = analyze_trend(ohlcv_df)
        structure_result = analyze_smc_structure(ohlcv_df)
        
        response = {
            "symbol": symbol,
            "asset_class": asset_class_enum.value,
            "data_source": data_source,
            "quick_trend": trend_result,
            "structure_bias": structure_result.get('structure_bias', 'neutral'),
            "timestamp": datetime.now().isoformat()
        }
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick analysis failed: {str(e)}")

# FIX #5: Ensure POST method for watchlist add (no conflicts)
@app.post("/watchlist/add")
async def add_to_watchlist_route(request: WatchlistRequest):
    """
    FIXED: Add symbol to watchlist with auto asset detection
    """
    try:
        symbol = request.symbol.upper()
        
        # Auto-detect asset class if set to "auto"
        if request.asset_class == "auto":
            asset_class_enum = detect_asset_class(symbol)
        else:
            asset_class_enum = AssetClass(request.asset_class)
        
        success = add_to_watchlist(symbol, asset_class_enum.value)
        
        if success:
            return {"message": f"Added {symbol} to watchlist", "symbol": symbol, "asset_class": asset_class_enum.value}
        else:
            raise HTTPException(status_code=400, detail=f"{symbol} is already in watchlist")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to watchlist: {str(e)}")

@app.get("/watchlist")
async def get_watchlist_route():
    """Get all symbols in watchlist"""
    try:
        watchlist = get_watchlist()
        return {"watchlist": watchlist, "count": len(watchlist)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get watchlist: {str(e)}")

@app.delete("/watchlist/{symbol}")
async def remove_from_watchlist_route(symbol: str):
    """Remove symbol from watchlist"""
    try:
        symbol = symbol.upper()
        success = remove_from_watchlist(symbol)
        
        if success:
            return {"message": f"Removed {symbol} from watchlist"}
        else:
            raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove from watchlist: {str(e)}")

@app.get("/history/{symbol}")
async def get_analysis_history_route(symbol: str, limit: int = 10):
    """Get analysis history for a symbol"""
    try:
        symbol = symbol.upper()
        history = get_analysis_history(symbol, limit)
        return {"symbol": symbol, "history": history, "count": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
