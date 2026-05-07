"""
LLM explanation module — sends analysis data to an LLM for plain-English insight.

Priority:
  1. Claude Haiku (Anthropic API) — if ANTHROPIC_API_KEY is set
  2. Local Ollama — if running at OLLAMA_BASE_URL (default: http://localhost:11434)
  3. Rule-based fallback — always works offline
"""

import os
from typing import Any

import httpx

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # Fast + cheap for real-time bot responses
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

PROMPT_TEMPLATE = """You are a concise financial analyst assistant for Indian retail investors.

Stock: {ticker}
Current Price: ₹{price}
20-day MA: ₹{ma20}
50-day MA: ₹{ma50}
RSI (14): {rsi}
Signal: {signal}

In 2-3 sentences, explain what this data means for a retail investor. Be specific about the numbers. Use plain language, no jargon. Do not give direct buy/sell advice — frame it as analysis only."""


async def get_llm_explanation(data: dict[str, Any]) -> str:
    prompt = PROMPT_TEMPLATE.format(**data)

    # 1. Claude Haiku via Anthropic API
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and _ANTHROPIC_AVAILABLE:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception:
            pass  # fall through to Ollama

    # 2. Local Ollama
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()
    except Exception:
        pass  # fall through to rule-based

    # 3. Rule-based offline fallback
    return _rule_based_explanation(data)


def _rule_based_explanation(data: dict[str, Any]) -> str:
    """Offline fallback — generates a readable explanation without any API call."""
    ticker = data["ticker"]
    price  = data["price"]
    ma20   = data["ma20"]
    ma50   = data["ma50"]
    rsi    = data["rsi"]
    signal = data["signal"].upper()

    trend = "above" if price > ma20 else "below"
    momentum = "above" if ma20 > ma50 else "below"

    rsi_note = ""
    if rsi > 70:
        rsi_note = "RSI is above 70, indicating the stock may be overbought."
    elif rsi < 30:
        rsi_note = "RSI is below 30, suggesting the stock may be oversold."
    else:
        rsi_note = f"RSI at {rsi} is in neutral territory."

    return (
        f"{ticker} is trading at ₹{price}, currently {trend} its 20-day MA (₹{ma20}). "
        f"The short-term average is {momentum} the 50-day MA (₹{ma50}), indicating a "
        f"{'bullish' if momentum == 'above' else 'bearish'} trend. {rsi_note} "
        f"Overall signal: {signal}."
    )
