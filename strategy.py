from config import MIN_SCORE_THRESHOLD, MAX_ALLOWABLE_RSI
from risk import calculate_risk_management
from indicators import analyze_candlesticks


def evaluate_stock_strategy(df, ticker_symbol):

    try:
        if df is None or len(df) < 220:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        required_columns = [
            "Close", "MA_200", "EMA_20", "EMA_50", "RSI_14",
            "ADX", "MACD", "MACD_signal", "ATR", "Volume",
            "Vol_SMA20", "Resistance_20", "Support_20"
        ]

        for column in required_columns:
            if column not in df.columns:
                return None
            if latest[column] != latest[column] or prev[column] != prev[column]:
                return None

        close_price = float(latest["Close"])
        ma200 = float(latest["MA_200"])
        ema20 = float(latest["EMA_20"])
        ema50 = float(latest["EMA_50"])
        rsi = float(latest["RSI_14"])
        adx = float(latest["ADX"])
        prev_adx = float(prev["ADX"])
        macd = float(latest["MACD"])
        macd_signal = float(latest["MACD_signal"])
        prev_macd = float(prev["MACD"])
        prev_signal = float(prev["MACD_signal"])
        atr = float(latest["ATR"])
        volume = float(latest["Volume"])
        vol_sma20 = float(latest["Vol_SMA20"])
        resistance = float(latest["Resistance_20"])
        support = float(latest["Support_20"])

        if close_price <= 0 or ma200 <= 0 or ema20 <= 0 or ema50 <= 0 or atr <= 0 or resistance <= 0 or support <= 0:
            return None

        if rsi > MAX_ALLOWABLE_RSI:
            return None

        ema50_slope = 0
        if len(df) >= 11:
            ema50_10_days_ago = float(df["EMA_50"].iloc[-11])
            if ema50_10_days_ago > 0:
                ema50_slope = ((ema50 - ema50_10_days_ago) / ema50_10_days_ago) * 100

        ma200_slope = 0
        if len(df) >= 21:
            ma200_20_days_ago = float(df["MA_200"].iloc[-21])
            if ma200_20_days_ago > 0:
                ma200_slope = ((ma200 - ma200_20_days_ago) / ma200_20_days_ago) * 100

        ema20_slope = 0
        if len(df) >= 6:
            ema20_5_days_ago = float(df["EMA_20"].iloc[-6])
            if ema20_5_days_ago > 0:
                ema20_slope = ((ema20 - ema20_5_days_ago) / ema20_5_days_ago) * 100

        bullish_macd_cross = (prev_macd <= prev_signal and macd > macd_signal)
        macd_positive = (macd > macd_signal and macd > 0)

        volume_ratio = (volume / vol_sma20 if vol_sma20 > 0 else 0)
        breakout = (close_price > resistance)
        distance_from_ema = ((close_price - ema20) / ema20) * 100

        candle_reasons = analyze_candlesticks(df)

        score = 0
        reasons = []

        if close_price > ma200:
            score += 10
            reasons.append("✅ السعر أعلى من متوسط 200 يوم")

        if ma200_slope > 0:
            score += 5
            reasons.append(f"📈 MA200 صاعد ({ma200_slope:+.1f}%)")

        if ema20 > ema50:
            score += 10
            reasons.append("📈 EMA20 أعلى من EMA50")

        if ema50_slope > 0:
            score += 5
            reasons.append(f"📈 EMA50 صاعد ({ema50_slope:+.1f}%)")

        if adx > 25 and adx > prev_adx:
            score += 10
            reasons.append(f"💪 اتجاه قوي ومتزايد (ADX: {adx:.1f})")
        elif adx > 20:
            score += 5
            reasons.append(f"📊 قوة اتجاه مقبولة (ADX: {adx:.1f})")

        if 50 <= rsi <= 65:
            score += 10
            reasons.append(f"🔥 RSI مناسب للزخم ({rsi:.1f})")
        elif 45 <= rsi < 50:
            score += 5
            reasons.append(f"⚠️ RSI ضعيف نسبيًا ({rsi:.1f})")
        elif rsi < 40:
            score += 5
            reasons.append(f"⚠️ RSI في مناطق التجميع ({rsi:.1f})")

        if bullish_macd_cross:
            score += 10
            reasons.append("🚀 MACD Bullish Cross")
        elif macd_positive:
            score += 5
            reasons.append("📈 MACD إيجابي")

        if volume_ratio >= 1.5:
            score += 10
            reasons.append(f"💥 حجم تداول قوي ({volume_ratio:.1f}x المتوسط)")
        elif volume_ratio >= 1.0:
            score += 5
            reasons.append(f"📊 حجم تداول جيد ({volume_ratio:.1f}x المتوسط)")

        if breakout:
            score += 5
            reasons.append("🎯 السعر اخترق مقاومة الـ20 جلسة")

        if candle_reasons:
            score += min(len(candle_reasons) * 5, 5)
            reasons.extend(candle_reasons)

        score = min(score, 100)

        forecast_1m_score = 0
        if ema20 > ema50: forecast_1m_score += 15
        if ema20_slope > 0: forecast_1m_score += 10
        if ema50_slope > 0: forecast_1m_score += 10
        if close_price > ma200: forecast_1m_score += 10
        if adx > 25 and adx > prev_adx: forecast_1m_score += 15
        elif adx > 20: forecast_1m_score += 8
        if 50 <= rsi <= 65: forecast_1m_score += 10
        elif 45 <= rsi < 50: forecast_1m_score += 5
        if bullish_macd_cross: forecast_1m_score += 15
        elif macd_positive: forecast_1m_score += 8
        if volume_ratio >= 1.5: forecast_1m_score += 10
        elif volume_ratio >= 1.0: forecast_1m_score += 5

        forecast_2m_score = 0
        if close_price > ma200: forecast_2m_score += 15
        if ma200_slope > 0: forecast_2m_score += 15
        if ema20 > ema50: forecast_2m_score += 10
        if ema50_slope > 0: forecast_2m_score += 15
        if adx > 25 and adx > prev_adx: forecast_2m_score += 15
        elif adx > 20: forecast_2m_score += 8
        if 50 <= rsi <= 65: forecast_2m_score += 10
        elif 45 <= rsi < 50: forecast_2m_score += 5
        if macd_positive: forecast_2m_score += 10
        elif bullish_macd_cross: forecast_2m_score += 8
        if volume_ratio >= 1.5: forecast_2m_score += 10
        elif volume_ratio >= 1.0: forecast_2m_score += 5

        forecast_1m_score = min(forecast_1m_score, 100)
        forecast_2m_score = min(forecast_2m_score, 100)

        if forecast_1m_score >= 85: forecast_1m_status = "🔥 ترشيح قوي للشهر القادم"
        elif forecast_1m_score >= 70: forecast_1m_status = "🟢 ترشيح جيد للشهر القادم"
        elif forecast_1m_score >= 55: forecast_1m_status = "🟡 مراقبة للشهر القادم"
        else: forecast_1m_status = "🔴 ترشيح ضعيف للشهر القادم"

        if forecast_2m_score >= 85: forecast_2m_status = "🔥 ترشيح قوي للشهرين القادمين"
        elif forecast_2m_score >= 70: forecast_2m_status = "🟢 ترشيح جيد للشهرين القادمين"
        elif forecast_2m_score >= 55: forecast_2m_status = "🟡 مراقبة للشهرين القادمين"
        else: forecast_2m_status = "🔴 ترشيح ضعيف للشهرين القادمين"

        if forecast_1m_score >= 65 and forecast_2m_score >= 65:
            trend_status = "🟢 اتجاه حالي داعم للشهر والشهرين القادمين"
        elif forecast_1m_score >= 65:
            trend_status = "🟢 Setup أقوى للشهر القادم"
        elif forecast_2m_score >= 65:
            trend_status = "🟢 Setup أقوى للشهرين القادمين"
        else:
            trend_status = "🟡 Setup متوسط ويحتاج متابعة"

        max_allowed_drop = close_price * 0.985
        realistic_support = max(support, max_allowed_drop)

        ideal_entry = round(realistic_support, 2)
        entry_high = round(close_price, 2)

        overextended = (distance_from_ema > 25)
        too_far_below_ema = (distance_from_ema < -10)

        if overextended:
            entry_status = "🟡 WAIT - السعر ممتد فوق EMA20"
        elif too_far_below_ema:
            entry_status = "🟡 WAIT - السعر بعيد عن المتوسطات"
        else:
            entry_status = "🟢 BUY - سعر الدخول قريب ومرتبط بالزخم الحالي"

        risk_data = calculate_risk_management(close_price, atr, support)
        if not risk_data:
            return None

        if score >= 85:
            recommendation = "🔥 BUY STRONG"
        elif score >= 70:
            recommendation = "🟢 BUY"
        else:
            recommendation = "🟡 WATCH"

        # خطة الخروج
        if rsi >= 75 or close_price >= resistance * 0.98:
            exit_strategy = "💰 تشبع شرائي أو اقتراب مقاومة - يُنصح بجني أرباح جزئي"
        elif close_price < risk_data["stop_loss"]:
            exit_strategy = "🔴 تم كسر نقطة وقف الخسارة - خروج فوري للحفاظ على رأس المال"
        else:
            exit_strategy = "🟢 الوضع الفني آمن - استمر في الاحتفاظ حتى الأهداف"

        return {
            "ticker": ticker_symbol,
            "symbol": ticker_symbol,
            "price": close_price,
            "score": score,
            "rec": recommendation,
            "reasons": reasons,
            "forecast_1m_score": forecast_1m_score,
            "forecast_1m_status": forecast_1m_status,
            "forecast_2m_score": forecast_2m_score,
            "forecast_2m_status": forecast_2m_status,
            "trend_status": trend_status,
            "entry_status": entry_status,
            "ideal_entry": ideal_entry,
            "entry_high": entry_high,
            "distance_from_ema": distance_from_ema,
            "ma200_slope": ma200_slope,
            "ema50_slope": ema50_slope,
            "volume_ratio": volume_ratio,
            "support": support,
            "resistance": resistance,
            "atr": atr,
            "shares": risk_data.get("shares", 0),
            "stop_loss": risk_data.get("stop_loss", 0),
            "stop_loss_pct": risk_data.get("stop_loss_pct", 0),
            "tp1": risk_data.get("tp1", 0),
            "days_tp1_text": "15-30 يوم",
            "tp2": risk_data.get("tp2", 0),
            "days_tp2_text": "30-60 يوم",
            "position_value": risk_data.get("position_value", 0),
            "actual_risk": risk_data.get("actual_risk", 0),
            "risk_per_share": risk_data.get("risk_per_share", 0),
            "rr1": risk_data.get("rr1", 0),
            "rr2": risk_data.get("rr2", 0),
            "exit_strategy": exit_strategy
        }

    except Exception as e:
        print(f"Error in evaluate_stock_strategy: {e}")
        return None
