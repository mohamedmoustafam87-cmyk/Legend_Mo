from config import MIN_SCORE_THRESHOLD
from risk import calculate_risk_management
from indicators import analyze_candlesticks


def evaluate_stock_strategy(df, ticker_symbol):

    try:

        # ==========================================================
        # Basic Validation
        # ==========================================================

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

        # ==========================================================
        # Current Values
        # ==========================================================

        close_price = float(latest["Close"])

        ma200 = float(latest["MA_200"])

        ema20 = float(latest["EMA_20"])

        ema50 = float(latest["EMA_50"])

        rsi = float(latest["RSI_14"])

        adx = float(latest["ADX"])

        prev_adx = float(prev["ADX"])

        macd = float(latest["MACD"])

        macd_signal = float(
            latest["MACD_signal"]
        )

        prev_macd = float(prev["MACD"])

        prev_signal = float(
            prev["MACD_signal"]
        )

        atr = float(latest["ATR"])

        volume = float(latest["Volume"])

        vol_sma20 = float(
            latest["Vol_SMA20"]
        )

        resistance = float(
            latest["Resistance_20"]
        )

        support = float(
            latest["Support_20"]
        )

        # ==========================================================
        # Validation
        # ==========================================================

        if (
            close_price <= 0
            or ma200 <= 0
            or ema20 <= 0
            or ema50 <= 0
            or atr <= 0
            or resistance <= 0
            or support <= 0
        ):
            return None

        # ==========================================================
        # EMA50 Slope
        # ==========================================================

        if len(df) >= 11:

            ema50_10_days_ago = float(
                df["EMA_50"].iloc[-11]
            )

            if ema50_10_days_ago > 0:

                ema50_slope = (
                    (ema50 - ema50_10_days_ago)
                    / ema50_10_days_ago
                ) * 100

            else:

                ema50_slope = 0

        else:

            ema50_slope = 0

        # ==========================================================
        # MA200 Slope
        # ==========================================================

        if len(df) >= 21:

            ma200_20_days_ago = float(
                df["MA_200"].iloc[-21]
            )

            if ma200_20_days_ago > 0:

                ma200_slope = (
                    (ma200 - ma200_20_days_ago)
                    / ma200_20_days_ago
                ) * 100

            else:

                ma200_slope = 0

        else:

            ma200_slope = 0

        # ==========================================================
        # EMA20 Slope
        # ==========================================================

        if len(df) >= 6:

            ema20_5_days_ago = float(
                df["EMA_20"].iloc[-6]
            )

            if ema20_5_days_ago > 0:

                ema20_slope = (
                    (ema20 - ema20_5_days_ago)
                    / ema20_5_days_ago
                ) * 100

            else:

                ema20_slope = 0

        else:

            ema20_slope = 0

        # ==========================================================
        # MACD Conditions
        # ==========================================================

        bullish_macd_cross = (
            prev_macd <= prev_signal
            and macd > macd_signal
        )

        macd_positive = (
            macd > macd_signal
            and macd > 0
        )

        # ==========================================================
        # Volume Ratio
        # ==========================================================

        volume_ratio = (
            volume / vol_sma20
            if vol_sma20 > 0
            else 0
        )

        # ==========================================================
        # Breakout
        # ==========================================================

        breakout = (
            close_price > resistance
        )

        # ==========================================================
        # Distance From EMA20
        # ==========================================================

        distance_from_ema = (
            (close_price - ema20)
            / ema20
        ) * 100

        # ==========================================================
        # Candlestick Confirmation
        # ==========================================================

        candle_reasons = analyze_candlesticks(
            df
        )

        # ==========================================================
        # Overall Current Market Score
        # ==========================================================

        score = 0

        reasons = []

        if close_price > ma200:

            score += 10

            reasons.append(
                "✅ السعر أعلى من متوسط 200 يوم"
            )

        if ma200_slope > 0:

            score += 5

            reasons.append(
                f"📈 MA200 صاعد ({ma200_slope:+.1f}%)"
            )

        if ema20 > ema50:

            score += 10

            reasons.append(
                "📈 EMA20 أعلى من EMA50"
            )

        if ema50_slope > 0:

            score += 5

            reasons.append(
                f"📈 EMA50 صاعد ({ema50_slope:+.1f}%)"
            )

        if (
            adx > 25
            and adx > prev_adx
        ):

            score += 10

            reasons.append(
                f"💪 اتجاه قوي ومتزايد (ADX: {adx:.1f})"
            )

        elif adx > 20:

            score += 5

            reasons.append(
                f"📊 قوة اتجاه مقبولة (ADX: {adx:.1f})"
            )

        if 50 <= rsi <= 65:

            score += 10

            reasons.append(
                f"🔥 RSI مناسب للزخم ({rsi:.1f})"
            )

        elif 45 <= rsi < 50:

            score += 5

            reasons.append(
                f"⚠️ RSI ضعيف نسبيًا ({rsi:.1f})"
            )

        elif rsi > 70:

            reasons.append(
                f"⚠️ RSI مرتفع جدًا ({rsi:.1f})"
            )

        elif rsi < 40:

            reasons.append(
                f"⚠️ RSI منخفض ({rsi:.1f})"
            )

        if bullish_macd_cross:

            score += 10

            reasons.append(
                "🚀 MACD Bullish Cross"
            )

        elif macd_positive:

            score += 5

            reasons.append(
                "📈 MACD إيجابي"
            )

        if volume_ratio >= 1.5:

            score += 10

            reasons.append(
                f"💥 حجم تداول قوي ({volume_ratio:.1f}x المتوسط)"
            )

        elif volume_ratio >= 1.0:

            score += 5

            reasons.append(
                f"📊 حجم تداول جيد ({volume_ratio:.1f}x المتوسط)"
            )

        if breakout:

            score += 5

            reasons.append(
                "🎯 السعر اخترق مقاومة الـ20 جلسة"
            )

        if candle_reasons:

            score += min(
                len(candle_reasons) * 5,
                5
            )

            reasons.extend(
                candle_reasons
            )

        score = min(
            score,
            100
        )

        # ==========================================================
        # 1 MONTH FORECAST SCORE
        # ==========================================================

        forecast_1m_score = 0

        if ema20 > ema50:
            forecast_1m_score += 15

        if ema20_slope > 0:
            forecast_1m_score += 10

        if ema50_slope > 0:
            forecast_1m_score += 10

        if close_price > ma200:
            forecast_1m_score += 10

        if adx > 25 and adx > prev_adx:
            forecast_1m_score += 15

        elif adx > 20:
            forecast_1m_score += 8

        if 50 <= rsi <= 65:
            forecast_1m_score += 10

        elif 45 <= rsi < 50:
            forecast_1m_score += 5

        if bullish_macd_cross:
            forecast_1m_score += 15

        elif macd_positive:
            forecast_1m_score += 8

        if volume_ratio >= 1.5:
            forecast_1m_score += 10

        elif volume_ratio >= 1.0:
            forecast_1m_score += 5

        # ==========================================================
        # 2 MONTH FORECAST SCORE
        # ==========================================================

        forecast_2m_score = 0

        if close_price > ma200:
            forecast_2m_score += 15

        if ma200_slope > 0:
            forecast_2m_score += 15

        if ema20 > ema50:
            forecast_2m_score += 10

        if ema50_slope > 0:
            forecast_2m_score += 15

        if adx > 25 and adx > prev_adx:
            forecast_2m_score += 15

        elif adx > 20:
            forecast_2m_score += 8

        if 50 <= rsi <= 65:
            forecast_2m_score += 10

        elif 45 <= rsi < 50:
            forecast_2m_score += 5

        if macd_positive:
            forecast_2m_score += 10

        elif bullish_macd_cross:
            forecast_2m_score += 8

        if volume_ratio >= 1.5:
            forecast_2m_score += 10

        elif volume_ratio >= 1.0:
            forecast_2m_score += 5

        forecast_1m_score = min(
            forecast_1m_score,
            100
        )

        forecast_2m_score = min(
            forecast_2m_score,
            100
        )

        if forecast_1m_score >= 85:
            forecast_1m_status = "🔥 ترشيح قوي للشهر القادم"
        elif forecast_1m_score >= 75:
            forecast_1m_status = "🟢 ترشيح جيد للشهر القادم"
        elif forecast_1m_score >= 65:
            forecast_1m_status = "🟡 مراقبة للشهر القادم"
        else:
            forecast_1m_status = "🔴 ترشيح ضعيف للشهر القادم"

        if forecast_2m_score >= 85:
            forecast_2m_status = "🔥 ترشيح قوي للشهرين القادمين"
        elif forecast_2m_score >= 75:
            forecast_2m_status = "🟢 ترشيح جيد للشهرين القادمين"
        elif forecast_2m_score >= 65:
            forecast_2m_status = "🟡 مراقبة للشهرين القادمين"
        else:
            forecast_2m_status = "🔴 ترشيح ضعيف للشهرين القادمين"

        if (
            forecast_1m_score >= 75
            and forecast_2m_score >= 75
        ):
            trend_status = "🟢 اتجاه حالي داعم للشهر والشهرين القادمين"
        elif forecast_1m_score >= 75:
            trend_status = "🟢 Setup أقوى للشهر القادم"
        elif forecast_2m_score >= 75:
            trend_status = "🟢 Setup أقوى للشهرين القادمين"
        elif (
            forecast_1m_score >= 65
            and forecast_2m_score >= 65
        ):
            trend_status = "🟡 Setup متوسط ويحتاج متابعة"
        else:
            trend_status = "🔴 Setup المستقبلي ضعيف"

        # ==========================================================
        # Entry Analysis (Adjusted for Momentum Stocks)
        # ==========================================================

        # السماح للأسهم الصاروخية بتجاوز النسبة التقليدية طالما التوقعات المستقبلية قوية
        overextended = (
            distance_from_ema > 25
            and forecast_1m_score < 75
        )

        too_far_below_ema = (
            distance_from_ema < -8
        )

        entry_candidates = [
            ema20,
            ema50,
            support
        ]

        entry_candidates = [
            x
            for x in entry_candidates
            if x > 0
        ]

        if entry_candidates:
            ideal_entry = min(entry_candidates)
            entry_high = max(entry_candidates)
        else:
            ideal_entry = close_price
            entry_high = close_price

        if overextended:
            entry_status = "🟡 WAIT - السعر ممتد فوق EMA20"
        elif too_far_below_ema:
            entry_status = "🟡 WAIT - السعر أسفل مناطق الدعم"
        elif breakout or forecast_1m_score >= 75:
            entry_status = "🟢 BUY - Strong Momentum / Breakout"
        elif (
            close_price >= ideal_entry
            and close_price <= entry_high * 1.02
        ):
            entry_status = "🟢 BUY ZONE"
        else:
            entry_status = "🟡 WATCH - انتظار نقطة دخول أفضل"

        # ==========================================================
        # Risk Management
        # ==========================================================

        risk = calculate_risk_management(
            close_price,
            atr,
            support
        )

        if risk is None:
            return None

        stop_loss = float(
            risk["stop_loss"]
        )

        if stop_loss >= close_price:
            return None

        # ==========================================================
        # Final Recommendation
        # ==========================================================

        if score < MIN_SCORE_THRESHOLD:
            recommendation = "🔴 لا توجد إشارة شراء كافية"
        elif (
            score >= 90
            and forecast_1m_score >= 75
            and forecast_2m_score >= 75
            and entry_status.startswith("🟢")
        ):
            recommendation = "🔥 شراء قوي جداً"
        elif (
            score >= 85
            and (
                forecast_1m_score >= 75
                or forecast_2m_score >= 75
            )
            and entry_status.startswith("🟢")
        ):
            recommendation = "🟢 فرصة شراء قوية"
        elif (
            forecast_1m_score >= 75
            and forecast_2m_score >= 75
            and entry_status.startswith("🟢")
        ):
            recommendation = "🟡 فرصة شراء جيدة"
        elif (
            forecast_1m_score >= 75
            or forecast_2m_score >= 75
        ):
            recommendation = "🟡 WATCH - التوقع إيجابي وانتظر دخول أفضل"
        else:
            recommendation = "🟡 WATCH"

        # ==========================================================
        # Return Result
        # ==========================================================

        return {
            "ticker": ticker_symbol.replace(".CA", ""),
            "price": round(close_price, 2),
            "score": score,
            "rec": recommendation,
            "trend_status": trend_status,
            "forecast_1m_score": forecast_1m_score,
            "forecast_2m_score": forecast_2m_score,
            "forecast_1m_status": forecast_1m_status,
            "forecast_2m_status": forecast_2m_status,
            "entry_status": entry_status,
            "distance_from_ema": round(distance_from_ema, 2),
            "ideal_entry": round(ideal_entry, 2),
            "entry_high": round(entry_high, 2),
            "ma200_slope": round(ma200_slope, 2),
            "ema50_slope": round(ema50_slope, 2),
            "atr": round(atr, 2),
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "volume_ratio": round(volume_ratio, 2),
            "stop_loss": risk["stop_loss"],
            "stop_loss_pct": risk.get("stop_loss_pct", 0),
            "shares": risk["shares"],
            "position_value": risk["position_value"],
            "actual_risk": risk["actual_risk"],
            "risk_per_share": risk["risk_per_share"],
            "tp1": risk["tp1"],
            "tp2": risk["tp2"],
            "rr1": risk["rr1"],
            "rr2": risk["rr2"],
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
