from config import (
    MIN_SCORE_THRESHOLD,
    MAX_ALLOWABLE_RSI,
    MAX_DISTANCE_FROM_EMA20,
)

from risk import calculate_risk_management

from indicators import analyze_candlesticks


# ==========================================================
# Strategy Evaluation
# ==========================================================

def evaluate_stock_strategy(
    df,
    ticker_symbol
):

    try:

        # ======================================================
        # Basic Validation
        # ======================================================

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
            "Support_20",
        ]

        for column in required_columns:

            if column not in df.columns:
                return None

            if (
                latest[column] != latest[column]
                or
                prev[column] != prev[column]
            ):
                return None

        # ======================================================
        # Current Values
        # ======================================================

        close_price = float(
            latest["Close"]
        )

        ma200 = float(
            latest["MA_200"]
        )

        ema20 = float(
            latest["EMA_20"]
        )

        ema50 = float(
            latest["EMA_50"]
        )

        rsi = float(
            latest["RSI_14"]
        )

        adx = float(
            latest["ADX"]
        )

        prev_adx = float(
            prev["ADX"]
        )

        macd = float(
            latest["MACD"]
        )

        macd_signal = float(
            latest["MACD_signal"]
        )

        prev_macd = float(
            prev["MACD"]
        )

        prev_signal = float(
            prev["MACD_signal"]
        )

        atr = float(
            latest["ATR"]
        )

        volume = float(
            latest["Volume"]
        )

        vol_sma20 = float(
            latest["Vol_SMA20"]
        )

        resistance = float(
            latest["Resistance_20"]
        )

        support = float(
            latest["Support_20"]
        )

        # ======================================================
        # Validation
        # ======================================================

        if any(
            value <= 0
            for value in [
                close_price,
                ma200,
                ema20,
                ema50,
                atr,
                resistance,
                support,
            ]
        ):
            return None

        # ======================================================
        # RSI Filter
        # ======================================================

        if rsi > MAX_ALLOWABLE_RSI:
            return None

        # ======================================================
        # EMA50 Slope
        # ======================================================

        ema50_slope = 0

        if len(df) >= 11:

            old_ema50 = float(
                df["EMA_50"].iloc[-11]
            )

            if old_ema50 > 0:

                ema50_slope = (
                    (
                        ema50 -
                        old_ema50
                    )
                    /
                    old_ema50
                ) * 100

        # ======================================================
        # MA200 Slope
        # ======================================================

        ma200_slope = 0

        if len(df) >= 21:

            old_ma200 = float(
                df["MA_200"].iloc[-21]
            )

            if old_ma200 > 0:

                ma200_slope = (
                    (
                        ma200 -
                        old_ma200
                    )
                    /
                    old_ma200
                ) * 100

        # ======================================================
        # EMA20 Slope
        # ======================================================

        ema20_slope = 0

        if len(df) >= 6:

            old_ema20 = float(
                df["EMA_20"].iloc[-6]
            )

            if old_ema20 > 0:

                ema20_slope = (
                    (
                        ema20 -
                        old_ema20
                    )
                    /
                    old_ema20
                ) * 100

        # ======================================================
        # MACD
        # ======================================================

        bullish_macd_cross = (
            prev_macd <= prev_signal
            and
            macd > macd_signal
        )

        macd_positive = (
            macd > macd_signal
            and
            macd > 0
        )

        # ======================================================
        # Volume
        # ======================================================

        volume_ratio = (
            volume / vol_sma20
            if vol_sma20 > 0
            else 0
        )

        # ======================================================
        # Breakout
        # ======================================================

        breakout = (
            close_price >
            resistance
        )

        # ======================================================
        # EMA20 Distance
        # ======================================================

        distance_from_ema = (
            (
                close_price -
                ema20
            )
            /
            ema20
        ) * 100

        # ======================================================
        # Candlesticks
        # ======================================================

        candle_reasons = (
            analyze_candlesticks(df)
        )

        # ======================================================
        # Main Score
        # ======================================================

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
            and
            adx > prev_adx
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

        elif rsi < 40:

            score += 5

            reasons.append(
                f"⚠️ RSI في مناطق التجميع ({rsi:.1f})"
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

        # ======================================================
        # 1 Month Setup Score
        # ======================================================

        forecast_1m_score = 0

        if ema20 > ema50:
            forecast_1m_score += 15

        if ema20_slope > 0:
            forecast_1m_score += 10

        if ema50_slope > 0:
            forecast_1m_score += 10

        if close_price > ma200:
            forecast_1m_score += 10

        if (
            adx > 25
            and
            adx > prev_adx
        ):
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

        forecast_1m_score = min(
            forecast_1m_score,
            100
        )

        # ======================================================
        # 2 Month Setup Score
        # ======================================================

        forecast_2m_score = 0

        if close_price > ma200:
            forecast_2m_score += 15

        if ma200_slope > 0:
            forecast_2m_score += 15

        if ema20 > ema50:
            forecast_2m_score += 10

        if ema50_slope > 0:
            forecast_2m_score += 15

        if (
            adx > 25
            and
            adx > prev_adx
        ):
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

        forecast_2m_score = min(
            forecast_2m_score,
            100
        )

        # ======================================================
        # Status
        # ======================================================

        if forecast_1m_score >= 85:

            forecast_1m_status = (
                "🔥 ترشيح قوي للشهر القادم"
            )

        elif forecast_1m_score >= 70:

            forecast_1m_status = (
                "🟢 ترشيح جيد للشهر القادم"
            )

        elif forecast_1m_score >= 55:

            forecast_1m_status = (
                "🟡 مراقبة للشهر القادم"
            )

        else:

            forecast_1m_status = (
                "🔴 ترشيح ضعيف للشهر القادم"
            )

        if forecast_2m_score >= 85:

            forecast_2m_status = (
                "🔥 ترشيح قوي للشهرين القادمين"
            )

        elif forecast_2m_score >= 70:

            forecast_2m_status = (
                "🟢 ترشيح جيد للشهرين القادمين"
            )

        elif forecast_2m_score >= 55:

            forecast_2m_status = (
                "🟡 مراقبة للشهرين القادمين"
            )

        else:

            forecast_2m_status = (
                "🔴 ترشيح ضعيف للشهرين القادمين"
            )

        if (
            forecast_1m_score >= 65
            and
            forecast_2m_score >= 65
        ):

            trend_status = (
                "🟢 اتجاه حالي داعم للشهر والشهرين القادمين"
            )

        elif forecast_1m_score >= 65:

            trend_status = (
                "🟢 Setup أقوى للشهر القادم"
            )

        elif forecast_2m_score >= 65:

            trend_status = (
                "🟢 Setup أقوى للشهرين القادمين"
            )

        else:

            trend_status = (
                "🟡 Setup متوسط ويحتاج متابعة"
            )

        # ======================================================
        # Entry Analysis
        # ======================================================

        max_allowed_drop = (
            close_price * 0.985
        )

        realistic_support = max(
            support,
            max_allowed_drop
        )

        ideal_entry = round(
            realistic_support,
            2
        )

        entry_high = round(
            close_price,
            2
        )

        # استخدام إعداد config بدل 25%
        overextended = (
            distance_from_ema >
            MAX_DISTANCE_FROM_EMA20
        )

        too_far_below_ema = (
            distance_from_ema < -10
        )

        if overextended:

            entry_status = (
                "🟡 WAIT - السعر ممتد فوق EMA20"
            )

        elif too_far_below_ema:

            entry_status = (
                "🟡 WAIT - السعر بعيد عن المتوسطات"
            )

        else:

            entry_status = (
                "🟢 BUY - سعر الدخول قريب ومرتبط بالزخم الحالي"
            )

        # ======================================================
        # Risk Management
        # ======================================================

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

        # ======================================================
        # Expected Time
        # ======================================================

        distance_tp1 = (
            risk["tp1"] -
            close_price
        )

        distance_tp2 = (
            risk["tp2"] -
            close_price
        )

        daily_speed = (
            atr
            if atr > 0
            else close_price * 0.02
        )

        effective_speed = (
            daily_speed * 1.2
            if adx > 25
            else daily_speed
        )

        sessions_tp1 = max(
            1,
            round(
                distance_tp1 /
                effective_speed
            )
        )

        sessions_tp2 = max(
            1,
            round(
                distance_tp2 /
                effective_speed
            )
        )

        if sessions_tp1 >= 5:

            days_tp1_text = (
                f"تقريباً {sessions_tp1} جلسات "
                f"({max(1, sessions_tp1 // 5)} أسبوع)"
            )

        else:

            days_tp1_text = (
                f"تقريباً {sessions_tp1} جلسات تداول"
            )

        if sessions_tp2 >= 5:

            days_tp2_text = (
                f"تقريباً {sessions_tp2} جلسات "
                f"({max(1, sessions_tp2 // 5)} أسابيع)"
            )

        else:

            days_tp2_text = (
                f"تقريباً {sessions_tp2} جلسات تداول"
            )

        # ======================================================
        # Exit Strategy
        # ======================================================

        exit_signals = []

        # مهم: 80 قبل 75
        if rsi >= 80:

            exit_signals.append(
                "🚨 تشبع شرائي شديد (>80) - راقب جني الأرباح"
            )

        elif rsi >= 75:

            exit_signals.append(
                "⚠️ RSI ممتد (>75) - راقب جني أرباح جزئي"
            )

        if close_price < ema20:

            exit_signals.append(
                "🔴 السعر كسر EMA20 هبوطاً - إشارة حماية"
            )

        if close_price >= resistance * 0.98:

            exit_signals.append(
                "🎯 السعر يقترب من المقاومة الرئيسية"
            )

        if not exit_signals:

            exit_strategy_text = (
                "🟢 الوضع مستقر - متابعة الأهداف TP1 / TP2"
            )

        else:

            exit_strategy_text = (
                " | ".join(exit_signals)
            )

        # ======================================================
        # Recommendation
        # ======================================================

        if score < MIN_SCORE_THRESHOLD:

            return None

        elif (
            score >= 80
            and
            forecast_1m_score >= 70
        ):

            recommendation = (
                "🔥 شراء قوي جداً"
            )

        elif score >= 70:

            recommendation = (
                "🟢 فرصة شراء قوية"
            )

        elif score >= 60:

            recommendation = (
                "🟡 فرصة شراء جيدة"
            )

        else:

            recommendation = (
                "🟡 WATCH"
            )

        # ======================================================
        # Return
        # ======================================================

        return {

            "ticker":
                ticker_symbol.replace(
                    ".CA",
                    ""
                ),

            # السعر التاريخي المستخدم في الاستراتيجية
            "price":
                round(
                    close_price,
                    2
                ),

            "score":
                score,

            "rec":
                recommendation,

            "trend_status":
                trend_status,

            "forecast_1m_score":
                forecast_1m_score,

            "forecast_2m_score":
                forecast_2m_score,

            "forecast_1m_status":
                forecast_1m_status,

            "forecast_2m_status":
                forecast_2m_status,

            "entry_status":
                entry_status,

            "distance_from_ema":
                round(
                    distance_from_ema,
                    2
                ),

            "ideal_entry":
                ideal_entry,

            "entry_high":
                entry_high,

            "ma200_slope":
                round(
                    ma200_slope,
                    2
                ),

            "ema50_slope":
                round(
                    ema50_slope,
                    2
                ),

            "atr":
                round(
                    atr,
                    2
                ),

            "support":
                round(
                    support,
                    2
                ),

            "resistance":
                round(
                    resistance,
                    2
                ),

            "volume_ratio":
                round(
                    volume_ratio,
                    2
                ),

            "stop_loss":
                risk["stop_loss"],

            "stop_loss_pct":
                risk.get(
                    "stop_loss_pct",
                    0
                ),

            "shares":
                risk["shares"],

            "position_value":
                risk["position_value"],

            "actual_risk":
                risk["actual_risk"],

            "risk_per_share":
                risk["risk_per_share"],

            "tp1":
                risk["tp1"],

            "days_tp1_text":
                days_tp1_text,

            "tp2":
                risk["tp2"],

            "days_tp2_text":
                days_tp2_text,

            "rr1":
                risk["rr1"],

            "rr2":
                risk["rr2"],

            "reasons":
                reasons,

            "exit_strategy":
                exit_strategy_text,
        }

    except (
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        ZeroDivisionError
    ):

        return None
