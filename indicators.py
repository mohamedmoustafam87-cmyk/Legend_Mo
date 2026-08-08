import pandas as pd

def calculate_indicators(df):
    if df is None or len(df) < 30:
        return None
    
    # حساب المتوسطات المتحركة ببساطة وسرعة
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # حساب مؤشر القوة النسبية RSI يدوياً وبدقة
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

def analyze_stock(df, symbol):
    df = calculate_indicators(df)
    if df is None or df.empty:
        return None
    
    last = df.iloc[-1]
    score = 50
    reasons = []
    
    # تحليل RSI
    if 'RSI' in df.columns and not pd.isna(last['RSI']):
        if last['RSI'] < 40:
            score += 15
            reasons.append(f"RSI إيجابي ومنطقة تجميع ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            score -= 10
            reasons.append(f"RSI مرتفع جداً ({last['RSI']:.1f})")
            
    return {
        'symbol': symbol,
        'price': last['Close'],
        'score': score,
        'reasons': reasons
    }
        return None
