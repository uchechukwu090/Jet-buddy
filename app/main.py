# ==============================================================================
# FILE: app/main.py
# ==============================================================================
# --- Description:
# The main application file. It sets up the FastAPI server, defines API
# endpoints, and orchestrates the analysis pipeline and scheduling.

# --- FastAPI App ---
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
from datetime import datetime
import os
import json

from app.config import settings
from app.models import AnalysisOutput, WatchlistAddItem, WatchlistItem
from app.caching import init_cache, set_cached_analysis, get_cached_analysis
from app.database import (
    init_db, add_to_watchlist, remove_from_watchlist,
    get_full_watchlist, get_unique_symbols_from_watchlist, get_emails_for_symbol
)
from app.symbol_normalizer import normalize_symbol
from app.email_sender import send_email_report
from app.modules import (
    data_fetcher, trend_engine, smc_engine, sentiment_engine,
    tp_engine, time_engine, aggregator, risk_engine
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Symbol Normalization ---
def normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()

# --- Analysis Pipeline ---
 def run_full_analysis(symbol: str):
     print(f"[{datetime.now()}] Running full analysis for {symbol}...")

-    ohlcv_df = data_fetcher.get_ohlcv(symbol, resolution='15', count=200)
+    # data_fetcher.get_ohlcv_data returns (DataFrame, note)
+    ohlcv_df, _ = data_fetcher.get_ohlcv_data(symbol)

     if ohlcv_df is None or ohlcv_df.empty:
         raise HTTPException(status_code=404, detail="No OHLCV data found.")

    trend_result = trend_engine.get_bias(ohlcv_df)
    structure = smc_engine.get_structure(ohlcv_df)
    sentiment_result = sentiment_engine.get_confidence(symbol)
    entry_price = structure.get('key_level', ohlcv_df['close'].iloc[-1])
    time_result = time_engine.estimate_entry_and_tp_time(ohlcv_df)
    risk_result = risk_engine.calculate_risk(entry_price, structure)
    tp_data = tp_engine.generate_tp_prediction(trend_result, structure, sentiment_result)
    sl_level = tp_data.get('sl_level', None)

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

    set_cached_analysis(symbol, signal)
    send_email_report(symbol, signal)
    return signal

# --- Scheduler Setup ---
scheduler = AsyncIOScheduler(timezone="UTC")

def scheduled_analysis_job():
    print("Scheduler triggered: Starting analysis for all watchlist symbols.")
    symbols_to_run = get_unique_symbols_from_watchlist()
    if not symbols_to_run:
        print("Watchlist is empty. Skipping scheduled run.")
        return
    for symbol in symbols_to_run:
        run_full_analysis(symbol)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_cache()
    print("Starting Jet Buddy Engine...")
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=6, minute=55, id="pre_london")
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=12, minute=55, id="pre_ny")
    scheduler.add_job(scheduled_analysis_job, 'cron', hour=22, minute=55, id="pre_asian")
    scheduler.start()
    print("Scheduler started with session-based cron jobs (UTC).")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="Jet Buddy Trading Engine")

# --- CORS Setup ---
def get_cors_origins():
    origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---
@app.get("/")
def root():
    return {"status": "Jet Buddy is running!"}

@app.get("/analyze/{symbol}", response_model=AnalysisOutput, tags=["Analysis"])
async def get_analysis(symbol: str, background_tasks: BackgroundTasks):
    symbol = symbol.upper()
    cached_data = get_cached_analysis(symbol)
    if cached_data:
        if cached_data.get("status") == "error":
            raise HTTPException(status_code=500, detail=cached_data.get("error_message"))
        return AnalysisOutput(**cached_data)
    else:
        background_tasks.add_task(run_full_analysis, symbol)
        raise HTTPException(
            status_code=202,
            detail=f"Analysis for {symbol} is not yet available. It has been scheduled. Please check back in a few minutes."
        )

@app.api_route("/watchlist/add", methods=["OPTIONS", "POST"], status_code=201, tags=["Watchlist"])
async def add_symbol_to_watchlist(request: Request):
    if request.method == "OPTIONS":
        return JSONResponse(content={"detail": "CORS preflight OK"}, status_code=200)

    body = await request.json()
    symbol = body.get("symbol")
    email = body.get("email")  # Optional

    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required.")

    normalized = normalize_symbol(symbol)
    add_to_watchlist(symbol, normalized, email)  # Handles None or multiple emails

    await run_in_threadpool(run_full_analysis, normalized)

    msg = f"'{symbol}' (as '{normalized}') added to watchlist. Analysis triggered."
    if email:
        msg += f" Signal will be sent to {email}."

    return {"message": msg}

@app.delete("/watchlist/remove/{item_id}", status_code=200, tags=["Watchlist"])
def remove_symbol_from_watchlist(item_id: int):
    remove_from_watchlist(item_id)
    return {"message": f"Item {item_id} removed from watchlist."}

@app.get("/market-data/{symbol}", tags=["On-Demand Data"])
async def get_market_data(symbol: str):
    normalized_symbol = normalize_symbol(symbol)
    try:
        df, note = data_fetcher.get_ohlcv_data(normalized_symbol)
        if df is None:
            raise HTTPException(status_code=404, detail=f"Market data not available for '{normalized_symbol}'.")
        df_reset = df.reset_index()
        json_output = json.loads(df_reset.to_json(orient="records", date_format="iso"))
        return {"symbol": normalized_symbol, "source": note, "data": json_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sentiment/{symbol}", tags=["On-Demand Data"])
async def get_sentiment(symbol: str):
    normalized_symbol = normalize_symbol(symbol)
    try:
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

@app.post("/analyze/force-run/{symbol}", response_model=AnalysisOutput)
def force_run_analysis(symbol: str):
    symbol = symbol.upper()
    result = run_full_analysis(symbol)
    return AnalysisOutput(**result)

@app.get("/health/cache")
def check_cache():
    try:
        init_cache()
        return {"status": "ok", "message": "Cache initialized successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})
