import requests
import pandas as pd
from config import SHARIA_EGX_STOCKS, MIN_SCORE_THRESHOLD
from indicators import analyze_stock

def get_stock_data(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'Open': quote['open'],
            'High': quote['high'],
            'Low': quote['low'],
            'Close': quote['close'],
            'Volume': quote['volume']
        }, index=pd.to_datetime(timestamps, unit='s'))
        
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def scan_market():
    opportunities = []
    for symbol in SHARIA_EGX_STOCKS:
        print(f"Scanning {symbol}...")
        df = get_stock_data(symbol)
        if df is not None and not df.empty:
            analysis = analyze_stock(df, symbol)
            if analysis and analysis['score'] >= MIN_SCORE_THRESHOLD:
                opportunities.append(analysis)
    return opportunities
