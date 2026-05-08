"""
Stock analysis module — fetches data via Alpha Vantage (primary) or yfinance (fallback).
"""

import asyncio
import logging
import os
from typing import Any

import httpx
import yfinance as yf
import pandas as pd

# yfinance emits noisy 404 warnings for retired Yahoo Finance endpoints (fc.yahoo.com).
# Silence them — the actual history() calls use a different endpoint and work fine.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_AV_BASE = "https://www.alphavantage.co/query"


def _av_key() -> str | None:
    return os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("STOCK_API_KEY")


def _to_av_symbol(ticker: str) -> str:
    """Convert yfinance ticker suffix to Alpha Vantage format."""
    # If no exchange suffix provided, default to NSE (.NS)
    if "." not in ticker:
        ticker = ticker + ".NS"
    return ticker.replace(".NS", ".NSE").replace(".BO", ".BSE")


def _to_yf_symbol(ticker: str) -> str:
    """Convert common/AV suffixes to yfinance format."""
    # Ensure it ends with .NS or .BO for Indian stocks
    if "." not in ticker:
        return ticker + ".NS"
    return ticker.replace(".NSE", ".NS").replace(".BSE", ".BO")



# ── Technical indicators ───────────────────────────────────────────────────────

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
    if price > ma20 > ma50 and rsi < 70:
        return "buy"
    if price < ma20 < ma50 and rsi > 30:
        return "sell"
    return "hold"


# ── Alpha Vantage data fetchers ────────────────────────────────────────────────

def _fetch_analysis_av(ticker: str, api_key: str) -> dict[str, Any]:
    """Fetch daily time series from Alpha Vantage and compute indicators."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": _to_av_symbol(ticker),
        "outputsize": "compact",
        "apikey": api_key,
    }
    with httpx.Client(timeout=15.0) as client:
        res = client.get(_AV_BASE, params=params)
        res.raise_for_status()
        data = res.json()

    if "Note" in data:
        raise RuntimeError("Alpha Vantage rate limit reached.")
    if "Error Message" in data or "Time Series (Daily)" not in data:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol.")

    time_series = data["Time Series (Daily)"]
    dates = sorted(time_series.keys())  # ascending

    if len(dates) < 50:
        raise ValueError(f"Not enough historical data for '{ticker}' to compute MA50.")

    close = pd.Series(
        [float(time_series[d]["4. close"]) for d in dates],
        index=pd.to_datetime(dates),
    )

    price  = round(float(close.iloc[-1]), 2)
    ma20   = round(float(close.rolling(20).mean().iloc[-1]), 2)
    ma50   = round(float(close.rolling(50).mean().iloc[-1]), 2)
    rsi    = _compute_rsi(close)
    signal = _compute_signal(price, ma20, ma50, rsi)

    return {"ticker": ticker, "price": price, "ma20": ma20, "ma50": ma50, "rsi": rsi, "signal": signal}


def _fetch_quote_av(ticker: str, api_key: str) -> tuple[float | None, float | None]:
    """Fetch current price and daily change % via Alpha Vantage GLOBAL_QUOTE."""
    av_symbol = _to_av_symbol(ticker)
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": av_symbol,
        "apikey": api_key,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(_AV_BASE, params=params)
            res.raise_for_status()
            data = res.json()

        # Handle rate limiting
        if "Note" in data:
            logging.warning(f"AV rate limit hit during quote for {av_symbol}")
            return None, None

        quote = data.get("Global Quote", {})
        if quote and quote.get("05. price"):
            price = round(float(quote["05. price"]), 2)
            change_str = quote.get("10. change percent", "").replace("%", "").strip()
            change_pct = round(float(change_str), 2) if change_str else None
            return price, change_pct

        # If GLOBAL_QUOTE returned empty (common for some intl stocks), fallback to TIME_SERIES_DAILY
        logging.info(f"AV GLOBAL_QUOTE empty for {av_symbol}, falling back to DAILY")
        params["function"] = "TIME_SERIES_DAILY"
        params["outputsize"] = "compact"
        with httpx.Client(timeout=15.0) as client:
            res = client.get(_AV_BASE, params=params)
            res.raise_for_status()
            data = res.json()

        if "Time Series (Daily)" in data:
            ts = data["Time Series (Daily)"]
            dates = sorted(ts.keys())
            if not dates: return None, None
            
            latest_date = dates[-1]
            price = round(float(ts[latest_date]["4. close"]), 2)
            
            change_pct = None
            if len(dates) >= 2:
                prev_date = dates[-2]
                prev_price = float(ts[prev_date]["4. close"])
                change_pct = round((price - prev_price) / prev_price * 100, 2)
            
            return price, change_pct

    except Exception as e:
        logging.error(f"AV fetch error for {av_symbol}: {e}")
    
    return None, None



# ── yfinance fallback fetchers ─────────────────────────────────────────────────

def _fetch_analysis_yf(ticker: str) -> dict[str, Any]:
    yf_symbol = _to_yf_symbol(ticker)
    stock = yf.Ticker(yf_symbol)
    hist = stock.history(period="3mo")

    if hist.empty:
        raise ValueError(f"No data found for ticker '{yf_symbol}'. Check the symbol.")


    close = hist["Close"]

    if len(close) < 50:
        raise ValueError(f"Not enough historical data for '{ticker}' to compute MA50.")

    price  = round(float(close.iloc[-1]), 2)
    ma20   = round(float(close.rolling(20).mean().iloc[-1]), 2)
    ma50   = round(float(close.rolling(50).mean().iloc[-1]), 2)
    rsi    = _compute_rsi(close)
    signal = _compute_signal(price, ma20, ma50, rsi)

    return {"ticker": ticker, "price": price, "ma20": ma20, "ma50": ma50, "rsi": rsi, "signal": signal}


# ── Public API ─────────────────────────────────────────────────────────────────

def _fetch_analysis_sync(ticker: str) -> dict[str, Any]:
    api_key = _av_key()
    if api_key:
        try:
            return _fetch_analysis_av(ticker, api_key)
        except (RuntimeError, Exception):
            pass  # rate limited or network error — fall through to yfinance
    return _fetch_analysis_yf(ticker)


async def get_stock_analysis(ticker: str) -> dict[str, Any]:
    """Run the blocking data fetch in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_analysis_sync, ticker)


# ── IPO Listings ───────────────────────────────────────────────────────────────

# Curated list of recent notable Indian IPOs (NSE tickers).
# yfinance and Alpha Vantage don't provide a live IPO calendar,
# so we maintain a seed list and enrich each entry with live price data.
RECENT_IPOS = [
    {"ticker": "BAJAJHFL.NS",  "name": "Bajaj Housing Finance",     "ipo_date": "2024-09-16"},
    {"ticker": "HYUNDAI.NS",   "name": "Hyundai Motor India",        "ipo_date": "2024-10-22"},
    {"ticker": "SWIGGY.NS",    "name": "Swiggy",                     "ipo_date": "2024-11-13"},
    {"ticker": "SAGILITY.NS",  "name": "Sagility India",             "ipo_date": "2024-11-12"},
    {"ticker": "NTPCGREEN.NS", "name": "NTPC Green Energy",          "ipo_date": "2024-11-27"},
    {"ticker": "ACMESOLAR.NS",      "name": "ACME Solar Holdings",        "ipo_date": "2024-11-13"},
    {"ticker": "MOBIKWIK.NS",  "name": "One Mobikwik Systems",       "ipo_date": "2024-12-18"},
    {"ticker": "IDENTICAL-SM.NS", "name": "Identical Brain Studios",    "ipo_date": "2025-01-01"},
    {"ticker": "HEXAWARE.NS",  "name": "Hexaware Technologies",      "ipo_date": "2025-02-12"},
    {"ticker": "DELHIVERY.NS", "name": "Delhivery",                  "ipo_date": "2022-05-24"},
]


def _fetch_ipo_data_sync(entries: list[dict], limit: int) -> list[dict]:
    api_key = _av_key()
    results = []

    for entry in entries[:limit]:
        current_price, change_pct = None, None

        # Try Alpha Vantage GLOBAL_QUOTE first
        if api_key:
            try:
                current_price, change_pct = _fetch_quote_av(entry["ticker"], api_key)
            except Exception:
                pass

        # Fall back to yfinance if Alpha Vantage gave nothing
        if current_price is None:
            try:
                yf_symbol = _to_yf_symbol(entry["ticker"])
                hist = yf.Ticker(yf_symbol).history(period="5d")
                if not hist.empty:
                    current_price = round(float(hist["Close"].iloc[-1]), 2)
                    if len(hist) >= 2:
                        prev = float(hist["Close"].iloc[-2])
                        change_pct = round((current_price - prev) / prev * 100, 2)
            except Exception as e:
                logging.error(f"yfinance fetch error for {entry['ticker']}: {e}")


        results.append({
            "ticker":        entry["ticker"],
            "name":          entry["name"],
            "ipo_date":      entry["ipo_date"],
            "current_price": current_price,
            "change_pct":    change_pct,
        })

    return results


async def get_ipo_listings(limit: int = 10) -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_ipo_data_sync, RECENT_IPOS, limit)
