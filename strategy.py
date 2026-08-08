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
        macd_signal = float(latest["MACD_signal"])

        prev_macd = float(prev["MACD"])
        prev_signal = float(prev["MACD_signal"])

        atr = float(latest["ATR"])

        volume = float(latest["Volume"])
        vol_sma20 = float(latest["Vol_SMA20"])

        resistance = float(latest["Resistance_20"])
        support = float(latest["Support_20"])

        # ==========================================================
        # Validation
        # ==========================================================

        if (
            close_price <= 0
            or ma200 <= 0
            or ema20 <= 0
            or ema50 <= 0
            or atr <= 0
        ):
            return None

        # ==========================================================
        # 1 Month Performance
        # حوالي 21 جلسة تداول
        # ==========================================================

        if len(df) >= 22:

            price_1m_ago = float(
                df["Close"].iloc[-22]
            )

            return_1m = (
                (close_price - price_1m_ago)
                / price_1m_ago
            ) * 100

        else:

            return_1m = 0

        # ==========================================================
        # 2 Month Performance
        # حوالي 42 جلسة تداول
        # ==========================================================

        if len(df) >= 43:

            price_2m_ago = float(
                df["Close"].iloc[-43]
            )

            return_2m = (
                (close_price - price_2m_ago)
                / price_2m_ago
            ) * 100

        else:

            return_2m = 0

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
        # Trend Classification
        # ==========================================================

        bullish_1m = return_1m > 0
        bullish_2m = return_2m > 0

        strong_1m = return_1m >= 3
        strong_2m = return_2m >= 5

        if strong_1m and strong_2m:

            trend_status = "🟢 اتجاه صاعد قوي"

        elif bullish_1m and bullish_2m:

            trend_status = "🟢 اتجاه صاعد مستمر"

        elif bullish_1m:

            trend_status = "🟡 صاعد قصير المدى"

        elif bullish_2m:

            trend_status = "🟡 صاعد على مدى شهرين"

        else:

            trend_status = "🔴 الاتجاه غير صاعد"

        # ==========================================================
        # Score
        # ==========================================================

        score = 0
        reasons = []

        # ==========================================================
        # Long Term Trend - 15 Points
        # ==========================================================

        if close_price > ma200:

            score += 10

            reasons.append(
                "✅ السعر أعلى من متوسط 200 يوم"
            )

        if ma200_slope > 0:

            score += 5

            reasons.append(
                f"📈 MA200 في اتجاه صاعد ({ma200_slope:.1f}%)"
            )

        # ==========================================================
        # Medium Term Trend - 15 Points
        # ==========================================================

        if ema20 > ema50:

            score += 10

            reasons.append(
                "📈 EMA20 أعلى من EMA50"
            )

        if ema50_slope > 0:

            score += 5

            reasons.append(
                f"📈 EMA50 صاعد ({ema50_slope:.1f}%)"
            )

        # ==========================================================
        # 1 Month Trend - 10 Points
        # ==========================================================

        if return_1m >= 5:

            score += 10

            reasons.append(
                f"🚀 أداء الشهر إيجابي (+{return_1m:.1f}%)"
            )

        elif return_1m > 0:

            score += 5

            reasons.append(
                f"🟢 أداء الشهر إيجابي (+{return_1m:.1f}%)"
            )

        # ==========================================================
        # 2 Month Trend - 10 Points
        # ==========================================================

        if return_2m >= 8:

            score += 10

            reasons.append(
                f"🚀 اتجاه الشهرين قوي (+{return_2m:.1f}%)"
            )

        elif return_2m > 0:

            score += 5

            reasons.append(
                f"🟢 أداء الشهرين إيجابي (+{return_2m:.1f}%)"
            )

        # ==========================================================
        # ADX - 10 Points
        # ==========================================================

        if adx > 25 and adx > prev_adx:

            score += 10

            reasons.append(
                f"💪 ترند قوي ومتزايد (ADX: {adx:.1f})"
            )

        elif adx > 20:

            score += 5

            reasons.append(
                f"📊 قوة اتجاه مقبولة (ADX: {adx:.1f})"
            )

        # ==========================================================
        # RSI - 10 Points
        # ==========================================================

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

        # ==========================================================
        # MACD - 10 Points
        # ==========================================================

        bullish_macd_cross = (
            prev_macd <= prev_signal
            and macd > macd_signal
        )

        macd_positive = (
            macd > macd_signal
            and macd > 0
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

        # ==========================================================
        # Volume - 10 Points
        # ==========================================================

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

        elif volume_ratio >= 1.0:

            score += 5

            reasons.append(
                f"📊 حجم تداول جيد ({volume_ratio:.1f}x المتوسط)"
            )

        # ==========================================================
        # Candlestick Confirmation
        # ==========================================================

        candle_reasons = analyze_candlesticks(df)

        if candle_reasons:

            score += min(
                len(candle_reasons) * 5,
                5
            )

            reasons.extend(
                candle_reasons
            )

        # ==========================================================
        # Score Limit
        # ==========================================================

        score = min(score, 100)

        # ==========================================================
        # Entry Analysis
        # ==========================================================

        distance_from_ema = (
            (close_price - ema20)
            / ema20
        ) * 100

        overextended = distance_from_ema > 5

        # ==========================================================
        # Breakout
        # ==========================================================

        breakout = close_price > resistance

        if breakout:

            reasons.append(
                "🎯 السعر اخترق مقاومة الـ20 جلسة"
            )

        # ==========================================================
        # Ideal Entry Zone
        # ==========================================================

        entry_candidates = [
            ema20,
            ema50,
            support
        ]

        entry_candidates = [
            x for x in entry_candidates
            if x > 0
        ]

        if entry_candidates:

            ideal_entry = min(
                entry_candidates
            )

            entry_high = max(
                entry_candidates
            )

        else:

            ideal_entry = close_price
            entry_high = close_price

        # ==========================================================
        # Entry Status
        # ==========================================================

        if overextended:

            entry_status = "🟡 WAIT - السعر ممتد"

        elif (
            close_price >= ideal_entry
            and close_price <= entry_high * 1.02
        ):

            entry_status = "🟢 BUY ZONE"

        elif breakout:

            entry_status = "🟢 BUY - Breakout"

        else:

            entry_status = "🟡 WATCH"

        # ==========================================================
        # Risk Management
        # مهم: تمرير Support إلى risk.py
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

            recommendation = (
                "🔴 AVOID / لا توجد إشارة شراء كافية"
            )

        elif (
            trend_status.startswith("🟢")
            and entry_status.startswith("🟢")
        ):

            recommendation = (
                "🟢 BUY - شراء"
            )

        elif trend_status.startswith("🟢"):

            recommendation = (
                "🟡 WATCH - الاتجاه قوي وانتظر دخول أفضل"
            )

        else:

            recommendation = (
                "🟡 WATCH"
            )

        # ==========================================================
        # Return Result
        # ==========================================================

        return {

            "ticker":
                ticker_symbol.replace(
                    ".CA",
                    ""
                ),

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

            "entry_status":
                entry_status,

            "return_1m":
                round(
                    return_1m,
                    2
                ),

            "return_2m":
                round(
                    return_2m,
                    2
                ),

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

            "distance_from_ema":
                round(
                    distance_from_ema,
                    2
                ),

            "ideal_entry":
                round(
                    ideal_entry,
                    2
                ),

            "entry_high":
                round(
                    entry_high,
                    2
                ),

            "atr":
                round(
                    atr,
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

            "tp2":
                risk["tp2"],

            "rr1":
                risk["rr1"],

            "rr2":
                risk["rr2"],

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

            "reasons":
                reasons
        }

    except (
        TypeError,
        ValueError,
        KeyError,
        IndexError,
        ZeroDivisionError
    ):

        return None
