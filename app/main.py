# ==============================================================================
# FILE: app/main.py
# ==============================================================================
# --- Description:
# The main application file. It sets up the FastAPI server, defines API
# endpoints, and orchestrates the analysis pipeline and scheduling.

from fastapi import FastAPI, HTTPException, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

# Import all modules and components
from app.config import settings
from app.models import AnalysisOutput
from app.caching import init_cache, set_cached_analysis, get_cached_analysis

from app.modules import data_fetcher
from app.modules import trend_engine
from app.modules import smc_engine
from app.modules import sentiment_engine
from app.modules import time_engine
from app.modules import aggregator
from app.modules import risk_engine

# --- Analysis Pipeline ---
def run_full_analysis(symbol: str):
    """
    Orchestrates the entire analysis pipeline for a given symbol.
    """
    print(f"[{datetime.now()}] Running full analysis for {symbol}...")
    
    # 1. Fetch Data
    # Using Finnhub as the primary source for OHLCV
    ohlcv_df = data_fetcher.get_finnhub_ohlcv(symbol, resolution='15', count=200)
    if ohlcv_df is None or ohlcv_df.empty:
        error_result = {"status": "error", "error_message": f"Could not fetch market data for {symbol}."}
        set_cached_analysis(symbol, error_result)
        return

    # 2. Run Individual Analysis Modules
    trend_result = trend_engine.analyze_trend(ohlcv_df)
    smc_result = smc_engine.analyze_smc_structure(ohlcv_df)
    sentiment_result = sentiment_engine.analyze_sentiment(symbol)
    
    # 3. Aggregate Signals
    aggregator_result = aggregator.aggregate_signals(trend_result, sentiment_result, smc_result)
    
    # 4. Time & Volatility Estimation
    entry_zone = smc_result.get('order_block', {}).get('zone') if smc_result.get('order_block') else None
    time_result = time_engine.estimate_time_and_volatility(ohlcv_df, entry_zone)

    # 5. Risk Management
    risk_result = risk_engine.get_position_size(
        confidence=aggregator_result['bias_confidence'],
        volatility=time_result['volatility']
    )

    # 6. Format Final Output
    final_output = {
        "trend_direction": trend_result.get('trend_direction', 'N/A'),
        "sentiment": sentiment_result.get('sentiment', 'N/A'),
        "bias_confidence": aggregator_result.get('bias_confidence', 0.0),
        "entry_zone": time_result.get('best_entry_zone', 'N/A'),
        "estimated_entry_time": time_result.get('estimated_entry_time', 'N/A'),
        "tp_eta": time_result.get('tp_eta', 'N/A'),
        "risk_profile": risk_result.get('risk_profile', 'N/A'),
        "suggested_lot_size": risk_result.get('suggested_lot_size', 0.0),
        "status": "ok",
        "error_message": None
    }
    
    # Cache the final result
    set_cached_analysis(symbol, final_output)
    print(f"[{datetime.now()}] Analysis for {symbol} complete and cached.")


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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Jet Buddy Engine...")
    init_db()
    
    # ADJUSTMENT 1: Use cron triggers for major market sessions
    scheduler.add_job(
        scheduled_analysis_job, 
        'cron', 
        hour=6, 
        minute=55, 
        id="pre_london_run",
        name="Run analysis before London open"
    )
    scheduler.add_job(
        scheduled_analysis_job, 
        'cron', 
        hour=12, 
        minute=55, 
        id="pre_ny_run",
        name="Run analysis before New York open"
    )
    scheduler.add_job(
        scheduled_analysis_job, 
        'cron', 
        hour=22, 
        minute=55, 
        id="pre_asian_run",
        name="Run analysis before Asian open"
    )
    
    scheduler.start()
    print("Scheduler started with session-based cron jobs (times are in UTC).")
    yield
    scheduler.shutdown()

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan, title="Jet Buddy Trading Engine")

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
async def get_analysis(symbol: str):
    normalized_symbol = normalize_symbol(symbol)
    cached_data = get_cached_analysis(normalized_symbol)
    if not cached_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Analysis for '{symbol}' not found. Add it to the watchlist to generate a report."
        )
    return AnalysisOutput(**cached_data)

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)

@app.get("/", tags=["Status"])
def read_root():
    """Root endpoint providing system status."""
    return {"message": f"Welcome to the {settings.app_name}", "status": "running"}

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

@app.post("/analyze/force-run/{symbol}", tags=["Analysis"])
async def force_run_analysis(symbol: str, background_tasks: BackgroundTasks):
    """
    Forces an immediate re-analysis of a symbol in the background.
    """
    symbol = symbol.upper()
    background_tasks.add_task(run_full_analysis, symbol)
    return {"message": f"A new analysis for {symbol} has been triggered in the background."}
