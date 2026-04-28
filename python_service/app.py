from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

@app.get('/')
async def index():
    tm = datetime.now()
    return {
        'status': 'success',
        'time': tm.strftime("%Y-%m-%d %H:%M:%S"),
    }

@app.post('/track')
async def track(ticker: str, units: float, cap: float):
    return {
        'ticker': ticker,
        'cap': cap,
        'units purchased': units,
        'current value': cur_val,
    }

@app.put('/update')
async def update(ticker: str, units: float, cap: float):
    return u_info

@app.get('/info')
async def info(ticker: str):
    if ticker not in tickers:
        raise HTTPException(status_code = 400, detail = 'Not in your portfolio')
    return s_info
