import sys, os
import pandas as pd
import requests
from config import SHARIA_EGX_STOCKS
from indicators import calculate_all_indicators
from strategy import evaluate_stock_strategy
from risk import calculate_risk_management
from report import send_scanner_report

def fetch_stock_data(ticker):
    """
    دالة مخصصة لجلب بيانات السعر التاريخية واللحظية للأسهم المصرية 
    بدون الاعتماد على yfinance لتفادي التأخير.
    """
    try:
        # استخدام مصدر بديل أو جلب البيانات عبر API مباشر للبورصة/التواريخ
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        result = data['chart']['result'][0]
        timestamp = result['timestamp']
        quote = result['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'Open': quote['open'],
            'High': quote['high'],
            'Low': quote['low'],
            'Close': quote['close'],
            'Volume': quote['volume']
        }, index=pd.to_datetime(timestamp, unit='s'))
        
        df.dropna(inplace=True)
        return df
    except Exception as e:
        return None

def run_market_scanner():
    print("🔍 جاري بدء فحص السوق المصري للأسهم النقية بمصدر بيانات مباشر...")
    opportunities = []

    for stock in SHARIA_EGX_STOCKS:
        try:
            df = fetch_stock_data(stock)

            if df is None or df.empty or len(df) < 200:
                continue

            df_indicators = calculate_all_indicators(df, stock)
            if df_indicators is None:
                continue

            strategy_result = evaluate_stock_strategy(df_indicators, stock)
            if strategy_result is None:
                continue

            risk_result = calculate_risk_management(strategy_result['price'], strategy_result['atr'])
            if risk_result is None:
                continue

            complete_trade_opportunity = {
                'ticker': strategy_result['ticker'],
                'price': strategy_result['price'],
                'score': strategy_result['score'],
                'rec': strategy_result['rec'],
                'prob': strategy_result['prob'],
                'shares': risk_result['shares'],
                'stop_loss': risk_result['stop_loss'],
                'tp1': risk_result['tp1'],
                'tp2': risk_result['tp2'],
                'reasons': strategy_result['reasons']
            }

            opportunities.append(complete_trade_opportunity)

        except Exception as e:
            continue

    opportunities = sorted(opportunities, key=lambda x: x['score'], reverse=True)
    send_scanner_report(opportunities)
    print("✨ تم الانتهاء من عملية الفحص وإرسال التقرير بنجاح!")

if __name__ == "__main__":
    run_market_scanner()
