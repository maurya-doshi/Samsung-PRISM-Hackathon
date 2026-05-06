"""
IPO Pulse — FastAPI Backend
Provides stock analysis and AI-powered explanations for the Telegram bot.
"""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from .analysis import get_stock_analysis, get_ipo_listings
from .explain import get_llm_explanation

load_dotenv()

app = FastAPI(
    title="IPO Pulse API",
    description="Stock analysis and IPO tracking backend for the Telegram bot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────────

class AnalysisData(BaseModel):
    ticker: str
    price: float
    ma20: float
    ma50: float
    rsi: float
    signal: str


class ExplainRequest(BaseModel):
    ticker: str
    price: float
    ma20: float
    ma50: float
    rsi: float
    signal: str


class ExplainResponse(BaseModel):
    explanation: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "IPO Pulse API"}


@app.get("/analysis", response_model=AnalysisData)
async def analysis(ticker: str = Query(..., description="Stock ticker symbol")):
    """
    Fetch live stock data and compute technical indicators.
    Returns price, MA20, MA50, RSI, and a BUY/SELL/HOLD signal.
    """
    try:
        result = await get_stock_analysis(ticker.upper())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {e}")


@app.post("/explain", response_model=ExplainResponse)
async def explain(data: ExplainRequest):
    """
    Send analysis data to Claude (or fallback message) and return a plain-English explanation.
    """
    try:
        explanation = await get_llm_explanation(data.model_dump())
        return ExplainResponse(explanation=explanation)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")


@app.get("/ipos")
async def ipos(limit: int = Query(10, ge=1, le=50)):
    """
    Return a list of recent/upcoming IPO listings fetched via yfinance.
    """
    try:
        result = await get_ipo_listings(limit=limit)
        return {"ipos": result, "count": len(result)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IPO fetch failed: {e}")
