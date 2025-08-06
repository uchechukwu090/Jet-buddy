# ==============================================================================
# FILE: app/main.py
# ==============================================================================
# --- Description:
# The main application file. It sets up the FastAPI server, defines API
# endpoints, and orchestrates the analysis pipeline and scheduling.

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import os
# Import all modules and components
from app.config import settings
from app.models import AnalysisOutput,WatchlistAddItem, WatchlistItem
from typing import List, Dict, Optional, Union
from datetime import datetime
from app.caching import init_cache, set_cached_analysis, get_cached_analysis
from app.config import settings
from app.database import (init_db, add_to_watchlist, remove_from_watchlist, get_full_watchlist, get_unique_symbols_from_watchlist, get_emails_for_symbol)
from app.symbol_normalizer import normalize_symbol
from app.email_sender import send_email_report
from app.modules import (data_fetcher, trend_engine, smc_engine, sentiment_engine, tp_engine, time_engine, aggregator, risk_engine)

# --- Analysis Pipeline ---
def run_full_analysis(symbol: str):
    """Orchestrates the entire analysis pipeline for a given symbol."""
    print(f"[{datetime.now()}] Running full analysis for {symbol}...")

    # 1. Fetch OHLCV data
    ohlcv_df = data_fetcher.get_ohlcv(symbol, resolution='15', count=200)
    if ohlcv_df is None or ohlcv_df.empty:
        raise HTTPException(status_code=404, detail="No OHLCV data found.")

    # 2. Run analysis modules
    trend_result = trend_engine.get_bias(ohlcv_df)
    structure = smc_engine.get_structure(ohlcv_df)
    sentiment_result = sentiment_engine.get_confidence(symbol)
    entry_price = structure.get('key_level', ohlcv_df['close'].iloc[-1])

    # 3. Time-based analysis
    time_result = time_engine.estimate_entry_and_tp_time(ohlcv_df)

    # 4. Risk analysis
    risk_result = risk_engine.calculate_risk(entry_price, structure)

    # 5. TP and SL generation
    tp_data = tp_engine.generate_tp_prediction(trend_result, structure, sentiment_result)
    sl_level = sl_engine.generate_sl_level(entry_price, trend_result, structure)

    # 6. Aggregate signal
    signal = {
        "symbol": symbol,
        "trend_direction": trend_result.get('trend_direction', 'N/A'),
        "sentiment": sentiment_result.get('sentiment', 'N/A'),
        "bias_confidence": tp_data.get('bias_confidence', 0.0),
        "entry_price": entry_price,
        "entry_zone": time_result.get('best_entry_zone', 'N/A'),
        "estimated_entry_time": time_result.get('estimated_entry_time', 'N/A'),
        "tp_eta": time_result.get('tp_eta', 'N/A'),
        "tp_zone": tp_data.get('tp_zone', 'N/A'),
        "tp_levels": tp_data.get('levels', []),
        "sl_level": sl_level,
        "risk_profile": risk_result.get('risk_profile', 'N/A'),
        "suggested_lot_size": risk_result.get('suggested_lot_size', 0.0),
        "status": "ok",
        "error_message": None
    }

    # 7. Cache, email, and return
    set_cached_analysis(symbol, signal)
    send_email_report(symbol, signal)
    return signal


# Dynamic cors for multiple domain
def get_cors_origins():
    origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in origins.split(",")]

# --- Scheduler Setup ---
scheduler = AsyncIOScheduler(timezone="UTC")

def scheduled_analysis_job():
    """Job that runs analysis for all symbols in the user watchlist."""
    print(f"Scheduler triggered: Starting analysis for all watchlist symbols.")
    symbols_to_run = get_unique_symbols_from_watchlist()
    if not symbols_to_run:
        print("Watchlist is empty. Skipping scheduled run.")
        return
    for symbol in symbols_to_run:
        # Using background tasks to run analyses concurrently
        # This is a placeholder; a more robust solution might use a task queue
        run_full_analysis(symbol)
def normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown logic."""
    init_db()
    init_cache()
    print("Starting Jet Buddy Engine...")
    # Add cron jobs for market sessions (unchanged)
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=6, minute=55, id="pre_london")
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=12, minute=55, id="pre_ny")
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=22, minute=55, id="pre_asian")
    scheduler.start()
    print("Scheduler started with session-based cron jobs (UTC).")
    yield
    scheduler.shutdown()

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan, title="Jet Buddy Trading Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NEW ENDPOINTS (FIX #1 and #4) ---
@app.get("/market-data/{symbol}", tags=["On-Demand Data"])
async def get_market_data(symbol: str):
    """
    [FIX #1] Fetches and returns raw OHLCV market data for a given symbol,
    using the robust fallback logic.
    """
    normalized_symbol = normalize_symbol(symbol)
    try:
        df, note = data_fetcher.get_ohlcv_data(normalized_symbol)
        if df is None:
            raise HTTPException(status_code=404, detail=f"Market data not available for '{normalized_symbol}'.")
        
        # Convert DataFrame to a JSON-friendly format
        df_reset = df.reset_index()
        json_output = json.loads(df_reset.to_json(orient="records", date_format="iso"))
        
        return {"symbol": normalized_symbol, "source": note, "data": json_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sentiment/{symbol}", tags=["On-Demand Data"])
async def get_sentiment(symbol: str):
    """
    [FIX #4] Fetches and returns news-based sentiment analysis for a given symbol.
    """
    normalized_symbol = normalize_symbol(symbol)
    try:
        # The sentiment engine already uses Newsdata.io with a keyword fallback
        sentiment_result = sentiment_engine.analyze_sentiment(normalized_symbol)
        if "error" in sentiment_result:
             raise HTTPException(status_code=500, detail=sentiment_result["error"])
        
        return {
            "symbol": normalized_symbol,
            "dominant_sentiment": sentiment_result.get("sentiment"),
            "confidence": sentiment_result.get("confidence"),
            "source": "Newsdata.io with LLM/Keyword analysis"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- API Endpoints (Unchanged) ---

@app.post("/watchlist/add", status_code=201, tags=["Watchlist"])
def add_symbol_to_watchlist(item: WatchlistAddItem, background_tasks: BackgroundTasks):
    normalized = normalize_symbol(item.symbol)
    add_to_watchlist(item.symbol, normalized, item.email)
    background_tasks.add_task(run_full_analysis, normalized)
    return {"message": f"'{item.symbol}' (as '{normalized}') added to watchlist. Analysis triggered."}

@app.get("/watchlist", response_model=List[WatchlistItem], tags=["Watchlist"])
def get_watchlist():
    return get_full_watchlist()

@app.delete("/watchlist/remove/{item_id}", status_code=200, tags=["Watchlist"])
def remove_symbol_from_watchlist(item_id: int):
    remove_from_watchlist(item_id)
    return {"message": f"Item {item_id} removed from watchlist."}

@app.get("/analyze/{symbol}", response_model=AnalysisOutput, tags=["Analysis"])
async def get_analysis(symbol: str, background_tasks: BackgroundTasks):
    """
    Retrieves the latest cached analysis for a symbol.
    If no cache exists, it triggers a new analysis in the background.
    """
    symbol = symbol.upper()
    cached_data = get_cached_analysis(symbol)
    
    if cached_data:
        if cached_data.get("status") == "error":
             raise HTTPException(status_code=500, detail=cached_data.get("error_message"))
        return AnalysisOutput(**cached_data)
    else:
        # If not in cache, trigger a background analysis and return a pending status
        if symbol not in SYMBOLS_TO_TRACK:
            # For on-demand analysis of untracked symbols
             background_tasks.add_task(run_full_analysis, symbol)
        
        raise HTTPException(
            status_code=202, 
            detail=f"Analysis for {symbol} is not yet available. It has been scheduled. Please check back in a few minutes."
        )

@app.post("/analyze/force-run/{symbol}")
def force_run_analysis(symbol: str):
    normalized = normalize_symbol(symbol)
    result = analyze_symbol(normalized)  # your existing analysis function

    # Fetch email from watchlist
    email = get_email_by_symbol(normalized)
    if email:
        send_signal_email(to_email=email, symbol=normalized, analysis_data=result)
    
    return result

@app.get("/")
def root():
    return {"status": "Jet Buddy is running!"}

@app.get("/health/cache")
def check_cache():
    try:
        init_cache()
        return {"status": "ok", "message": "Cache initialized successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."}
    )

