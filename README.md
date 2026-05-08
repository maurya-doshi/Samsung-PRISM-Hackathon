# TEAM NUMBER: RIT_ByteX

## Stock Pulse - An Autonomous Stock Intelligence Assistant With Telegram Integration.

> A conversational AI agent built on the OpenClaw framework that delivers real-time Indian stock analysis, price alerts, and portfolio tracking — directly in Telegram.

**Hackathon:** Samsung PRISM × OpenClaw — "Clash of the Claws" 2026  
**Theme:** Theme 3 — Productivity (Delegate tasks to the intelligent orchestrator)

---

## What It Does

| Command | Description |
|---|---|
| `/analyze RELIANCE` | Technical analysis (MA20, MA50, RSI) + AI/Rule Based insight |
| `/alert TCS 3500` | Get notified when TCS hits ₹3500 |
| `/alerts | Get a list of all the active alerts set by you |
| `/buy TCS 10 3500` | Track portfolio entry |
| `/sell TCS 5` | Partial or full sell |
| `/portfolio` | View holdings with total invested value |

The bot runs 24/7 with a background heartbeat that monitors price alerts every 2 minutes.

---

## Architecture

```
     Telegram User
         │
         ▼
┌─────────────────────┐
│  Node.js Bot        │  bot.js — Telegram polling, SQLite alerts & portfolio
│  (OpenClaw Channel) │
└────────┬────────────┘
         │ HTTP (axios)
         ▼
┌─────────────────────┐
│  Python FastAPI     │  api/ — Alpha Vantage, yfinance data, technical indicators
│  localhost:8000     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Claude Haiku       │  AI-powered plain-English explanations
│  (claude-haiku-4-5) │
|                     |
|   Local Ollma       |
|                     |
|   Rule Based        |
└─────────────────────┘
```

**OpenClaw files:**
- `SOUL.md` — Agent personality & behavioral boundaries
- `HEARTBEAT.md` — Background daemon task configuration
- `Skill.md` — Skill definitions for each capability

---

## Setup (Windows)

### Prerequisites
- Node.js ≥ 22 — [nodejs.org](https://nodejs.org)
- Python ≥ 3.11 — [python.org](https://python.org)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- (Optional) An Anthropic API key for AI explanations — [console.anthropic.com](https://console.anthropic.com)

### 1. Clone the repo

```powershell
git clone https://github.com/maurya-doshi/Samsung-PRISM-Hackathon.git
cd Samsung-PRISM-Hackathon
```

### 2. Set up the Python API

```powershell
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set up the Node.js bot

```powershell
cd backend
npm install
cd ..
```

### 4. Configure environment variables

Create `backend/.env`:

```env
TOKEN=your_telegram_bot_api_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
```

---

## Running the Project

You need **two terminals** running simultaneously.

### Terminal 1 — Python FastAPI backend

```powershell
# From project root, with venv activated
venv\Scripts\activate
uvicorn api.main:app --reload --port 8000
```

Verify it's running: open http://localhost:8000/health in your browser.

### Terminal 2 — Telegram bot

```powershell
cd backend
node bot.js
```

Open Telegram, find your bot, and send `/start`.

---

## Usage Examples

```
/analyze RELIANCE
/analyze TCS.NS
/alert INFY 1800
/alerts
/cancelalert 1
/buy WIPRO 20 450
/sell WIPRO 10
/portfolio
```

---

## Project Structure

```
    Samsung-PRISM-Hackathon/
    ├── api
    │   ├── analysis.py
    │   ├── explain.py
    │   ├── __init__.py
    │   └── main.py
    ├── backend
    │   ├── bot.js
    │   ├── package.json
    │   └── package-lock.json
    ├── HEARTBEAT.md
    ├── LICENSE
    ├── package-lock.json
    ├── README.md
    ├── requirements.txt
    ├── Skill.md
    └── SOUL.md

    3 directories, 14 files
```

---

## Documentation

A directory that contains the complete documentation in the format requested by the organizers.

    1. Project Video Demo.
    2. Photos of the output/conversation with the bot using the telegram interface.
    3. Database and debug logs.

---

## AI Disclosure

The following AI models were used during the course of the development of this software:
1. Claude Sonnet 4.6
2. Claude Haiku 4.5

They were used for the following purposes:
1. Code generation.
2. Information retrieval.
