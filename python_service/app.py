from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Mock data
tickers = ['AAPL', 'GOOGL', 'MSFT']
mock_portfolio = {
    'AAPL': {'units': 10, 'cap': 1500, 'current_value': 1750.50},
    'GOOGL': {'units': 5, 'cap': 1000, 'current_value': 1200.25},
    'MSFT': {'units': 8, 'cap': 2000, 'current_value': 2100.75}
}

@app.get('/')
async def index():
    tm = datetime.now()
    return {
        'status': 'success',
        'time': tm.strftime("%Y-%m-%d %H:%M:%S"),
    }

@app.post('/track')
async def track(ticker: str, units: float, cap: float):
    cur_val = units * 150.0 # Mock current value calculation
    return {
        'ticker': ticker,
        'cap': cap,
        'units purchased': units,
        'current value': cur_val,
    }

@app.put('/update')
async def update(ticker: str, units: float, cap: float):
    u_info = {
        'ticker': ticker,
        'updated_units': units,
        'updated_cap': cap,
        'status': 'Successfully updated'
    }
    return u_info

@app.get('/info')
async def info(ticker: str):
    if ticker not in tickers:
        raise HTTPException(status_code = 400, detail = 'Not in your portfolio')
    s_info = mock_portfolio.get(ticker)
    s_info['ticker'] = ticker
    return s_info

@app.get('/analysis')
async def analysis(ticker: str):
    # Mock analysis data
    return {
        'ticker': ticker,
        'price': 150.25,
        'ma20': 148.50,
        'ma50': 145.00,
        'rsi': 65.4,
        'signal': 'BUY'
    }

class AnalysisData(BaseModel):
    ticker: str
    price: float
    ma20: float
    ma50: float
    rsi: float
    signal: str

@app.post('/explain')
async def explain(data: AnalysisData):
    # Mock explanation
    return {
        'explanation': f"The stock {data.ticker} is currently trading at {data.price}. With the RSI at {data.rsi} and the price above both the 20-day and 50-day moving averages, the technical indicators suggest a bullish trend. Hence the {data.signal} signal."
    }
