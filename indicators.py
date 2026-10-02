import numpy as np
import pandas as pd

from config import (
    RSI_PERIOD,
    ATR_PERIOD,
    EMA_FAST,
    EMA_SLOW,
    MA_LONG,
    ADX_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    VOLUME_MA_PERIOD,
    SUPPORT_RESISTANCE_PERIOD,
)


# ==========================================================
# Helpers
# ==========================================================

def safe_numeric(series):
    return pd.to_numeric(
        series,
        errors="coerce"
    )


# ==========================================================
# Main Indicators
# ==========================================================

def calculate_indicators(df):

    if df is None or df.empty:
        return None

    df = df.copy()

    # ------------------------------------------------------
    # Preserve metadata
    # ------------------------------------------------------

    attrs = dict(
        getattr(
            df,
            "attrs",
            {}
        )
    )

    # ------------------------------------------------------
    # Required OHLCV
    # ------------------------------------------------------

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required_columns:

        if column not in df.columns:
            return None

        df[column] = safe_numeric(
            df[column]
        )

    df.dropna(
        subset=required_columns,
        inplace=True
    )

    if len(df) < 220:
        return None

    # ======================================================
    # MOVING AVERAGES
    # ======================================================

    df["SMA_50"] = (
        df["Close"]
        .rolling(50)
        .mean()
    )

    df["SMA_200"] = (
        df["Close"]
        .rolling(200)
        .mean()
    )

    # Existing strategy alias
    df["MA_200"] = df["SMA_200"]

    # ======================================================
    # EXPONENTIAL MOVING AVERAGES
    # ======================================================

    df["EMA_20"] = (
        df["Close"]
        .ewm(
            span=EMA_FAST,
            adjust=False
        )
        .mean()
    )

    df["EMA_50"] = (
        df["Close"]
        .ewm(
            span=EMA_SLOW,
            adjust=False
        )
        .mean()
    )

    # ======================================================
    # RSI
    # ======================================================

    delta = df["Close"].diff()

    gain = (
        delta.clip(lower=0)
        .ewm(
            alpha=1 / RSI_PERIOD,
            adjust=False
        )
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .ewm(
            alpha=1 / RSI_PERIOD,
            adjust=False
        )
        .mean()
    )

    rs = gain / loss.replace(
        0,
        np.nan
    )

    df["RSI_14"] = (
        100
        - (
            100
            / (1 + rs)
        )
    )

    # ======================================================
    # TRUE RANGE / ATR
    # ======================================================

    previous_close = (
        df["Close"].shift(1)
    )

    tr1 = (
        df["High"]
        - df["Low"]
    )

    tr2 = (
        df["High"]
        - previous_close
    ).abs()

    tr3 = (
        df["Low"]
        - previous_close
    ).abs()

    df["True_Range"] = pd.concat(
        [
            tr1,
            tr2,
            tr3,
        ],
        axis=1
    ).max(axis=1)

    df["ATR_14"] = (
        df["True_Range"]
        .ewm(
            alpha=1 / ATR_PERIOD,
            adjust=False
        )
        .mean()
    )

    # ATR as percentage of price
    df["ATR_Pct"] = (
        df["ATR_14"]
        / df["Close"]
    ) * 100

    # ======================================================
    # MACD
    # ======================================================

    ema_fast = (
        df["Close"]
        .ewm(
            span=MACD_FAST,
            adjust=False
        )
        .mean()
    )

    ema_slow = (
        df["Close"]
        .ewm(
            span=MACD_SLOW,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        ema_fast
        - ema_slow
    )

    df["MACD_Signal"] = (
        df["MACD"]
        .ewm(
            span=MACD_SIGNAL,
            adjust=False
        )
        .mean()
    )

    df["MACD_Hist"] = (
        df["MACD"]
        - df["MACD_Signal"]
    )

    # MACD crossover
    df["MACD_Bullish_Cross"] = (
        (
            df["MACD"]
            > df["MACD_Signal"]
        )
        &
        (
            df["MACD"].shift(1)
            <=
            df["MACD_Signal"].shift(1)
        )
    )

    df["MACD_Bearish_Cross"] = (
        (
            df["MACD"]
            < df["MACD_Signal"]
        )
        &
        (
            df["MACD"].shift(1)
            >=
            df["MACD_Signal"].shift(1)
        )
    )

    # ======================================================
    # ADX / DI
    # ======================================================

    up_move = (
        df["High"]
        .diff()
    )

    down_move = (
        -df["Low"]
        .diff()
    )

    plus_dm = np.where(
        (
            (up_move > down_move)
            &
            (up_move > 0)
        ),
        up_move,
        0,
    )

    minus_dm = np.where(
        (
            (down_move > up_move)
            &
            (down_move > 0)
        ),
        down_move,
        0,
    )

    atr_for_adx = (
        df["True_Range"]
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False
        )
        .mean()
    )

    plus_di = (
        100
        * pd.Series(
            plus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False
        )
        .mean()
        / atr_for_adx
    )

    minus_di = (
        100
        * pd.Series(
            minus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False
        )
        .mean()
        / atr_for_adx
    )

    dx = (
        (
            plus_di
            - minus_di
        ).abs()
        /
        (
            plus_di
            + minus_di
        ).replace(
            0,
            np.nan
        )
    ) * 100

    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di

    df["ADX_14"] = (
        dx
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False
        )
        .mean()
    )

    # ======================================================
    # VOLUME
    # ======================================================

    df["Volume_SMA_20"] = (
        df["Volume"]
        .rolling(
            VOLUME_MA_PERIOD
        )
        .mean()
    )

    df["Volume_Ratio"] = (
        df["Volume"]
        /
        df["Volume_SMA_20"]
    )

    # ======================================================
    # ON BALANCE VOLUME - OBV
    # ======================================================

    price_direction = np.sign(
        df["Close"].diff()
    ).fillna(0)

    df["OBV"] = (
        price_direction
        * df["Volume"]
    ).cumsum()

    df["OBV_EMA_20"] = (
        df["OBV"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    # OBV trend
    df["OBV_Slope_10D"] = (
        df["OBV"]
        - df["OBV"].shift(10)
    )

    df["OBV_Bullish"] = (
        df["OBV"]
        > df["OBV_EMA_20"]
    )

    # ======================================================
    # ACCUMULATION / DISTRIBUTION LINE
    # ======================================================

    hl_range = (
        df["High"]
        - df["Low"]
    )

    money_flow_multiplier = (
        (
            (
                df["Close"]
                - df["Low"]
            )
            -
            (
                df["High"]
                - df["Close"]
            )
        )
        /
        hl_range.replace(
            0,
            np.nan
        )
    )

    money_flow_multiplier = (
        money_flow_multiplier
        .fillna(0)
    )

    money_flow_volume = (
        money_flow_multiplier
        * df["Volume"]
    )

    df["AD_LINE"] = (
        money_flow_volume
        .cumsum()
    )

    df["AD_Slope_20D"] = (
        df["AD_LINE"]
        - df["AD_LINE"].shift(20)
    )

    # ======================================================
    # CHAIKIN MONEY FLOW - CMF
    # ======================================================

    cmf_period = 20

    volume_sum = (
        df["Volume"]
        .rolling(cmf_period)
        .sum()
    )

    mfv_sum = (
        money_flow_volume
        .rolling(cmf_period)
        .sum()
    )

    df["CMF_20"] = (
        mfv_sum
        /
        volume_sum.replace(
            0,
            np.nan
        )
    )

    # ======================================================
    # MONEY FLOW INDEX - MFI
    # ======================================================

    typical_price = (
        df["High"]
        + df["Low"]
        + df["Close"]
    ) / 3

    raw_money_flow = (
        typical_price
        * df["Volume"]
    )

    tp_change = (
        typical_price.diff()
    )

    positive_flow = raw_money_flow.where(
        tp_change > 0,
        0
    )

    negative_flow = raw_money_flow.where(
        tp_change < 0,
        0
    ).abs()

    positive_sum = (
        positive_flow
        .rolling(14)
        .sum()
    )

    negative_sum = (
        negative_flow
        .rolling(14)
        .sum()
    )

    money_ratio = (
        positive_sum
        /
        negative_sum.replace(
            0,
            np.nan
        )
    )

    df["MFI_14"] = (
        100
        - (
            100
            /
            (1 + money_ratio)
        )
    )

    # ======================================================
    # RATE OF CHANGE - ROC
    # ======================================================

    df["ROC_5D"] = (
        df["Close"]
        .pct_change(5)
        * 100
    )

    df["ROC_20D"] = (
        df["Close"]
        .pct_change(20)
        * 100
    )

    df["ROC_60D"] = (
        df["Close"]
        .pct_change(60)
        * 100
    )

    # ======================================================
    # PRICE RETURNS
    # ======================================================

    df["Return_5D"] = (
        df["Close"]
        .pct_change(5)
        * 100
    )

    df["Return_20D"] = (
        df["Close"]
        .pct_change(20)
        * 100
    )

    df["Return_60D"] = (
        df["Close"]
        .pct_change(60)
        * 100
    )

    # ======================================================
    # 52-WEEK HIGH / LOW
    # ======================================================

    df["High_52W"] = (
        df["High"]
        .rolling(252)
        .max()
    )

    df["Low_52W"] = (
        df["Low"]
        .rolling(252)
        .min()
    )

    # Position inside 52-week range
    range_52w = (
        df["High_52W"]
        - df["Low_52W"]
    )

    df["Position_52W"] = (
        (
            df["Close"]
            - df["Low_52W"]
        )
        /
        range_52w.replace(
            0,
            np.nan
        )
    ) * 100

    # ======================================================
    # SUPPORT / RESISTANCE
    # ======================================================

    sr_period = (
        SUPPORT_RESISTANCE_PERIOD
    )

    df["Resistance_20"] = (
        df["High"]
        .rolling(sr_period)
        .max()
        .shift(1)
    )

    df["Support_20"] = (
        df["Low"]
        .rolling(sr_period)
        .min()
        .shift(1)
    )

    df["Resistance_50"] = (
        df["High"]
        .rolling(50)
        .max()
        .shift(1)
    )

    df["Support_50"] = (
        df["Low"]
        .rolling(50)
        .min()
        .shift(1)
    )

    # Distance from support
    df["Distance_From_Support_Pct"] = (
        (
            df["Close"]
            - df["Support_20"]
        )
        /
        df["Close"]
    ) * 100

    # Distance from resistance
    df["Distance_From_Resistance_Pct"] = (
        (
            df["Resistance_20"]
            - df["Close"]
        )
        /
        df["Close"]
    ) * 100

    # ======================================================
    # BREAKOUT DETECTION
    # ======================================================

    df["Breakout_20"] = (
        df["Close"]
        >
        df["Resistance_20"]
    )

    df["Breakdown_20"] = (
        df["Close"]
        <
        df["Support_20"]
    )

    # Breakout with volume confirmation
    df["Breakout_With_Volume"] = (
        df["Breakout_20"]
        &
        (
            df["Volume_Ratio"]
            >= 1.2
        )
    )

    # ======================================================
    # BOLLINGER BANDS
    # ======================================================

    bb_period = 20

    bb_middle = (
        df["Close"]
        .rolling(bb_period)
        .mean()
    )

    bb_std = (
        df["Close"]
        .rolling(bb_period)
        .std()
    )

    df["BB_MIDDLE"] = (
        bb_middle
    )

    df["BB_UPPER"] = (
        bb_middle
        + 2 * bb_std
    )

    df["BB_LOWER"] = (
        bb_middle
        - 2 * bb_std
    )

    bb_width = (
        df["BB_UPPER"]
        - df["BB_LOWER"]
    )

    df["BB_WIDTH_PCT"] = (
        bb_width
        /
        df["BB_MIDDLE"]
    ) * 100

    # Position inside Bollinger range
    df["BB_POSITION"] = (
        (
            df["Close"]
            - df["BB_LOWER"]
        )
        /
        (
            df["BB_UPPER"]
            - df["BB_LOWER"]
        ).replace(
            0,
            np.nan
        )
    ) * 100

    # ======================================================
    # EMA DISTANCE
    # ======================================================

    df["EMA20_Distance_Pct"] = (
        (
            df["Close"]
            - df["EMA_20"]
        )
        /
        df["EMA_20"]
    ) * 100

    df["EMA50_Distance_Pct"] = (
        (
            df["Close"]
            - df["EMA_50"]
        )
        /
        df["EMA_50"]
    ) * 100

    df["MA200_Distance_Pct"] = (
        (
            df["Close"]
            - df["MA_200"]
        )
        /
        df["MA_200"]
    ) * 100

    # ======================================================
    # SLOPES
    # ======================================================

    df["EMA50_Slope_10D"] = (
        df["EMA_50"]
        - df["EMA_50"].shift(10)
    )

    df["EMA20_Slope_5D"] = (
        df["EMA_20"]
        - df["EMA_20"].shift(5)
    )

    df["MA200_Slope_20D"] = (
        df["MA_200"]
        - df["MA_200"].shift(20)
    )

    df["ADX_Slope_5D"] = (
        df["ADX_14"]
        - df["ADX_14"].shift(5)
    )

    # ======================================================
    # PRICE ACTION
    # ======================================================

    body = (
        df["Close"]
        - df["Open"]
    )

    candle_range = (
        df["High"]
        - df["Low"]
    )

    upper_shadow = (
        df["High"]
        -
        df[["Open", "Close"]].max(
            axis=1
        )
    )

    lower_shadow = (
        df[["Open", "Close"]].min(
            axis=1
        )
        -
        df["Low"]
    )

    df["Candle_Body_Pct"] = (
        body.abs()
        /
        candle_range.replace(
            0,
            np.nan
        )
    ) * 100

    df["Upper_Shadow_Pct"] = (
        upper_shadow
        /
        candle_range.replace(
            0,
            np.nan
        )
    ) * 100

    df["Lower_Shadow_Pct"] = (
        lower_shadow
        /
        candle_range.replace(
            0,
            np.nan
        )
    ) * 100

    df["Bullish_Candle"] = (
        df["Close"]
        > df["Open"]
    )

    df["Bearish_Candle"] = (
        df["Close"]
        < df["Open"]
    )

    # ======================================================
    # CANDLE PATTERNS
    # ======================================================

    # Hammer
    df["Hammer"] = (
        (
            df["Lower_Shadow_Pct"]
            >= 50
        )
        &
        (
            df["Upper_Shadow_Pct"]
            <= 25
        )
        &
        (
            df["Candle_Body_Pct"]
            <= 40
        )
    )

    # Strong bullish candle
    df["Strong_Bullish_Candle"] = (
        (
            df["Close"]
            > df["Open"]
        )
        &
        (
            df["Candle_Body_Pct"]
            >= 60
        )
    )

    # ======================================================
    # BULLISH ENGULFING
    # ======================================================

    previous_open = (
        df["Open"].shift(1)
    )

    previous_close = (
        df["Close"].shift(1)
    )

    df["Bullish_Engulfing"] = (

        (
            previous_close
            < previous_open
        )

        &

        (
            df["Close"]
            > df["Open"]
        )

        &

        (
            df["Open"]
            <= previous_close
        )

        &

        (
            df["Close"]
            >= previous_open
        )
    )

    # ======================================================
    # SIMPLE TREND STATES
    # ======================================================

    df["Above_EMA20"] = (
        df["Close"]
        > df["EMA_20"]
    )

    df["Above_EMA50"] = (
        df["Close"]
        > df["EMA_50"]
    )

    df["Above_MA200"] = (
        df["Close"]
        > df["MA_200"]
    )

    df["EMA20_Above_EMA50"] = (
        df["EMA_20"]
        > df["EMA_50"]
    )

    df["DI_Bullish"] = (
        df["PLUS_DI"]
        > df["MINUS_DI"]
    )

    # ======================================================
    # COMPOSITE MOMENTUM FLAGS
    # ======================================================

    df["Momentum_Bullish"] = (

        (
            df["RSI_14"]
            > 50
        )

        &

        (
            df["MACD"]
            > df["MACD_Signal"]
        )

        &

        (
            df["ROC_20D"]
            > 0
        )
    )

    df["Momentum_Bearish"] = (

        (
            df["RSI_14"]
            < 50
        )

        &

        (
            df["MACD"]
            < df["MACD_Signal"]
        )

        &

        (
            df["ROC_20D"]
            < 0
        )
    )

    # ======================================================
    # MONEY FLOW COMPOSITE
    # ======================================================

    df["Money_Flow_Bullish"] = (

        (
            df["CMF_20"]
            > 0
        )

        &

        (
            df["OBV"]
            > df["OBV_EMA_20"]
        )

        &

        (
            df["AD_Slope_20D"]
            > 0
        )
    )

    df["Money_Flow_Bearish"] = (

        (
            df["CMF_20"]
            < 0
        )

        &

        (
            df["OBV"]
            < df["OBV_EMA_20"]
        )

        &

        (
            df["AD_Slope_20D"]
            < 0
        )
    )

    # ======================================================
    # CLEAN INF VALUES
    # ======================================================

    df.replace(
        [np.inf, -np.inf],
        np.nan,
        inplace=True
    )

    # ======================================================
    # RESTORE ATTRIBUTES
    # ======================================================

    df.attrs.update(
        attrs
    )

    return df


# ==========================================================
# Candlestick Analysis
# ==========================================================

def analyze_candlesticks(df):

    if df is None or df.empty:
        return []

    last = df.iloc[-1]

    reasons = []

    if bool(
        last.get(
            "Hammer",
            False
        )
    ):

        reasons.append(
            "ظهور شمعة Hammer"
        )

    if bool(
        last.get(
            "Bullish_Engulfing",
            False
        )
    ):

        reasons.append(
            "ظهور Bullish Engulfing"
        )

    if bool(
        last.get(
            "Strong_Bullish_Candle",
            False
        )
    ):

        reasons.append(
            "شمعة صاعدة قوية"
        )

    return reasons
