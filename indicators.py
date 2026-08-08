import pandas as pd

def calculate_indicators(df):
    if df is None or len(df) < 30:
        return None
    
    # المتوسطات المتحركة
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # مؤشر القوة النسبية RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

def analyze_candlesticks(df):
    if df is None or len(df) < 2:
        return []
    
    reasons = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # حساب خصائص الشمعة الأخيرة
    body = abs(last['Close'] - last['Open'])
    total_range = last['High'] - last['Low']
    lower_shadow = min(last['Open'], last['Close']) - last['Low']
    upper_shadow = last['High'] - max(last['Open'], last['Close'])
    
    # 1. فحص شمعة المطرقة (Hammer)
    if total_range > 0 and (lower_shadow >= 2 * body) and (upper_shadow <= body * 0.5):
        if last['Close'] > last['Open']:
            reasons.append("🔨 ظهور شمعة المطرقة الإيجابية (دعم قوي من القاع)")
            
    # 2. فحص الابتلاع الشرائي (Bullish Engulfing)
    prev_body = abs(prev['Close'] - prev['Open'])
    is_prev_red = prev['Close'] < prev['Open']
    is_last_green = last['Close'] > last['Open']
    
    if is_prev_red and is_last_green:
        if last['Close'] >= prev['Open'] and last['Open'] <= prev['Close']:
            reasons.append("🟢 شمعة الابتلاع الشرائي (سيطرة قوية للمشترين)")
            
    return reasons

def analyze_stock(df, symbol):
    df = calculate_indicators(df)
    if df is None or df.empty:
        return None
    
    last = df.iloc[-1]
    score = 50
    reasons = []
    
    # تقييم RSI
    if 'RSI' in df.columns and not pd.isna(last['RSI']):
        if last['RSI'] < 45:
            score += 15
            reasons.append(f"RSI في منطقة تجميع إيجابية ({last['RSI']:.1f})")
        elif last['RSI'] > 70:
            score -= 10
            reasons.append(f"RSI مرتفع جداً ({last['RSI']:.1f})")
            
    # إضافة تحليل الشموع اليابانية
    candle_reasons = analyze_candlesticks(df)
    if candle_reasons:
        score += 20
        reasons.extend(candle_reasons)
        
    return {
        'symbol': symbol,
        'price': last['Close'],
        'score': score,
        'reasons': reasons
    }
