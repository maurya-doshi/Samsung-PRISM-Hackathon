# Skill.md — IPO Pulse Skill Definitions

Skills are discrete capabilities the agent can invoke. Each skill maps to a specific
API endpoint or bot command.

---

## Skill: stock-analysis

**Command:** `/analyze <ticker>`  
**API:** `GET /analysis?ticker=<ticker>`  
**Description:** Fetches 3 months of historical price data for a given ticker via yfinance.
Computes 20-day MA, 50-day MA, and 14-period RSI. Derives a BUY/SELL/HOLD signal from
the relationship between price, moving averages, and RSI thresholds.  
**Output:** Formatted Telegram message with price, indicators, signal, and AI explanation.  
**Fallback:** If the LLM API is unavailable, uses a rule-based explanation.

---

## Skill: ipo-tracker

**Command:** `/ipo`  
**API:** `GET /ipos?limit=<n>`  
**Description:** Returns a curated list of recent Indian IPO listings enriched with live
price data and day-over-day percentage change. Covers NSE-listed stocks.  
**Output:** Formatted list with company name, ticker, listing date, current price, and change %.

---

## Skill: price-alert

**Command:** `/alert <ticker> <price>`  
**Storage:** SQLite `alerts` table  
**Description:** Persists a price alert for the user. The heartbeat daemon checks every 2
minutes and sends a Telegram notification when the price crosses the target level.  
**Direction logic:** First heartbeat check locks in whether the target is above or below
current price. Alert fires when price crosses in the locked direction.

---

## Skill: portfolio-tracker

**Commands:** `/buy`, `/sell`, `/portfolio`  
**Storage:** SQLite `portfolio` table  
**Description:** Tracks user stock holdings with quantity and average cost basis.
Handles partial sells and averaging down/up on repeat buys.  
**Output:** Formatted portfolio view with total invested value.

---

## Skill: ai-explain

**API:** `POST /explain`  
**Description:** Sends structured analysis data to Claude (claude-haiku-4-5-20251001) for
a 2-3 sentence plain-English explanation aimed at retail investors. Gracefully falls back
to a rule-based explanation if the Anthropic API key is not configured.  
**Model:** claude-haiku-4-5-20251001 (fast, cost-effective for real-time responses)
