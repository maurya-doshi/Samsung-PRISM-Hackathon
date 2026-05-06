"""
LLM explanation module — sends analysis data to Claude for plain-English insight.
Falls back gracefully if the API key is not set.
"""

import os
from typing import Any

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # Fast + cheap for real-time bot responses

PROMPT_TEMPLATE = """You are a concise financial analyst assistant for Indian retail investors.

Stock: {ticker}
Current Price: ₹{price}
20-day MA: ₹{ma20}
50-day MA: ₹{ma50}
RSI (14): {rsi}
Signal: {signal}

In 2-3 sentences, explain what this data means for a retail investor. Be specific about the numbers. Use plain language, no jargon. Do not give direct buy/sell advice — frame it as analysis only."""


async def get_llm_explanation(data: dict[str, Any]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or not _ANTHROPIC_AVAILABLE:
        return _rule_based_explanation(data)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = PROMPT_TEMPLATE.format(**data)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    except Exception:
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
