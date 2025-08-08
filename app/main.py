# ==============================================================================
# FILE: app/main.py
# ==============================================================================
# The main application file. It sets up the FastAPI server, defines API
# endpoints, orchestrates the analysis pipeline and scheduling.
# ==============================================================================

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
from datetime import datetime
import os
import json

from typing import List, Optional

from app.config import settings
from app.models import AnalysisOutput, WatchlistAddItem, WatchlistItem
from app.caching import init_cache, set_cached_analysis, get_cached_analysis
from app.database import (
    init_db,
    add_to_watchlist,
    remove_from_watchlist,
    get_full_watchlist,
    get_unique_symbols_from_watchlist,
    get_emails_for_symbol,
)
from app.symbol_normalizer import normalize_symbol, AssetClass, Provider
from app.email_sender import send_email_report
from app.modules import (
    data_fetcher,
    trend_engine,
    smc_engine,
    sentiment_engine,
    tp_engine,
    time_engine,
    aggregator,
    risk_engine,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ------------------------------------------------------------------------------
# Analysis Pipeline
# ------------------------------------------------------------------------------
def run_full_analysis(
    symbol: str,
    asset: AssetClass = AssetClass.STOCK,
    provider: Provider = Provider.FINNHUB
):
    # 1. Normalize the incoming symbol for the chosen asset class + provider
    norm = normalize_symbol(symbol, asset=asset, provider=provider)
    print(f"[{datetime.now()}] Running full analysis for {norm} (original: {symbol})…")

    # 2. Fetch OHLCV data using the normalized symbol
    ohlcv_df, _ = data_fetcher.get_ohlcv_data(norm)
    if ohlcv_df is None or ohlcv_df.empty:
        raise HTTPException(status_code=404, detail=f"No OHLCV data found for '{norm}'.")

    # 3. Core analysis engines
    trend_result = trend_engine.get_bias(ohlcv_df)
    structure = smc_engine.get_structure(ohlcv_df)
    sentiment_result = sentiment_engine.get_confidence(norm)
    entry_price = structure.get("key_level", ohlcv_df["close"].iloc[-1])
    time_result = time_engine.estimate_entry_and_tp_time(ohlcv_df)
    risk_result = risk_engine.calculate_risk(entry_price, structure)
    tp_data = tp_engine.generate_tp_prediction(trend_result, structure, sentiment_result)
    sl_level = tp_data.get("sl_level")

    # 4. Assemble signal payload
    signal = {
        "symbol": norm,
        "trend_direction": trend_result.get("trend_direction", "N/A"),
        "sentiment": sentiment_result.get("sentiment", "N/A"),
        "bias_confidence": tp_data.get("bias_confidence", 0.0),
        "entry_price": entry_price,
        "entry_zone": time_result.get("best_entry_zone", "N/A"),
        "estimated_entry_time": time_result.get("estimated_entry_time", "N/A"),
        "tp_eta": time_result.get("tp_eta", "N/A"),
        "tp_zone": tp_data.get("tp_zone", "N/A"),
        "tp_levels": tp_data.get("levels", []),
        "sl_level": sl_level,
        "risk_profile": risk_result.get("risk_profile", "N/A"),
        "suggested_lot_size": risk_result.get("suggested_lot_size", 0.0),
        "status": "ok",
        "error_message": None,
    }

    # 5. Cache & report
    set_cached_analysis(norm, signal)
    send_email_report(norm, signal)

    return signal


# ------------------------------------------------------------------------------
# Scheduler Setup
# ------------------------------------------------------------------------------
scheduler = AsyncIOScheduler(timezone="UTC")


def scheduled_analysis_job():
    print("Scheduler triggered: Starting analysis for all watchlist symbols.")
    symbols_to_run = get_unique_symbols_from_watchlist()
    if not symbols_to_run:
        print("Watchlist is empty. Skipping scheduled run.")
        return
    for sym in symbols_to_run:
        run_full_analysis(sym)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_cache()
    print("Starting Jet Buddy Engine...")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=6, minute=55, id="pre_london")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=12, minute=55, id="pre_ny")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=22, minute=55, id="pre_asian")
    scheduler.start()
    print("Scheduler started with session-based cron jobs (UTC).")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan, title="Jet Buddy Trading Engine")


# ------------------------------------------------------------------------------
# CORS Setup
# ------------------------------------------------------------------------------
def get_cors_origins() -> List[str]:
    origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in origins.split(",")]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------
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

    background_tasks.add_task(run_full_analysis, symbol)
    raise HTTPException(
        status_code=202,
        detail=(
            f"Analysis for {symbol} is not yet available. "
            "It has been scheduled. Please check back in a few minutes."
        ),
    )


@app.api_route("/watchlist/add", methods=["OPTIONS", "POST"], status_code=201, tags=["Watchlist"])
async def add_symbol_to_watchlist(item: WatchlistAddItem, background_tasks: BackgroundTasks):
    """
    WatchlistAddItem has:
      - symbol: str (required)
      - email: Optional[str]
    """
    normalized = normalize_symbol(item.symbol)
    add_to_watchlist(item.symbol, normalized, item.email)  

    # Trigger analysis in the background:
    background_tasks.add_task(run_full_analysis, normalized)

    msg = f"'{item.symbol}' (as '{normalized}') added to watchlist. Analysis triggered."
    if item.email:
        msg += f" Signal will be sent to {item.email}."

    return {"message": msg}


@app.get("/watchlist", response_model=List[WatchlistItem], tags=["Watchlist"])
def get_watchlist():
    """
    Return all items in the watchlist so your front end can fetch them.
    """
    return get_full_watchlist()


@app.delete("/watchlist/remove/{item_id}", status_code=200, tags=["Watchlist"])
def remove_symbol_from_watchlist(item_id: int):
    remove_from_watchlist(item_id)
    return {"message": f"Item {item_id} removed from watchlist."}


@app.get("/market-data/{symbol}", tags=["On-Demand Data"])
async def get_market_data(symbol: str):
    norm = normalize_symbol(symbol)
    try:
        df, note = data_fetcher.get_ohlcv_data(norm)
        if df is None:
            raise HTTPException(status_code=404, detail=f"Market data not available for '{norm}'.")
        records = json.loads(df.reset_index().to_json(orient="records", date_format="iso"))
        return {"symbol": norm, "source": note, "data": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentiment/{symbol}", tags=["On-Demand Data"])
async def get_sentiment(symbol: str):
    norm = normalize_symbol(symbol)
    try:
        res = sentiment_engine.analyze_sentiment(norm)
        if "error" in res:
            raise HTTPException(status_code=500, detail=res["error"])
        return {
            "symbol": norm,
            "dominant_sentiment": res.get("sentiment"),
            "confidence": res.get("confidence"),
            "source": "Newsdata.io with LLM/Keyword analysis",
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
