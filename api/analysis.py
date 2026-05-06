"""
Stock analysis module — fetches data via yfinance and computes technical indicators.
"""

import asyncio
from typing import Any
import yfinance as yf
import pandas as pd


def _compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def _compute_signal(price: float, ma20: float, ma50: float, rsi: float) -> str:
    """Simple rule-based signal."""
    if price > ma20 > ma50 and rsi < 70:
        return "buy"
    if price < ma20 < ma50 and rsi > 30:
        return "sell"
    return "hold"


def _fetch_analysis_sync(ticker: str) -> dict[str, Any]:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")

    if hist.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol.")

    close = hist["Close"]

    if len(close) < 50:
        raise ValueError(f"Not enough historical data for '{ticker}' to compute MA50.")

    price = round(float(close.iloc[-1]), 2)
    ma20  = round(float(close.rolling(20).mean().iloc[-1]), 2)
    ma50  = round(float(close.rolling(50).mean().iloc[-1]), 2)
    rsi   = _compute_rsi(close)
    signal = _compute_signal(price, ma20, ma50, rsi)

    return {
        "ticker": ticker,
        "price":  price,
        "ma20":   ma20,
        "ma50":   ma50,
        "rsi":    rsi,
        "signal": signal,
    }


async def get_stock_analysis(ticker: str) -> dict[str, Any]:
    """Run the blocking yfinance call in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_analysis_sync, ticker)


# ── IPO Listings ───────────────────────────────────────────────────────────────

# Curated list of recent notable Indian IPOs (NSE tickers)
# yfinance doesn't have a live IPO calendar, so we maintain a seed list
# and enrich each entry with live price data where available.
RECENT_IPOS = [
    {"ticker": "BAJAJHFL.NS",  "name": "Bajaj Housing Finance",     "ipo_date": "2024-09-16"},
    {"ticker": "HYUNDAI.NS",   "name": "Hyundai Motor India",        "ipo_date": "2024-10-22"},
    {"ticker": "SWIGGY.NS",    "name": "Swiggy",                     "ipo_date": "2024-11-13"},
    {"ticker": "SAGILITY.NS",  "name": "Sagility India",             "ipo_date": "2024-11-12"},
    {"ticker": "NTPCGREEN.NS", "name": "NTPC Green Energy",          "ipo_date": "2024-11-27"},
    {"ticker": "ACME.NS",      "name": "ACME Solar Holdings",        "ipo_date": "2024-11-13"},
    {"ticker": "MOBIKWIK.NS",  "name": "One Mobikwik Systems",       "ipo_date": "2024-12-18"},
    {"ticker": "IDENTICAL.NS", "name": "Identical Brain Studios",    "ipo_date": "2025-01-01"},
    {"ticker": "HEXAWARE.NS",  "name": "Hexaware Technologies",      "ipo_date": "2025-02-12"},
    {"ticker": "DELHIVERY.NS", "name": "Delhivery",                  "ipo_date": "2022-05-24"},
]


def _fetch_ipo_data_sync(entries: list[dict], limit: int) -> list[dict]:
    results = []
    for entry in entries[:limit]:
        try:
            stock = yf.Ticker(entry["ticker"])
            hist = stock.history(period="5d")
            if hist.empty:
                current_price = None
                change_pct = None
            else:
                current_price = round(float(hist["Close"].iloc[-1]), 2)
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])
                    change_pct = round((current_price - prev) / prev * 100, 2)
                else:
                    change_pct = None
        except Exception:
            current_price = None
            change_pct = None

        results.append({
            "ticker":        entry["ticker"],
            "name":          entry["name"],
            "ipo_date":      entry["ipo_date"],
            "current_price": current_price,
            "change_pct":    change_pct,
        })

    return results


async def get_ipo_listings(limit: int = 10) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_ipo_data_sync, RECENT_IPOS, limit)
