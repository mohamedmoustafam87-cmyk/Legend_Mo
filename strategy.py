import pandas as pd

def evaluate_stock_strategy(df, ticker_symbol):
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close_price = float(latest['Close'])
        ma200 = float(latest['MA_200'])
        ema20 = float(latest['EMA_20'])
        ema50 = float(latest['EMA_50'])
        rsi = float(latest['RSI_14'])
        adx = float(latest['ADX'])
        prev_adx = float(prev['ADX'])
        macd = float(latest['MACD'])
        macd_signal = float(latest['MACD_signal'])
        prev_macd = float(prev['MACD'])
        prev_signal = float(prev['MACD_signal'])
        atr = float(latest['ATR'])
        volume = float(latest['Volume'])
        vol_sma20 = float(latest['Vol_SMA20'])
        resistance = float(df['Resistance_20'].iloc[-2])

        distance_from_ema = (close_price - ema20) / ema20 * 100
        if distance_from_ema > 5:
            return None

        score = 0
        reasons = []

        if close_price > ma200:
            score += 15
            reasons.append("✅ السعر أعلى من متوسط 200 يوم")
        if ema20 > ema50:
            score += 15
            reasons.append("✅ تقاطع إيجابي (EMA20 > EMA50)")
        if adx > 25 and adx > prev_adx:
            score += 10
            reasons.append(f"💪 ترند قوي وصاعد (ADX: {round(adx, 1)})")

        if 55 <= rsi <= 65:
            score += 15
            reasons.append(f"🔥 RSI في منطقة العزم المثالية ({round(rsi, 1)})")
        elif 50 <= rsi < 55:
            score += 10
            reasons.append(f"⚠️ RSI في مستويات مقبولة ({round(rsi, 1)})")

        if (prev_macd <= prev_signal) and (macd > macd_signal):
            score += 20
            reasons.append("🚀 إشارة تقاطع إيجابي في MACD")

        if close_price > resistance:
            score += 15
            reasons.append("🎯 اخترق مستوى مقاومة هام بنجاح")

        if volume > (vol_sma20 * 1.5):
            score += 10
            reasons.append("💥 حجم تداول استثنائي (> 1.5x المتوسط)")

        if score < 75:
            return None

        recommendation = "شراء قوي جداً 🔥" if score >= 85 else "فرصة شراء جيدة ✅"
        probability = min(round(score * 0.95), 94)

        return {
            'ticker': ticker_symbol.replace('.CA', ''),
            'price': round(close_price, 2),
            'score': score,
            'rec': recommendation,
            'prob': probability,
            'atr': atr,
            'reasons': reasons
        }

    except Exception as e:
        return None
