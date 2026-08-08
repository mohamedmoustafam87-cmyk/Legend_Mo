from config import MIN_SCORE_THRESHOLD
from risk import calculate_risk_management
from indicators import analyze_candlesticks


def evaluate_stock_strategy(df, ticker_symbol):

    try:
        if df is None or len(df) < 220:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        required_columns = [
            "Close",
            "MA_200",
            "EMA_20",
            "EMA_50",
            "RSI_14",
            "ADX",
            "MACD",
            "MACD_signal",
            "ATR",
            "Volume",
            "Vol_SMA20",
            "Resistance_20",
            "Support_20"
        ]

        for column in required_columns:
            if column not in df.columns:
                return None

            if (
                latest[column] != latest[column]
                or prev[column] != prev[column]
            ):
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

        if (
            close_price <= 0
            or atr <= 0
            or ema20 <= 0
            or ema50 <= 0
            or ma200 <= 0
        ):
            return None

        distance_from_ema = (
            (close_price - ema20)
            / ema20
        ) * 100

        if distance_from_ema > 5:
            return None

        score = 0
        reasons = []

        # Long term trend
        if close_price > ma200:
            score += 15
            reasons.append(
                "✅ السعر أعلى من متوسط 200 يوم"
            )

        # Short/medium trend
        if ema20 > ema50:
            score += 15
            reasons.append(
                "📈 EMA20 أعلى من EMA50"
            )

        # ADX
        if adx > 25 and adx > prev_adx:
            score += 10
            reasons.append(
                f"💪 اتجاه صاعد قوي (ADX: {adx:.1f})"
            )

        # RSI
        if 55 <= rsi <= 65:
            score += 15
            reasons.append(
                f"🔥 RSI في منطقة زخم جيدة ({rsi:.1f})"
            )
        elif 50 <= rsi < 55:
            score += 10
            reasons.append(
                f"⚠️ RSI مقبول ({rsi:.1f})"
            )

        # MACD
        bullish_macd_cross = (
            prev_macd <= prev_signal
            and macd > macd_signal
        )

        macd_positive = (
            macd > macd_signal
            and macd > 0
        )

        if bullish_macd_cross:
            score += 20
            reasons.append(
                "🚀 MACD Bullish Cross"
            )
        elif macd_positive:
            score += 10
            reasons.append(
                "📈 MACD إيجابي"
            )

        # Breakout
        breakout = close_price > resistance

        if breakout:
            score += 15
            reasons.append(
                "🎯 اختراق مقاومة الـ20 جلسة"
            )

        # Volume
        volume_ratio = (
            volume / vol_sma20
            if vol_sma20 > 0
            else 0
        )

        if volume_ratio >= 1.5:
            score += 10
            reasons.append(
                f"💥 حجم تداول قوي ({volume_ratio:.1f}x المتوسط)"
            )

        # Candlestick confirmation
        candle_reasons = analyze_candlesticks(df)

        if candle_reasons:
            score += min(
                len(candle_reasons) * 5,
                5
            )
            reasons.extend(candle_reasons)

        score = min(score, 100)

        if score < MIN_SCORE_THRESHOLD:
            return None

        # Risk Management
        risk = calculate_risk_management(
            close_price,
            atr
        )

        if risk is None:
            return None

        stop_loss = float(
            risk["stop_loss"]
        )

        if stop_loss >= close_price:
            return None

        if score >= 90:
            recommendation = "🔥 شراء قوي جداً"
        elif score >= 85:
            recommendation = "🟢 فرصة شراء قوية"
        else:
            recommendation = "🟡 فرصة شراء جيدة"

        return {
            "ticker": ticker_symbol.replace(".CA", ""),
            "price": round(close_price, 2),
            "score": score,
            "rec": recommendation,
            "atr": round(atr, 2),
            "stop_loss": risk["stop_loss"],
            "shares": risk["shares"],
            "position_value": risk["position_value"],
            "actual_risk": risk["actual_risk"],
            "risk_per_share": risk["risk_per_share"],
            "tp1": risk["tp1"],
            "tp2": risk["tp2"],
            "rr1": risk["rr1"],
            "rr2": risk["rr2"],
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "volume_ratio": round(volume_ratio, 2),
            "reasons": reasons
        }

    except (
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        ZeroDivisionError
    ):
        return None
