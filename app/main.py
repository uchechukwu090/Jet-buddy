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
    # 1) Normalize symbol for the chosen asset + provider
    norm = normalize_symbol(symbol, asset=asset, provider=provider)
    print(f"[{datetime.now()}] Running full analysis for {norm} (original: {symbol})…")

    # 2) Attempt primary provider
    used_provider = provider
    try:
        ohlcv_df, source = data_fetcher.get_ohlcv_data(
            symbol,
            interval="15min",
            output_size=200,
            asset=asset,
            provider=used_provider,
        )
        # raise if provider returned a None or empty DataFrame
        if ohlcv_df is None or ohlcv_df.empty:
            raise ValueError(f"No data from {used_provider}")
    except Exception as primary_exc:
        # Only fallback if primary was Finnhub
        if provider == Provider.FINNHUB:
            print(f"{provider.value.capitalize()} failed ({primary_exc}). Falling back to Twelve Data.")
            used_provider = Provider.TWELVEDATA
            ohlcv_df, source = data_fetcher.get_ohlcv_data(
                symbol,
                interval="15min",
                output_size=200,
                asset=asset,
                provider=used_provider,
            )
            if ohlcv_df is None or ohlcv_df.empty:
                raise HTTPException(
                    status_code=502,
                    detail=f"No data from fallback provider ({used_provider.value})."
                )
        else:
            # If primary wasn’t Finnhub (e.g. you explicitly asked for Twelve Data) rethrow
            raise HTTPException(
                status_code=502,
                detail=f"Data fetch error from {used_provider.value}: {primary_exc}"
            )

    # 3) Core analysis on the fetched DataFrame
    trend_result = trend_engine.get_bias(ohlcv_df)
    structure    = smc_engine.get_structure(ohlcv_df)
    sentiment    = sentiment_engine.get_confidence(norm)
    entry_price  = structure.get("key_level", ohlcv_df["close"].iloc[-1])
    time_res     = time_engine.estimate_entry_and_tp_time(ohlcv_df)
    risk_res     = risk_engine.calculate_risk(entry_price, structure)
    tp_data      = tp_engine.generate_tp_prediction(trend_result, structure, sentiment)
    sl_level     = tp_data.get("sl_level")

    # 4) Assemble the signal
    signal = {
        "symbol": norm,
        "provider": used_provider.value,
        "source": source,
        "trend_direction": trend_result.get("trend_direction", "N/A"),
        "sentiment": sentiment.get("sentiment", "N/A"),
        "bias_confidence": tp_data.get("bias_confidence", 0.0),
        "entry_price": entry_price,
        "entry_zone": time_res.get("best_entry_zone", "N/A"),
        "estimated_entry_time": time_res.get("estimated_entry_time", "N/A"),
        "tp_eta": time_res.get("tp_eta", "N/A"),
        "tp_zone": tp_data.get("tp_zone", "N/A"),
        "tp_levels": tp_data.get("levels", []),
        "sl_level": sl_level,
        "risk_profile": risk_res.get("risk_profile", "N/A"),
        "suggested_lot_size": risk_res.get("suggested_lot_size", 0.0),
        "status": "ok",
        "error_message": None,
    }

    # 5) Cache & send email
    set_cached_analysis(norm, signal)
    send_email_report(norm, signal)

    return signal


# ------------------------------------------------------------------------------
# Scheduler Setup
# ------------------------------------------------------------------------------
scheduler = AsyncIOScheduler(timezone="UTC")


def scheduled_analysis_job():
    print("Scheduler triggered: Starting analysis for all watchlist symbols.")
    symbols = get_unique_symbols_from_watchlist()
    if not symbols:
        print("Watchlist is empty. Skipping scheduled run.")
        return
    for sym in symbols:
        run_full_analysis(sym)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_cache()
    print("Starting Jet Buddy Engine…")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=6, minute=55, id="pre_london")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=12, minute=55, id="pre_ny")
    scheduler.add_job(scheduled_analysis_job, "cron", hour=22, minute=55, id="pre_asian")
    scheduler.start()
    print("Scheduler started with cron jobs (UTC).")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan, title="Jet Buddy Trading Engine")


# ------------------------------------------------------------------------------
# CORS Setup
# ------------------------------------------------------------------------------
def get_cors_origins() -> List[str]:
    origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [o.strip() for o in origins.split(",")]

ALLOWED_ORIGINS = [
    "https://9fcb73c8-5bbb-4200-a5b9-3f3dd8635e07.canvases.tempo.build",
    "http://localhost:5173",
    "http://localhost:3000",
    # add any other frontends you use
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # keep false if you aren’t sending cookies/auth
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
    cached = get_cached_analysis(symbol)

    if cached:
        if cached.get("status") == "error":
            raise HTTPException(status_code=500, detail=cached.get("error_message"))
        return AnalysisOutput(**cached)

    background_tasks.add_task(run_full_analysis, symbol)
    raise HTTPException(
        status_code=202,
        detail=(
            f"Analysis for {symbol} is being processed. "
            "Please retry in a few minutes."
        ),
    )


@app.post("/watchlist/add", status_code=201, tags=["Watchlist"])
async def add_symbol_to_watchlist(item: WatchlistAddItem, background_tasks: BackgroundTasks):
    normalized = normalize_symbol(item.symbol)
    add_to_watchlist(item.symbol, normalized, item.email)
    background_tasks.add_task(run_full_analysis, normalized)
    msg = f"Added '{item.symbol}' (normalized to '{normalized}') to watchlist."
    if item.email:
        msg += f" Alerts will be sent to {item.email}."
    return {"message": msg}

@app.get("/watchlist", response_model=List[WatchlistItem], tags=["Watchlist"])
def get_watchlist():
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
            raise HTTPException(status_code=404, detail=f"No market data for '{norm}'.")
        records = json.loads(df.reset_index().to_json(orient="records", date_format="iso"))
        return {"symbol": norm, "source": note, "data": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentiment/{symbol}", tags=["On-Demand Data"])
async def get_sentiment(symbol: str):
    norm = normalize_symbol(symbol)
    try:
        res = sentiment_engine.analyze_sentiment(norm)
        if res.get("error"):
            raise HTTPException(status_code=500, detail=res["error"])
        return {
            "symbol": norm,
            "dominant_sentiment": res.get("sentiment"),
            "confidence": res.get("confidence"),
            "source": "Newsdata.io + LLM/Keyword analysis",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/force-run/{symbol}", response_model=AnalysisOutput, tags=["Analysis"])
def force_run_analysis(
    symbol: str,
    asset: AssetClass = AssetClass.STOCK,
    provider: Provider = Provider.FINNHUB
):
    return run_full_analysis(symbol, asset=asset, provider=provider)


@app.get("/health/cache", tags=["Health"])
def check_cache():
    try:
        init_cache()
        return {"status": "ok", "message": "Cache initialized successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})
