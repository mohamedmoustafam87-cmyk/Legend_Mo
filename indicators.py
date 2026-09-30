import pandas as pd
import numpy as np


# ==========================================================
# Technical Indicators
# ==========================================================

def calculate_indicators(df):

    if df is None or df.empty:
        return None

    if len(df) < 220:
        return None

    df = df.copy()

    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    for column in numeric_columns:

        if column not in df.columns:
            return None

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df.dropna(
        subset=numeric_columns,
        inplace=True
    )

    if len(df) < 220:
        return None

    df.sort_index(
        inplace=True
    )

    df["SMA_50"] = (
        df["Close"]
        .rolling(window=50)
        .mean()
    )

    df["SMA_200"] = (
        df["Close"]
        .rolling(window=200)
        .mean()
    )

    df["MA_200"] = df["SMA_200"]

    df["EMA_20"] = (
        df["Close"]
        .ewm(
            span=20,
            adjust=False,
            min_periods=20
        )
        .mean()
    )

    df["EMA_50"] = (
        df["Close"]
        .ewm(
            span=50,
            adjust=False,
            min_periods=50
        )
        .mean()
    )

    delta = df["Close"].diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = (
        gain
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    avg_loss = (
        loss
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    rs = (
        avg_gain /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    df["RSI_14"] = (
        100 -
        (
            100 /
            (1 + rs)
        )
    )

    df["RSI"] = df["RSI_14"]

    previous_close = (
        df["Close"]
        .shift(1)
    )

    tr1 = (
        df["High"] -
        df["Low"]
    )

    tr2 = (
        df["High"] -
        previous_close
    ).abs()

    tr3 = (
        df["Low"] -
        previous_close
    ).abs()

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(
        axis=1
    )

    df["TR"] = true_range

    df["ATR"] = (
        true_range
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        ema12 -
        ema26
    )

    df["MACD_signal"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_hist"] = (
        df["MACD"] -
        df["MACD_signal"]
    )

    up_move = (
        df["High"].diff()
    )

    down_move = (
        -df["Low"].diff()
    )

    plus_dm = pd.Series(
        np.where(
            (
                (up_move > down_move)
                &
                (up_move > 0)
            ),
            up_move,
            0.0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (
                (down_move > up_move)
                &
                (down_move > 0)
            ),
            down_move,
            0.0
        ),
        index=df.index
    )

    plus_dm_avg = (
        plus_dm
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    minus_dm_avg = (
        minus_dm
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    atr14 = df["ATR"]

    plus_di = (
        100 *
        plus_dm_avg /
        atr14.replace(
            0,
            np.nan
        )
    )

    minus_di = (
        100 *
        minus_dm_avg /
        atr14.replace(
            0,
            np.nan
        )
    )

    di_sum = (
        plus_di +
        minus_di
    )

    dx = (
        100 *
        (plus_di - minus_di).abs() /
        di_sum.replace(
            0,
            np.nan
        )
    )

    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di

    df["ADX"] = (
        dx
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    df["Vol_SMA20"] = (
        df["Volume"]
        .rolling(
            window=20
        )
        .mean()
    )

    df["Volume_Ratio"] = (
        df["Volume"] /
        df["Vol_SMA20"].replace(
            0,
            np.nan
        )
    )

    df["Resistance_20"] = (
        df["High"]
        .rolling(
            window=20
        )
        .max()
        .shift(1)
    )

    df["Support_20"] = (
        df["Low"]
        .rolling(
            window=20
        )
        .min()
        .shift(1)
    )

    bb_middle = (
        df["Close"]
        .rolling(
            window=20
        )
        .mean()
    )

    bb_std = (
        df["Close"]
        .rolling(
            window=20
        )
        .std()
    )

    df["BB_Middle"] = bb_middle

    df["BB_Upper"] = (
        bb_middle +
        (2 * bb_std)
    )

    df["BB_Lower"] = (
        bb_middle -
        (2 * bb_std)
    )

    df["EMA20_Distance_Pct"] = (
        (
            df["Close"] -
            df["EMA_20"]
        )
        /
        df["EMA_20"]
    ) * 100

    df["EMA50_Slope_10D"] = (
        (
            df["EMA_50"] -
            df["EMA_50"].shift(10)
        )
        /
        df["EMA_50"].shift(10)
    ) * 100

    df["MA200_Slope_20D"] = (
        (
            df["MA_200"] -
            df["MA_200"].shift(20)
        )
        /
        df["MA_200"].shift(20)
    ) * 100

    df.replace(
        [
            np.inf,
            -np.inf
        ],
        np.nan,
        inplace=True
    )

    return df


# ==========================================================
# Candlestick Analysis
# ==========================================================

def analyze_candlesticks(df):

    if df is None or len(df) < 3:
        return []

    reasons = []

    last = df.iloc[-1]
    prev = df.iloc[-2]

    body = abs(
        last["Close"] -
        last["Open"]
    )

    total_range = (
        last["High"] -
        last["Low"]
    )

    if total_range <= 0:
        return reasons

    lower_shadow = (
        min(
            last["Open"],
            last["Close"]
        )
        -
        last["Low"]
    )

    upper_shadow = (
        last["High"]
        -
        max(
            last["Open"],
            last["Close"]
        )
    )

    if (
        body > 0
        and lower_shadow >= 2 * body
        and upper_shadow <= body * 0.5
        and last["Close"] > last["Open"]
    ):
        reasons.append("🔨 شمعة Hammer إيجابية (دعم من القاع)")

    prev_red = (prev["Close"] < prev["Open"])
    current_green = (last["Close"] > last["Open"])

    if (
        prev_red
        and current_green
        and last["Open"] <= prev["Close"]
        and last["Close"] >= prev["Open"]
    ):
        reasons.append("🟢 Bullish Engulfing (سيطرة للمشترين)")

    if (
        body / total_range >= 0.70
        and current_green
    ):
        reasons.append("💪 شمعة صاعدة قوية ومتزنة")

    return reasons
