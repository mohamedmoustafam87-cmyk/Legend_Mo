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
        ):
            return None


        # ==========================================================
        # 1 MONTH TREND
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
        # 2 MONTH TREND
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
        # هل الاتجاه المتوسط يتحسن؟
        # ==========================================================

        if len(df) >= 11:

            ema50_10_days_ago = float(
                df["EMA_50"].iloc[-11]
            )

            ema50_slope = (
                (ema50 - ema50_10_days_ago)
                / ema50_10_days_ago
            ) * 100

        else:

            ema50_slope = 0


        # ==========================================================
        # MA200 Slope
        # الاتجاه طويل المدى
        # ==========================================================

        if len(df) >= 21:

            ma200_20_days_ago = float(
                df["MA_200"].iloc[-21]
            )

            ma200_slope = (
                (ma200 - ma200_20_days_ago)
                / ma200_20_days_ago
            ) * 100

        else:

            ma200_slope = 0


        # ==========================================================
        # Trend Classification
        # ==========================================================

        bullish_1m = (
            return_1m > 0
        )

        bullish_2m = (
            return_2m > 0
        )

        strong_1m = (
            return_1m >= 3
        )

        strong_2m = (
            return_2m >= 5
        )


        if strong_1m and strong_2m:

            trend_status = (
                "🟢 اتجاه صاعد قوي"
            )

        elif bullish_1m and bullish_2m:

            trend_status = (
                "🟢 اتجاه صاعد مستمر"
            )

        elif bullish_1m:

            trend_status = (
                "🟡 صاعد قصير المدى"
            )

        elif bullish_2m:

            trend_status = (
                "🟡 صاعد على مدى شهرين"
            )

        else:

            trend_status = (
                "🔴 الاتجاه غير صاعد"
            )


        # ==========================================================
        # Score
        # ==========================================================

        score = 0
        reasons = []


        # ==========================================================
        # LONG TERM TREND
        # 15 Points
        # ==========================================================

        if close_price > ma200:

            score += 10

            reasons.append(
                "✅ السعر أعلى من متوسط 200 يوم"
            )

        if ma200_slope > 0:

            score += 5

            reasons.append(
                f"📈 MA200 في اتجاه صاعد "
                f"({ma200_slope:.1f}%)"
            )


        # ==========================================================
        # MEDIUM TERM TREND
        # 15 Points
        # ==========================================================

        if ema20 > ema50:

            score += 10

            reasons.append(
                "📈 EMA20 أعلى من EMA50"
            )

        if ema50_slope > 0:

            score += 5

            reasons.append(
                f"📈 EMA50 صاعد "
                f"({ema50_slope:.1f}%)"
            )


        # ==========================================================
        # 1 MONTH TREND
        # 10 Points
        # ==========================================================

        if return_1m >= 5:

            score += 10

            reasons.append(
                f"🚀 أداء الشهر إيجابي "
                f"(+{return_1m:.1f}%)"
            )

        elif return_1m > 0:

            score += 5

            reasons.append(
                f"🟢 أداء الشهر إيجابي "
                f"(+{return_1m:.1f}%)"
            )


        # ==========================================================
        # 2 MONTH TREND
        # 10 Points
        # ==========================================================

        if return_2m >= 8:

            score += 10

            reasons.append(
                f"🚀 اتجاه الشهرين قوي "
                f"(+{return_2m:.1f}%)"
            )

        elif return_2m > 0:

            score += 5

            reasons.append(
                f"🟢 أداء الشهرين إيجابي "
                f"(+{return_2m:.1f}%)"
            )


        # ==========================================================
        # ADX
        # 10 Points
        # ==========================================================

        if (
            adx > 25
            and adx > prev_adx
        ):

            score += 10

            reasons.append(
                f"💪 ترند قوي ومتزايد "
                f"(ADX: {adx:.1f})"
            )

        elif adx > 20:

            score += 5

            reasons.append(
                f"📊 قوة اتجاه مقبولة "
                f"(ADX: {adx:.1f})"
            )


        # ==========================================================
        # RSI
        # 10 Points
        # ==========================================================

        if 50 <= rsi <= 65:

            score += 10

            reasons.append(
                f"🔥 RSI مناسب للزخم "
                f"({rsi:.1f})"
            )

        elif 45 <= rsi < 50:

            score += 5

            reasons.append(
                f"⚠️ RSI ضعيف نسبيًا "
                f"({rsi:.1f})"
            )

        elif rsi > 70:

            reasons.append(
                f"⚠️ RSI مرتفع جدًا "
                f"({rsi:.
