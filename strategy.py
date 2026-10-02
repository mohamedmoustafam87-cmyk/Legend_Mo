import numpy as np
import pandas as pd

from config import (
    MIN_SCORE_THRESHOLD,
    MAX_ALLOWABLE_RSI,
    MAX_DISTANCE_FROM_EMA20,
)

from risk import calculate_risk_management
from indicators import analyze_candlesticks


# ==========================================================
# Helpers
# ==========================================================

def safe_float(value, default=np.nan):

    try:

        if value is None:
            return default

        value = float(value)

        if pd.isna(value):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):

        return default


def clamp(
    value,
    minimum=0,
    maximum=100,
):

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def score_positive(
    value,
    points,
):

    return points if value else 0


# ==========================================================
# Trend Score - 20 Points
# ==========================================================

def calculate_trend_score(last):

    score = 0
    reasons = []

    close = safe_float(
        last.get("Close")
    )

    ema20 = safe_float(
        last.get("EMA_20")
    )

    ema50 = safe_float(
        last.get("EMA_50")
    )

    ma200 = safe_float(
        last.get("MA_200")
    )

    ema50_slope = safe_float(
        last.get("EMA50_Slope_10D")
    )

    ma200_slope = safe_float(
        last.get("MA200_Slope_20D")
    )

    adx = safe_float(
        last.get("ADX_14")
    )

    plus_di = safe_float(
        last.get("PLUS_DI")
    )

    minus_di = safe_float(
        last.get("MINUS_DI")
    )

    # ------------------------------------------------------
    # Price > MA200
    # ------------------------------------------------------

    if (
        not np.isnan(close)
        and not np.isnan(ma200)
        and close > ma200
    ):

        score += 4

        reasons.append(
            "السعر أعلى من MA200"
        )

    # ------------------------------------------------------
    # EMA20 > EMA50
    # ------------------------------------------------------

    if (
        not np.isnan(ema20)
        and not np.isnan(ema50)
        and ema20 > ema50
    ):

        score += 4

        reasons.append(
            "EMA20 أعلى من EMA50"
        )

    # ------------------------------------------------------
    # EMA50 positive slope
    # ------------------------------------------------------

    if (
        not np.isnan(ema50_slope)
        and ema50_slope > 0
    ):

        score += 3

        reasons.append(
            "ميل EMA50 إيجابي"
        )

    # ------------------------------------------------------
    # MA200 positive slope
    # ------------------------------------------------------

    if (
        not np.isnan(ma200_slope)
        and ma200_slope > 0
    ):

        score += 3

        reasons.append(
            "ميل MA200 إيجابي"
        )

    # ------------------------------------------------------
    # ADX
    # ------------------------------------------------------

    if not np.isnan(adx):

        if adx >= 25:

            score += 3

            reasons.append(
                "ADX يشير إلى اتجاه قوي"
            )

        elif adx >= 20:

            score += 2

            reasons.append(
                "ADX يشير إلى اتجاه متوسط"
            )

    # ------------------------------------------------------
    # DI confirmation
    # ------------------------------------------------------

    if (
        not np.isnan(plus_di)
        and not np.isnan(minus_di)
        and plus_di > minus_di
    ):

        score += 3

        reasons.append(
            "قوة المشترين أعلى من البائعين (DI+ > DI-)"
        )

    return (
        clamp(score, 0, 20),
        reasons
    )


# ==========================================================
# Momentum Score - 15 Points
# ==========================================================

def calculate_momentum_score(last):

    score = 0
    reasons = []

    rsi = safe_float(
        last.get("RSI_14")
    )

    macd = safe_float(
        last.get("MACD")
    )

    macd_signal = safe_float(
        last.get("MACD_Signal")
    )

    macd_hist = safe_float(
        last.get("MACD_Hist")
    )

    roc20 = safe_float(
        last.get("ROC_20D")
    )

    roc60 = safe_float(
        last.get("ROC_60D")
    )

    # ------------------------------------------------------
    # RSI
    # ------------------------------------------------------

    if not np.isnan(rsi):

        if 50 <= rsi <= 65:

            score += 5

            reasons.append(
                f"RSI إيجابي ومتوازن ({rsi:.1f})"
            )

        elif 45 <= rsi < 50:

            score += 3

        elif 65 < rsi <= 70:

            score += 3

            reasons.append(
                f"RSI قوي لكن قريب من التشبع ({rsi:.1f})"
            )

        elif 35 <= rsi < 45:

            score += 1

        elif rsi < 35:

            score += 2

            reasons.append(
                f"RSI منخفض ({rsi:.1f})"
            )

    # ------------------------------------------------------
    # MACD
    # ------------------------------------------------------

    if (
        not np.isnan(macd)
        and not np.isnan(macd_signal)
    ):

        if macd > macd_signal:

            score += 4

            reasons.append(
                "MACD أعلى من Signal"
            )

        if (
            not np.isnan(macd_hist)
            and macd_hist > 0
        ):

            score += 1

    # ------------------------------------------------------
    # ROC 20D
    # ------------------------------------------------------

    if not np.isnan(roc20):

        if roc20 > 5:

            score += 2

            reasons.append(
                f"العائد خلال 20 جلسة إيجابي ({roc20:.1f}%)"
            )

        elif roc20 > 0:

            score += 1

    # ------------------------------------------------------
    # ROC 60D
    # ------------------------------------------------------

    if not np.isnan(roc60):

        if roc60 > 10:

            score += 3

        elif roc60 > 0:

            score += 1

    return (
        clamp(score, 0, 15),
        reasons
    )


# ==========================================================
# Volume Score - 15 Points
# ==========================================================

def calculate_volume_score(last):

    score = 0
    reasons = []

    volume_ratio = safe_float(
        last.get("Volume_Ratio")
    )

    breakout_volume = bool(
        last.get(
            "Breakout_With_Volume",
            False
        )
    )

    # ------------------------------------------------------
    # Volume Ratio
    # ------------------------------------------------------

    if not np.isnan(volume_ratio):

        if volume_ratio >= 2:

            score += 8

            reasons.append(
                f"حجم تداول قوي جدًا ({volume_ratio:.2f}x)"
            )

        elif volume_ratio >= 1.5:

            score += 6

            reasons.append(
                f"حجم التداول أعلى من المتوسط ({volume_ratio:.2f}x)"
            )

        elif volume_ratio >= 1.0:

            score += 4

        elif volume_ratio >= 0.7:

            score += 2

    # ------------------------------------------------------
    # Breakout confirmation
    # ------------------------------------------------------

    if breakout_volume:

        score += 7

        reasons.append(
            "اختراق مؤكد بحجم تداول مرتفع"
        )

    return (
        clamp(score, 0, 15),
        reasons
    )


# ==========================================================
# Price Action Score - 15 Points
# ==========================================================

def calculate_price_action_score(last):

    score = 0
    reasons = []

    bullish_candle = bool(
        last.get(
            "Bullish_Candle",
            False
        )
    )

    strong_bullish = bool(
        last.get(
            "Strong_Bullish_Candle",
            False
        )
    )

    hammer = bool(
        last.get(
            "Hammer",
            False
        )
    )

    engulfing = bool(
        last.get(
            "Bullish_Engulfing",
            False
        )
    )

    breakout = bool(
        last.get(
            "Breakout_20",
            False
        )
    )

    breakdown = bool(
        last.get(
            "Breakdown_20",
            False
        )
    )

    # ------------------------------------------------------
    # Bullish candle
    # ------------------------------------------------------

    if bullish_candle:

        score += 2

    # ------------------------------------------------------
    # Strong bullish
    # ------------------------------------------------------

    if strong_bullish:

        score += 4

        reasons.append(
            "شمعة صاعدة قوية"
        )

    # ------------------------------------------------------
    # Hammer
    # ------------------------------------------------------

    if hammer:

        score += 3

        reasons.append(
            "ظهور Hammer"
        )

    # ------------------------------------------------------
    # Bullish Engulfing
    # ------------------------------------------------------

    if engulfing:

        score += 4

        reasons.append(
            "ظهور Bullish Engulfing"
        )

    # ------------------------------------------------------
    # Breakout
    # ------------------------------------------------------

    if breakout:

        score += 2

        reasons.append(
            "السعر فوق مقاومة 20 جلسة"
        )

    # ------------------------------------------------------
    # Breakdown penalty
    # ------------------------------------------------------

    if breakdown:

        score -= 5

        reasons.append(
            "السعر كسر دعم 20 جلسة"
        )

    return (
        clamp(score, 0, 15),
        reasons
    )


# ==========================================================
# Support / Resistance Score - 15 Points
# ==========================================================

def calculate_sr_score(last):

    score = 0
    reasons = []

    close = safe_float(
        last.get("Close")
    )

    support20 = safe_float(
        last.get("Support_20")
    )

    resistance20 = safe_float(
        last.get("Resistance_20")
    )

    distance_support = safe_float(
        last.get(
            "Distance_From_Support_Pct"
        )
    )

    distance_resistance = safe_float(
        last.get(
            "Distance_From_Resistance_Pct"
        )
    )

    if np.isnan(close):

        return 0, reasons

    # ------------------------------------------------------
    # Near support
    # ------------------------------------------------------

    if (
        not np.isnan(distance_support)
        and 0 <= distance_support <= 3
    ):

        score += 6

        reasons.append(
            "السعر قريب من منطقة دعم"
        )

    elif (
        not np.isnan(distance_support)
        and 3 < distance_support <= 6
    ):

        score += 3

    # ------------------------------------------------------
    # Distance from resistance
    # ------------------------------------------------------

    if (
        not np.isnan(distance_resistance)
        and distance_resistance > 5
    ):

        score += 4

        reasons.append(
            "مساحة جيدة نسبيًا حتى المقاومة"
        )

    elif (
        not np.isnan(distance_resistance)
        and 2 <= distance_resistance <= 5
    ):

        score += 2

    # ------------------------------------------------------
    # Price above support
    # ------------------------------------------------------

    if (
        not np.isnan(support20)
        and close > support20
    ):

        score += 2

    # ------------------------------------------------------
    # Price below resistance
    # ------------------------------------------------------

    if (
        not np.isnan(resistance20)
        and close < resistance20
    ):

        score += 3

    return (
        clamp(score, 0, 15),
        reasons
    )


# ==========================================================
# Money Flow Score - 10 Points
# ==========================================================

def calculate_money_flow_score(last):

    score = 0
    reasons = []

    obv_bullish = bool(
        last.get(
            "OBV_Bullish",
            False
        )
    )

    obv_slope = safe_float(
        last.get(
            "OBV_Slope_10D"
        )
    )

    cmf = safe_float(
        last.get(
            "CMF_20"
        )
    )

    mfi = safe_float(
        last.get(
            "MFI_14"
        )
    )

    ad_slope = safe_float(
        last.get(
            "AD_Slope_20D"
        )
    )

    # ------------------------------------------------------
    # OBV
    # ------------------------------------------------------

    if obv_bullish:

        score += 3

        reasons.append(
            "OBV يدعم الاتجاه الصاعد"
        )

    if (
        not np.isnan(obv_slope)
        and obv_slope > 0
    ):

        score += 1

    # ------------------------------------------------------
    # CMF
    # ------------------------------------------------------

    if not np.isnan(cmf):

        if cmf > 0.10:

            score += 3

            reasons.append(
                f"CMF يشير إلى دخول سيولة ({cmf:.2f})"
            )

        elif cmf > 0:

            score += 2

        elif cmf < -0.10:

            score -= 2

            reasons.append(
                f"CMF يشير إلى ضغط بيعي ({cmf:.2f})"
            )

    # ------------------------------------------------------
    # MFI
    # ------------------------------------------------------

    if not np.isnan(mfi):

        if 50 <= mfi <= 70:

            score += 2

        elif mfi > 80:

            score -= 1

        elif mfi < 25:

            score += 1

    # ------------------------------------------------------
    # A/D Line
    # ------------------------------------------------------

    if (
        not np.isnan(ad_slope)
        and ad_slope > 0
    ):

        score += 1

        reasons.append(
            "خط التجميع/التصريف في اتجاه إيجابي"
        )

    return (
        clamp(score, 0, 10),
        reasons
    )


# ==========================================================
# Volatility Score - 5 Points
# ==========================================================

def calculate_volatility_score(last):

    score = 0
    reasons = []

    atr_pct = safe_float(
        last.get("ATR_Pct")
    )

    bb_position = safe_float(
        last.get("BB_POSITION")
    )

    if not np.isnan(atr_pct):

        if 1.5 <= atr_pct <= 4:

            score += 3

        elif atr_pct < 1.5:

            score += 2

        elif atr_pct <= 6:

            score += 1

        else:

            reasons.append(
                f"تذبذب مرتفع (ATR {atr_pct:.1f}%)"
            )

    # ------------------------------------------------------
    # Bollinger Position
    # ------------------------------------------------------

    if not np.isnan(bb_position):

        if 30 <= bb_position <= 70:

            score += 2

        elif bb_position < 20:

            score += 1

        elif bb_position > 90:

            reasons.append(
                "السعر قريب من الحد العلوي لبولينجر"
            )

    return (
        clamp(score, 0, 5),
        reasons
    )


# ==========================================================
# Price Strength Score - 5 Points
# ==========================================================

def calculate_price_strength_score(last):

    score = 0
    reasons = []

    position52 = safe_float(
        last.get("Position_52W")
    )

    return20 = safe_float(
        last.get("Return_20D")
    )

    return60 = safe_float(
        last.get("Return_60D")
    )

    # ------------------------------------------------------
    # 52 Week Position
    # ------------------------------------------------------

    if not np.isnan(position52):

        if position52 >= 70:

            score += 2

        elif position52 >= 50:

            score += 1

        elif position52 < 25:

            score += 1

    # ------------------------------------------------------
    # 20D Return
    # ------------------------------------------------------

    if not np.isnan(return20):

        if return20 > 5:

            score += 1

        elif return20 > 0:

            score += 0.5

    # ------------------------------------------------------
    # 60D Return
    # ------------------------------------------------------

    if not np.isnan(return60):

        if return60 > 10:

            score += 2

        elif return60 > 0:

            score += 1

    return (
        clamp(score, 0, 5),
        reasons
    )


# ==========================================================
# Forecast / Scenario
# ==========================================================

def calculate_forecast_scores(
    total_score,
    momentum_score,
    trend_score,
    volume_score,
):

    # ------------------------------------------------------
    # 1 Month
    # ------------------------------------------------------

    score_1m = (
        total_score * 0.50
        +
        trend_score * 1.0
        +
        momentum_score * 1.0
        +
        volume_score * 0.5
    )

    # Normalize
    score_1m = clamp(
        score_1m / 1.20,
        0,
        100
    )

    # ------------------------------------------------------
    # 2 Months
    # ------------------------------------------------------

    score_2m = (
        total_score * 0.55
        +
        trend_score * 1.10
        +
        momentum_score * 0.75
        +
        volume_score * 0.50
    )

    score_2m = clamp(
        score_2m / 1.25,
        0,
        100
    )

    return (
        round(score_1m),
        round(score_2m)
    )


def forecast_status(score):

    if score >= 75:

        return "🟢 صاعد قوي"

    if score >= 60:

        return "🟢 صاعد"

    if score >= 45:

        return "🟡 عرضي / محايد"

    if score >= 30:

        return "🟠 ضعيف"

    return "🔴 هابط"


# ==========================================================
# Exit Strategy
# ==========================================================

def calculate_exit_strategy(
    rsi,
    score,
    macd_hist,
    price,
    ema20,
):

    if np.isnan(rsi):

        return "مراقبة المؤشرات قبل الخروج"

    # IMPORTANT:
    # Check 80 before 75.

    if rsi >= 80:

        return (
            "تشبع شرائي مرتفع جدًا؛ "
            "راقب جني الأرباح أو ظهور إشارة انعكاس."
        )

    if rsi >= 75:

        return (
            "السهم في منطقة تشبع شرائي؛ "
            "راقب ضعف الزخم أو كسر EMA20."
        )

    if (
        not np.isnan(macd_hist)
        and macd_hist < 0
    ):

        return (
            "الزخم يضعف؛ "
            "راقب استمرار انخفاض MACD Histogram."
        )

    if (
        not np.isnan(ema20)
        and price < ema20
    ):

        return (
            "السعر تحت EMA20؛ "
            "راقب كسر الدعم القريب."
        )

    if score < 45:

        return (
            "ضعف واضح في المؤشرات؛ "
            "تجنب زيادة المخاطرة."
        )

    return (
        "استمرار المراقبة مع الالتزام "
        "بمستوى وقف الخسارة."
    )


# ==========================================================
# Main Strategy
# ==========================================================

def evaluate_stock_strategy(
    df,
    ticker
):

    if df is None or df.empty:

        return None

    required = [

        "Close",
        "EMA_20",
        "EMA_50",
        "MA_200",
        "RSI_14",
        "ATR_14",
        "MACD",
        "MACD_Signal",
        "ADX_14",
        "Volume_Ratio",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        return None

    if len(df) < 220:

        return None

    last = df.iloc[-1]

    price = safe_float(
        last.get("Close")
    )

    atr = safe_float(
        last.get("ATR_14")
    )

    rsi = safe_float(
        last.get("RSI_14")
    )

    ema20 = safe_float(
        last.get("EMA_20")
    )

    ema50 = safe_float(
        last.get("EMA_50")
    )

    ma200 = safe_float(
        last.get("MA_200")
    )

    macd_hist = safe_float(
        last.get("MACD_Hist")
    )

    adx = safe_float(
        last.get("ADX_14")
    )

    volume_ratio = safe_float(
        last.get("Volume_Ratio")
    )

    if (
        np.isnan(price)
        or price <= 0
    ):

        return None

    # ======================================================
    # RSI Hard Filter
    # ======================================================

    if (
        not np.isnan(rsi)
        and rsi > MAX_ALLOWABLE_RSI
    ):

        return None

    # ======================================================
    # SCORE COMPONENTS
    # ======================================================

    trend_score, trend_reasons = (
        calculate_trend_score(
            last
        )
    )

    momentum_score, momentum_reasons = (
        calculate_momentum_score(
            last
        )
    )

    volume_score, volume_reasons = (
        calculate_volume_score(
            last
        )
    )

    price_action_score, price_action_reasons = (
        calculate_price_action_score(
            last
        )
    )

    sr_score, sr_reasons = (
        calculate_sr_score(
            last
        )
    )

    money_flow_score, money_flow_reasons = (
        calculate_money_flow_score(
            last
        )
    )

    volatility_score, volatility_reasons = (
        calculate_volatility_score(
            last
        )
    )

    price_strength_score, price_strength_reasons = (
        calculate_price_strength_score(
            last
        )
    )

    # ======================================================
    # TOTAL SCORE
    # ======================================================

    score = (

        trend_score
        +
        momentum_score
        +
        volume_score
        +
        price_action_score
        +
        sr_score
        +
        money_flow_score
        +
        volatility_score
        +
        price_strength_score

    )

    score = int(
        round(
            clamp(
                score,
                0,
                100
            )
        )
    )

    # ======================================================
    # ALL REASONS
    # ======================================================

    reasons = []

    reasons.extend(
        trend_reasons
    )

    reasons.extend(
        momentum_reasons
    )

    reasons.extend(
        volume_reasons
    )

    reasons.extend(
        price_action_reasons
    )

    reasons.extend(
        sr_reasons
    )

    reasons.extend(
        money_flow_reasons
    )

    reasons.extend(
        volatility_reasons
    )

    reasons.extend(
        price_strength_reasons
    )

    # Remove duplicates
    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    # ======================================================
    # FORECAST
    # ======================================================

    score_1m, score_2m = (
        calculate_forecast_scores(
            score,
            momentum_score,
            trend_score,
            volume_score,
        )
    )

    forecast_1m_status = (
        forecast_status(
            score_1m
        )
    )

    forecast_2m_status = (
        forecast_status(
            score_2m
        )
    )

    # ======================================================
    # TREND STATUS
    # ======================================================

    if (
        not np.isnan(ema20)
        and not np.isnan(ema50)
        and not np.isnan(ma200)
    ):

        if (
            price > ema20
            and ema20 > ema50
            and ema50 > ma200
        ):

            trend_status = (
                "📈 صاعد قوي"
            )

        elif (
            price > ema50
            and ema50 > ma200
        ):

            trend_status = (
                "📈 صاعد"
            )

        elif (
            price < ema20
            and ema20 < ema50
            and ema50 < ma200
        ):

            trend_status = (
                "📉 هابط قوي"
            )

        elif price < ma200:

            trend_status = (
                "📉 تحت MA200"
            )

        else:

            trend_status = (
                "↔️ عرضي / انتقالي"
            )

    else:

        trend_status = (
            "غير محدد"
        )

    # ======================================================
    # DISTANCE FROM EMA20
    # ======================================================

    distance_from_ema20 = safe_float(
        last.get(
            "EMA20_Distance_Pct"
        )
    )

    overextended = (
        not np.isnan(
            distance_from_ema20
        )
        and
        distance_from_ema20
        > MAX_DISTANCE_FROM_EMA20
    )

    too_far_below_ema = (
        not np.isnan(
            distance_from_ema20
        )
        and
        distance_from_ema20
        < -10
    )

    # ======================================================
    # SUPPORT / RESISTANCE
    # ======================================================

    support = safe_float(
        last.get(
            "Support_20"
        )
    )

    resistance = safe_float(
        last.get(
            "Resistance_20"
        )
    )

    # ======================================================
    # ENTRY
    # ======================================================

    max_allowed_drop = (
        price * 0.985
    )

    if (
        not np.isnan(support)
        and support > 0
        and support < price
    ):

        realistic_support = max(
            support,
            max_allowed_drop
        )

    else:

        realistic_support = (
            max_allowed_drop
        )

    ideal_entry = (
        realistic_support
    )

    entry_high = price

    # ======================================================
    # RISK MANAGEMENT
    # ======================================================

    risk_data = (
        calculate_risk_management(
            price,
            atr,
            support=support
        )
        if not np.isnan(atr)
        else {}
    )

    stop_loss = safe_float(
        risk_data.get(
            "stop_loss"
        )
    )

    if np.isnan(stop_loss):

        stop_loss = (
            price
            - 2 * atr
            if not np.isnan(atr)
            else price * 0.95
        )

    # ======================================================
    # TARGETS
    # ======================================================

    risk_per_share = (
        price
        - stop_loss
    )

    if (
        np.isnan(risk_per_share)
        or risk_per_share <= 0
    ):

        risk_per_share = (
            price * 0.05
        )

    tp1 = (
        price
        + risk_per_share * 2
    )

    tp2 = (
        price
        + risk_per_share * 3
    )

    # Use risk.py values if available
    if risk_data:

        tp1 = safe_float(
            risk_data.get(
                "tp1"
            ),
            tp1
        )

        tp2 = safe_float(
            risk_data.get(
                "tp2"
            ),
            tp2
        )

    # ======================================================
    # RISK / REWARD
    # ======================================================

    rr1 = (
        (
            tp1 - price
        )
        /
        risk_per_share
    )

    rr2 = (
        (
            tp2 - price
        )
        /
        risk_per_share
    )

    stop_loss_pct = (
        (
            stop_loss
            - price
        )
        /
        price
    ) * 100

    # ======================================================
    # TP TIME ESTIMATE
    # ======================================================

    if (
        not np.isnan(atr)
        and atr > 0
    ):

        atr_pct = (
            atr
            / price
        )

        days_tp1 = max(
            2,
            int(
                round(
                    (
                        tp1 - price
                    )
                    /
                    atr
                )
            )
        )

        days_tp2 = max(
            3,
            int(
                round(
                    (
                        tp2 - price
                    )
                    /
                    atr
                )
            )
        )

        if atr_pct > 0.05:

            days_tp1 = max(
                1,
                days_tp1 - 1
            )

            days_tp2 = max(
                2,
                days_tp2 - 2
            )

    else:

        days_tp1 = 10
        days_tp2 = 20

    days_tp1_text = (
        f"{days_tp1} جلسة تقريبًا"
    )

    days_tp2_text = (
        f"{days_tp2} جلسة تقريبًا"
    )

    # ======================================================
    # RECOMMENDATION
    # ======================================================

    if score >= 80:

        rec = (
            "🔥 شراء قوي جدًا"
        )

    elif score >= 70:

        rec = (
            "🟢 فرصة شراء قوية"
        )

    elif score >= 60:

        rec = (
            "🟡 فرصة شراء جيدة"
        )

    elif score >= 50:

        rec = (
            "🟠 مراقبة"
        )

    else:

        rec = (
            "🔴 ضعيف"
        )

    # ======================================================
    # EXIT STRATEGY
    # ======================================================

    exit_strategy = (
        calculate_exit_strategy(
            rsi,
            score,
            macd_hist,
            price,
            ema20,
        )
    )

    # ======================================================
    # CANDLE REASONS
    # ======================================================

    candle_reasons = (
        analyze_candlesticks(
            df
        )
    )

    for reason in candle_reasons:

        if reason not in reasons:

            reasons.append(
                reason
            )

    # ======================================================
    # RETURN
    # ======================================================

    return {

        "ticker":
            ticker,

        # --------------------------------------------------
        # Main score
        # --------------------------------------------------

        "score":
            score,

        "rec":
            rec,

        # --------------------------------------------------
        # Score breakdown
        # --------------------------------------------------

        "score_breakdown": {

            "trend":
                trend_score,

            "momentum":
                momentum_score,

            "volume":
                volume_score,

            "price_action":
                price_action_score,

            "support_resistance":
                sr_score,

            "money_flow":
                money_flow_score,

            "volatility":
                volatility_score,

            "price_strength":
                price_strength_score,
        },

        "trend_score":
            trend_score,

        "momentum_score":
            momentum_score,

        "volume_score":
            volume_score,

        "price_action_score":
            price_action_score,

        "sr_score":
            sr_score,

        "money_flow_score":
            money_flow_score,

        "volatility_score":
            volatility_score,

        "price_strength_score":
            price_strength_score,

        # --------------------------------------------------
        # Price
        # --------------------------------------------------

        "price":
            price,

        "strategy_price":
            price,

        # --------------------------------------------------
        # Trend
        # --------------------------------------------------

        "trend_status":
            trend_status,

        # --------------------------------------------------
        # Forecast
        # --------------------------------------------------

        "forecast_1m_score":
            score_1m,

        "forecast_2m_score":
            score_2m,

        "forecast_1m_status":
            forecast_1m_status,

        "forecast_2m_status":
            forecast_2m_status,

        # Backward compatibility
        "score_1m":
            score_1m,

        "score_2m":
            score_2m,

        # --------------------------------------------------
        # Technical
        # --------------------------------------------------

        "rsi":
            rsi,

        "adx":
            adx,

        "atr":
            atr,

        "volume_ratio":
            volume_ratio,

        "ema20":
            ema20,

        "ema50":
            ema50,

        "ma200":
            ma200,

        "ema20_distance_pct":
            distance_from_ema20,

        "support":
            support,

        "resistance":
            resistance,

        # --------------------------------------------------
        # Entry
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Risk
        # --------------------------------------------------

        "stop_loss":
            round(
                stop_loss,
                2
            ),

        "stop_loss_pct":
            round(
                stop_loss_pct,
                2
            ),

        "risk_per_share":
            round(
                risk_per_share,
                2
            ),

        "shares":
            risk_data.get(
                "shares",
                0
            ),

        "position_value":
            risk_data.get(
                "position_value",
                0
            ),

        "actual_risk":
            risk_data.get(
                "actual_risk",
                0
            ),

        # --------------------------------------------------
        # Targets
        # --------------------------------------------------

        "tp1":
            round(
                tp1,
                2
            ),

        "tp2":
            round(
                tp2,
                2
            ),

        "rr1":
            round(
                rr1,
                2
            ),

        "rr2":
            round(
                rr2,
                2
            ),

        "days_tp1":
            days_tp1,

        "days_tp2":
            days_tp2,

        "days_tp1_text":
            days_tp1_text,

        "days_tp2_text":
            days_tp2_text,

        # --------------------------------------------------
        # Flags
        # --------------------------------------------------

        "overextended":
            overextended,

        "too_far_below_ema":
            too_far_below_ema,

        # --------------------------------------------------
        # Reasons
        # --------------------------------------------------

        "reasons":
            reasons,

        # --------------------------------------------------
        # Exit
        # --------------------------------------------------

        "exit_strategy":
            exit_strategy,

        # --------------------------------------------------
        # Data
        # --------------------------------------------------

        "historical_close":
            df.attrs.get(
                "historical_close"
            ),

        "current_price":
            df.attrs.get(
                "current_price"
            ),

        "price_source":
            df.attrs.get(
                "price_source"
            ),

        "is_realtime":
            df.attrs.get(
                "is_realtime",
                False
            ),

        "current_vs_close_pct":
            df.attrs.get(
                "current_vs_close_pct"
            ),

        "data_source":
            df.attrs.get(
                "data_source"
            ),
            }
