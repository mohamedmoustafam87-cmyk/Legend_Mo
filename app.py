import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from config import EGX_STOCKS

from scanner import (
    get_stock_data,
    fetch_mubasher_prices,
)

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy


# =====================================================================
# PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="EGX Smart Dashboard",
    page_icon="📈",
    layout="wide",
)


# =====================================================================
# CSS
# =====================================================================

st.markdown(
    """
    <style>

    .stMarkdown,
    .stAlert,
    h1, h2, h3, h4, h5, h6 {
        direction: rtl;
        text-align: right;
    }

    [data-testid="stMetric"] {
        direction: rtl;
        text-align: right;
    }

    .section-title {
        direction: rtl;
        text-align: right;
        font-size: 22px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    div[data-testid="stToggle"] {
        direction: rtl;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =====================================================================
# CONSTANTS
# =====================================================================

MIN_HISTORY_ROWS = 60

SR_WINDOW = 80

SWING_LEFT = 3
SWING_RIGHT = 3

ZONE_TOLERANCE = 0.012

ATR_ZONE_MULTIPLIER = 0.50


# =====================================================================
# HELPERS
# =====================================================================

def safe_float(value, default=np.nan):

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def fmt(
    value,
    decimals=2,
    suffix=""
):

    value = safe_float(value)

    if np.isnan(value):
        return "—"

    return (
        f"{value:,.{decimals}f}"
        f"{suffix}"
    )


def normalize_stock_list(stocks):

    if stocks is None:
        return []

    if isinstance(stocks, dict):
        return list(stocks.keys())

    if isinstance(
        stocks,
        (list, tuple, set)
    ):
        return list(stocks)

    if isinstance(
        stocks,
        pd.DataFrame
    ):

        for col in [
            "ticker",
            "symbol",
            "code",
            "Ticker",
            "Symbol",
        ]:

            if col in stocks.columns:

                return (
                    stocks[col]
                    .dropna()
                    .astype(str)
                    .tolist()
                )

    return []


def find_column(
    df,
    candidates
):

    normalized = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:

        key = (
            candidate
            .strip()
            .lower()
        )

        if key in normalized:
            return normalized[key]

    return None


# =====================================================================
# STANDARDIZE OHLCV
# =====================================================================

def standardize_ohlcv(df):

    if df is None or len(df) == 0:
        return pd.DataFrame()

    attrs = dict(
        getattr(
            df,
            "attrs",
            {}
        )
    )

    df = df.copy()

    aliases = {

        "Date": [
            "date",
            "datetime",
            "time",
            "التاريخ",
        ],

        "Open": [
            "open",
            "opening",
            "الفتح",
        ],

        "High": [
            "high",
            "الاعلى",
            "أعلى",
        ],

        "Low": [
            "low",
            "الادنى",
            "أدنى",
        ],

        "Close": [
            "close",
            "price",
            "last",
            "السعر",
            "الإغلاق",
        ],

        "Volume": [
            "volume",
            "vol",
            "الحجم",
            "حجم التداول",
        ],
    }

    rename_map = {}

    for std, candidates in aliases.items():

        col = find_column(
            df,
            [std] + candidates
        )

        if (
            col is not None
            and col != std
        ):

            rename_map[col] = std

    df = df.rename(
        columns=rename_map
    )

    if "Date" in df.columns:

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        df = (
            df
            .dropna(
                subset=["Date"]
            )
            .set_index("Date")
        )

    elif not isinstance(
        df.index,
        pd.DatetimeIndex
    ):

        try:

            df.index = pd.to_datetime(
                df.index
            )

        except Exception:
            pass

    for col in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    if "Close" not in df.columns:
        return pd.DataFrame()

    df = (
        df
        .dropna(
            subset=["Close"]
        )
        .sort_index()
    )

    df = df[
        ~df.index.duplicated(
            keep="last"
        )
    ]

    df.index.name = "Date"

    df.attrs.update(attrs)

    return df


# =====================================================================
# MARKET DATA VALIDATION
# =====================================================================

def validate_market_data(df):

    result = {
        "score": 100,
        "warnings": [],
    }

    if df is None or df.empty:

        return {
            "score": 0,
            "warnings": [
                "لا توجد بيانات."
            ],
        }

    if len(df) < MIN_HISTORY_ROWS:

        result["score"] -= 30

        result["warnings"].append(
            f"عدد الجلسات قليل: "
            f"{len(df)} جلسة."
        )

    elif len(df) < 200:

        result["warnings"].append(
            f"المتاح {len(df)} جلسة فقط، "
            f"فـ MA 200 غير مكتمل."
        )

    return result


# =====================================================================
# MARKET STRUCTURE
# =====================================================================

def detect_market_structure(df):

    if len(df) < 30:

        return {
            "trend": "غير كافٍ",
            "structure": "غير كافٍ",
        }

    close = df["Close"]

    ema20 = close.ewm(
        span=20,
        adjust=False
    ).mean()

    ema50 = close.ewm(
        span=50,
        adjust=False
    ).mean()

    last = close.iloc[-1]

    slope20 = (
        ema20.iloc[-1]
        - ema20.iloc[-6]
    )

    slope50 = (
        ema50.iloc[-1]
        - ema50.iloc[-6]
    )

    if (
        last > ema20.iloc[-1]
        > ema50.iloc[-1]
        and slope20 > 0
        and slope50 > 0
    ):

        trend = "صاعد"

    elif (
        last < ema20.iloc[-1]
        < ema50.iloc[-1]
        and slope20 < 0
        and slope50 < 0
    ):

        trend = "هابط"

    else:

        trend = "عرضي / انتقالي"

    return {
        "trend": trend,
        "structure": "تحليل هيكلي نشط",
    }


# =====================================================================
# SWING HIGH / LOW
# =====================================================================

def find_swing_points(
    df,
    left=SWING_LEFT,
    right=SWING_RIGHT,
    window=SR_WINDOW,
):

    data = df.tail(window).copy()

    if len(data) < (
        left + right + 5
    ):

        return [], []

    highs = []
    lows = []

    high_values = data["High"].values
    low_values = data["Low"].values

    for i in range(
        left,
        len(data) - right
    ):

        current_high = (
            high_values[i]
        )

        left_highs = high_values[
            i - left:i
        ]

        right_highs = high_values[
            i + 1:i + 1 + right
        ]

        if (
            current_high >= left_highs.max()
            and
            current_high >= right_highs.max()
        ):

            highs.append(
                (
                    float(current_high),
                    data.index[i],
                )
            )

        current_low = (
            low_values[i]
        )

        left_lows = low_values[
            i - left:i
        ]

        right_lows = low_values[
            i + 1:i + 1 + right
        ]

        if (
            current_low <= left_lows.min()
            and
            current_low <= right_lows.min()
        ):

            lows.append(
                (
                    float(current_low),
                    data.index[i],
                )
            )

    return lows, highs


# =====================================================================
# MERGE PRICE ZONES
# =====================================================================

def merge_price_levels(
    levels,
    tolerance=ZONE_TOLERANCE,
):

    if not levels:
        return []

    clean = sorted(
        [
            float(x)
            for x in levels
            if np.isfinite(x)
            and x > 0
        ]
    )

    if not clean:
        return []

    zones = []

    current = [
        clean[0]
    ]

    for price in clean[1:]:

        center = np.mean(
            current
        )

        if (
            abs(price - center)
            / center
            <= tolerance
        ):

            current.append(
                price
            )

        else:

            zones.append(
                (
                    min(current),
                    max(current),
                    np.mean(current),
                )
            )

            current = [
                price
            ]

    zones.append(
        (
            min(current),
            max(current),
            np.mean(current),
        )
    )

    return zones


# =====================================================================
# SUPPORT / RESISTANCE
# =====================================================================

def find_support_resistance(
    df,
    current_price=None,
):

    data = df.tail(
        SR_WINDOW
    ).copy()

    if data.empty:
        return [], []

    if current_price is None:

        current_price = safe_float(
            data["Close"].iloc[-1]
        )

    current_price = safe_float(
        current_price
    )

    if np.isnan(current_price):
        return [], []

    swing_lows, swing_highs = (
        find_swing_points(data)
    )

    support_candidates = []
    resistance_candidates = []

    # ---------------------------------------------------------------
    # Swing Levels
    # ---------------------------------------------------------------

    for level, _ in swing_lows:

        if level < current_price:

            support_candidates.append(
                level
            )

    for level, _ in swing_highs:

        if level > current_price:

            resistance_candidates.append(
                level
            )

    # ---------------------------------------------------------------
    # Rolling 20D / 50D
    # ---------------------------------------------------------------

    for period in [20, 50]:

        if len(data) >= period:

            low_level = (
                data["Low"]
                .tail(period)
                .min()
            )

            high_level = (
                data["High"]
                .tail(period)
                .max()
            )

            if low_level < current_price:

                support_candidates.append(
                    float(low_level)
                )

            if high_level > current_price:

                resistance_candidates.append(
                    float(high_level)
                )

    # ---------------------------------------------------------------
    # EMA20 / EMA50 / MA200 as dynamic levels
    # ---------------------------------------------------------------

    for col in [
        "EMA_20",
        "EMA_50",
        "MA_200",
    ]:

        if col not in data.columns:
            continue

        level = safe_float(
            data[col].iloc[-1]
        )

        if np.isnan(level):
            continue

        distance = (
            abs(level - current_price)
            / current_price
        )

        # only nearby dynamic levels
        if distance <= 0.04:

            if level < current_price:

                support_candidates.append(
                    level
                )

            elif level > current_price:

                resistance_candidates.append(
                    level
                )

    # ---------------------------------------------------------------
    # Merge Into Zones
    # ---------------------------------------------------------------

    support_zones = merge_price_levels(
        support_candidates
    )

    resistance_zones = merge_price_levels(
        resistance_candidates
    )

    # ---------------------------------------------------------------
    # Keep Nearest 3
    # ---------------------------------------------------------------

    support_zones = sorted(
        support_zones,
        key=lambda x:
            abs(current_price - x[2])
    )[:3]

    resistance_zones = sorted(
        resistance_zones,
        key=lambda x:
            abs(current_price - x[2])
    )[:3]

    return (
        support_zones,
        resistance_zones,
    )


# =====================================================================
# PREVIOUS DAY HIGH / LOW
# =====================================================================

def previous_day_levels(df):

    if len(df) < 2:

        return {}

    row = df.iloc[-2]

    return {

        "Previous High":
            safe_float(
                row.get("High")
            ),

        "Previous Low":
            safe_float(
                row.get("Low")
            ),

        "Previous Close":
            safe_float(
                row.get("Close")
            ),
    }


# =====================================================================
# 20D / 50D LEVELS
# =====================================================================

def rolling_levels(df):

    result = {}

    for period in [20, 50]:

        if len(df) < period:
            continue

        result[
            f"{period}D High"
        ] = float(
            df["High"]
            .tail(period)
            .max()
        )

        result[
            f"{period}D Low"
        ] = float(
            df["Low"]
            .tail(period)
            .min()
        )

    return result


# =====================================================================
# PIVOT POINTS
# =====================================================================

def calc_pivot_points(df):

    if len(df) < 2:
        return {}

    row = df.iloc[-2]

    high = safe_float(
        row.get("High")
    )

    low = safe_float(
        row.get("Low")
    )

    close = safe_float(
        row.get("Close")
    )

    if any(
        np.isnan(x)
        for x in [
            high,
            low,
            close,
        ]
    ):

        return {}

    pivot = (
        high + low + close
    ) / 3

    r1 = (
        2 * pivot
    ) - low

    s1 = (
        2 * pivot
    ) - high

    r2 = (
        pivot
        + (high - low)
    )

    s2 = (
        pivot
        - (high - low)
    )

    r3 = (
        high
        + 2 * (
            pivot - low
        )
    )

    s3 = (
        low
        - 2 * (
            high - pivot
        )
    )

    return {

        "Pivot":
            pivot,

        "R1":
            r1,

        "R2":
            r2,

        "R3":
            r3,

        "S1":
            s1,

        "S2":
            s2,

        "S3":
            s3,
    }


# =====================================================================
# FIBONACCI BASED ON LATEST SWING
# =====================================================================

def calc_fibonacci(
    df,
):

    data = df.tail(
        SR_WINDOW
    ).copy()

    swing_lows, swing_highs = (
        find_swing_points(data)
    )

    if not swing_lows or not swing_highs:

        return {}

    # آخر Swing Low و Swing High
    last_low = max(
        swing_lows,
        key=lambda x: x[1]
    )

    last_high = max(
        swing_highs,
        key=lambda x: x[1]
    )

    low_price = last_low[0]
    high_price = last_high[0]

    low_date = last_low[1]
    high_date = last_high[1]

    if (
        not np.isfinite(low_price)
        or not np.isfinite(high_price)
        or high_price <= low_price
    ):

        return {}

    diff = (
        high_price
        - low_price
    )

    # ---------------------------------------------------------------
    # Uptrend movement:
    # Low occurred before High
    # ---------------------------------------------------------------

    if low_date < high_date:

        return {

            "0.0%":
                high_price,

            "23.6%":
                high_price
                - diff * 0.236,

            "38.2%":
                high_price
                - diff * 0.382,

            "50.0%":
                high_price
                - diff * 0.500,

            "61.8%":
                high_price
                - diff * 0.618,

            "78.6%":
                high_price
                - diff * 0.786,

            "100.0%":
                low_price,
        }

    # ---------------------------------------------------------------
    # Downtrend movement
    # High occurred before Low
    # ---------------------------------------------------------------

    return {

        "0.0%":
            low_price,

        "23.6%":
            low_price
            + diff * 0.236,

        "38.2%":
            low_price
            + diff * 0.382,

        "50.0%":
            low_price
            + diff * 0.500,

        "61.8%":
            low_price
            + diff * 0.618,

        "78.6%":
            low_price
            + diff * 0.786,

        "100.0%":
            high_price,
    }


# =====================================================================
# ATR ZONES
# =====================================================================

def calc_atr_zones(
    df,
    current_price,
):

    if "ATR_14" not in df.columns:
        return {}

    atr = safe_float(
        df["ATR_14"].iloc[-1]
    )

    current_price = safe_float(
        current_price
    )

    if (
        np.isnan(atr)
        or np.isnan(current_price)
        or atr <= 0
    ):

        return {}

    buffer_value = (
        atr
        * ATR_ZONE_MULTIPLIER
    )

    return {

        "ATR Support Zone":
            (
                current_price - atr,
                current_price - buffer_value,
            ),

        "ATR Resistance Zone":
            (
                current_price + buffer_value,
                current_price + atr,
            ),
    }


# =====================================================================
# RISK SCORE
# =====================================================================

def calculate_risk_score(
    df,
    current_price,
):

    if df is None or df.empty:
        return 50

    current_price = safe_float(
        current_price
    )

    if np.isnan(current_price):
        return 50

    risk = 20

    # ---------------------------------------------------------------
    # ATR volatility
    # ---------------------------------------------------------------

    if "ATR_14" in df.columns:

        atr = safe_float(
            df["ATR_14"].iloc[-1]
        )

        if (
            not np.isnan(atr)
            and current_price > 0
        ):

            atr_pct = (
                atr
                / current_price
            ) * 100

            if atr_pct >= 6:
                risk += 25

            elif atr_pct >= 4:
                risk += 15

            elif atr_pct >= 2.5:
                risk += 8

    # ---------------------------------------------------------------
    # RSI
    # ---------------------------------------------------------------

    if "RSI_14" in df.columns:

        rsi = safe_float(
            df["RSI_14"].iloc[-1]
        )

        if not np.isnan(rsi):

            if (
                rsi >= 75
                or rsi <= 25
            ):

                risk += 15

            elif (
                rsi >= 70
                or rsi <= 30
            ):

                risk += 8

    # ---------------------------------------------------------------
    # Distance from MA200
    # ---------------------------------------------------------------

    if "MA_200" in df.columns:

        ma200 = safe_float(
            df["MA_200"].iloc[-1]
        )

        if (
            not np.isnan(ma200)
            and ma200 > 0
        ):

            distance = (
                abs(
                    current_price
                    - ma200
                )
                / ma200
            ) * 100

            if distance >= 15:
                risk += 15

            elif distance >= 10:
                risk += 10

            elif distance >= 5:
                risk += 5

    # ---------------------------------------------------------------
    # Volume
    # ---------------------------------------------------------------

    if "Volume_Ratio" in df.columns:

        vr = safe_float(
            df["Volume_Ratio"].iloc[-1]
        )

        if (
            not np.isnan(vr)
            and vr < 0.7
        ):

            risk += 5

    return int(
        max(
            0,
            min(
                100,
                risk
            )
        )
    )


def risk_label(score):

    if score >= 75:
        return "مخاطرة مرتفعة"

    if score >= 55:
        return "مخاطرة متوسطة إلى مرتفعة"

    if score >= 35:
        return "مخاطرة معتدلة"

    return "مخاطرة منخفضة"


# =====================================================================
# DATA LOADING
# =====================================================================

@st.cache_data(
    ttl=300,
    show_spinner=False
)
def load_mubasher():

    try:

        prices = (
            fetch_mubasher_prices()
        )

        return (
            prices
            if prices
            else {}
        )

    except Exception:

        return {}


@st.cache_data(
    ttl=300,
    show_spinner=False
)
def load_analysis(
    ticker,
    prices,
):

    try:

        result = get_stock_data(
            ticker,
            prices
        )

    except Exception:

        return None, None

    if result is None:
        return None, None

    if isinstance(
        result,
        tuple
    ):

        df, data_source = result

    else:

        df = result
        data_source = "Unknown"

    if (
        df is None
        or not isinstance(
            df,
            pd.DataFrame
        )
        or df.empty
    ):

        return None, None

    # ---------------------------------------------------------------
    # Save metadata before transformations
    # ---------------------------------------------------------------

    metadata = {

        "current_price":
            df.attrs.get(
                "current_price"
            ),

        "historical_close":
            df.attrs.get(
                "historical_close"
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
                "data_source",
                data_source
            ),
    }

    # ---------------------------------------------------------------
    # Standardize
    # ---------------------------------------------------------------

    df = standardize_ohlcv(
        df
    )

    if df.empty:
        return None, None

    # ---------------------------------------------------------------
    # Indicators
    # ---------------------------------------------------------------

    df = calculate_indicators(
        df
    )

    if df is None or df.empty:
        return None, None

    # ---------------------------------------------------------------
    # Restore metadata
    # ---------------------------------------------------------------

    df = standardize_ohlcv(
        df
    )

    if df.empty:
        return None, None

    for key, value in (
        metadata.items()
    ):

        df.attrs[key] = value

    # ---------------------------------------------------------------
    # Strategy
    # ---------------------------------------------------------------

    analysis = evaluate_stock_strategy(
        df,
        ticker
    )

    if analysis is not None:

        for key, value in (
            metadata.items()
        ):

            analysis[key] = value

    return (
        df,
        analysis
    )


# =====================================================================
# CHART BUILDER
# =====================================================================

def build_chart(
    data,
    ticker,
    opts,
    analysis,
    sr_data,
):

    has_volume = (
        opts["volume"]
        and "Volume" in data.columns
    )

    has_rsi = (
        opts["rsi"]
        and "RSI_14" in data.columns
    )

    rows = {
        "price": 1
    }

    heights = [
        0.60
    ]

    if has_volume:

        rows["volume"] = (
            len(rows) + 1
        )

        heights.append(
            0.20
        )

    if has_rsi:

        rows["rsi"] = (
            len(rows) + 1
        )

        heights.append(
            0.20
        )

    total = sum(
        heights
    )

    heights = [
        h / total
        for h in heights
    ]

    fig = make_subplots(
        rows=len(rows),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=heights,
    )

    # =================================================================
    # CANDLESTICK
    # =================================================================

    fig.add_trace(

        go.Candlestick(

            x=data.index,

            open=data["Open"],

            high=data["High"],

            low=data["Low"],

            close=data["Close"],

            name=ticker,

        ),

        row=1,
        col=1,
    )

    # =================================================================
    # EMA20
    # =================================================================

    if (
        opts["ema20"]
        and "EMA_20" in data.columns
    ):

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["EMA_20"],

                mode="lines",

                name="EMA 20",

                line=dict(
                    color="#FFA726",
                    width=1.6,
                ),

            ),

            row=1,
            col=1,
        )

    # =================================================================
    # EMA50
    # =================================================================

    if (
        opts["ema50"]
        and "EMA_50" in data.columns
    ):

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["EMA_50"],

                mode="lines",

                name="EMA 50",

                line=dict(
                    color="#AB47BC",
                    width=1.5,
                ),

            ),

            row=1,
            col=1,
        )

    # =================================================================
    # MA200
    # =================================================================

    if (
        opts["ma200"]
        and "MA_200" in data.columns
        and data["MA_200"].notna().any()
    ):

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["MA_200"],

                mode="lines",

                name="MA 200",

                line=dict(
                    color="#29B6F6",
                    width=1.8,
                ),

            ),

            row=1,
            col=1,
        )

    # =================================================================
    # BOLLINGER BANDS
    # =================================================================

    if (
        opts["bollinger"]
        and "BB_UPPER" in data.columns
    ):

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["BB_UPPER"],

                mode="lines",

                name="BB Upper",

                line=dict(
                    color="#90CAF9",
                    width=1,
                    dash="dot",
                ),

            ),

            row=1,
            col=1,
        )

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["BB_LOWER"],

                mode="lines",

                name="BB Lower",

                line=dict(
                    color="#90CAF9",
                    width=1,
                    dash="dot",
                ),

            ),

            row=1,
            col=1,
        )

    # =================================================================
    # CURRENT PRICE
    # =================================================================

    current_price = safe_float(
        data.attrs.get(
            "current_price"
        )
    )

    if not np.isnan(current_price):

        fig.add_hline(

            y=current_price,

            line_dash="dash",

            line_color="white",

            line_width=1.5,

            annotation_text=(
                f"السعر الحالي: "
                f"{current_price:,.2f}"
            ),

            annotation_position="top left",

            row=1,
            col=1,
        )

    # =================================================================
    # SUPPORT / RESISTANCE
    # =================================================================

    if opts["support_resistance"]:

        supports = sr_data.get(
            "supports",
            []
        )

        resistances = sr_data.get(
            "resistances",
            []
        )

        # -------------------------------------------------------------
        # Support Zones
        # -------------------------------------------------------------

        for idx, zone in enumerate(
            supports,
            start=1
        ):

            low, high, center = zone

            fig.add_hrect(

                y0=low,

                y1=high,

                fillcolor=(
                    "rgba(46,204,113,0.08)"
                ),

                line_width=0,

                annotation_text=(
                    f"S{idx} "
                    f"{center:,.2f}"
                ),

                annotation_position="bottom left",

                row=1,
                col=1,
            )

            fig.add_hline(

                y=center,

                line_dash="dot",

                line_color=(
                    "rgba(46,204,113,0.75)"
                ),

                line_width=1,

                annotation_text=(
                    f"S{idx}: "
                    f"{center:,.2f}"
                ),

                annotation_position="bottom right",

                row=1,
                col=1,
            )

        # -------------------------------------------------------------
        # Resistance Zones
        # -------------------------------------------------------------

        for idx, zone in enumerate(
            resistances,
            start=1
        ):

            low, high, center = zone

            fig.add_hrect(

                y0=low,

                y1=high,

                fillcolor=(
                    "rgba(239,83,80,0.08)"
                ),

                line_width=0,

                annotation_text=(
                    f"R{idx} "
                    f"{center:,.2f}"
                ),

                annotation_position="top left",

                row=1,
                col=1,
            )

            fig.add_hline(

                y=center,

                line_dash="dot",

                line_color=(
                    "rgba(239,83,80,0.75)"
                ),

                line_width=1,

                annotation_text=(
                    f"R{idx}: "
                    f"{center:,.2f}"
                ),

                annotation_position="top right",

                row=1,
                col=1,
            )

    # =================================================================
    # SWING HIGH / LOW
    # =================================================================

    if opts["swing"]:

        swing_lows, swing_highs = (
            find_swing_points(
                data
            )
        )

        for level, date in (
            swing_lows
        ):

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=(
                    "rgba(0,200,83,0.45)"
                ),

                line_width=1,

                annotation_text=(
                    f"Swing Low "
                    f"{level:,.2f}"
                ),

                annotation_position="bottom left",

                row=1,
                col=1,
            )

        for level, date in (
            swing_highs
        ):

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=(
                    "rgba(255,82,82,0.45)"
                ),

                line_width=1,

                annotation_text=(
                    f"Swing High "
                    f"{level:,.2f}"
                ),

                annotation_position="top left",

                row=1,
                col=1,
            )

    # =================================================================
    # 20D / 50D LEVELS
    # =================================================================

    if opts["rolling_levels"]:

        levels = rolling_levels(
            data
        )

        for name, level in (
            levels.items()
        ):

            if np.isnan(
                safe_float(level)
            ):

                continue

            if "High" in name:

                color = (
                    "rgba(255,152,0,0.70)"
                )

                position = "top right"

            else:

                color = (
                    "rgba(3,169,244,0.70)"
                )

                position = "bottom right"

            fig.add_hline(

                y=level,

                line_dash="dashdot",

                line_color=color,

                line_width=1,

                annotation_text=(
                    f"{name}: "
                    f"{level:,.2f}"
                ),

                annotation_position=position,

                row=1,
                col=1,
            )

    # =================================================================
    # PREVIOUS DAY
    # =================================================================

    if opts["previous_day"]:

        previous = (
            previous_day_levels(
                data
            )
        )

        for name, level in (
            previous.items()
        ):

            if np.isnan(
                safe_float(level)
            ):

                continue

            if "High" in name:

                color = (
                    "rgba(255,82,82,0.65)"
                )

            elif "Low" in name:

                color = (
                    "rgba(76,175,80,0.65)"
                )

            else:

                color = (
                    "rgba(255,193,7,0.65)"
                )

            fig.add_hline(

                y=level,

                line_dash="longdash",

                line_color=color,

                line_width=1,

                annotation_text=(
                    f"{name}: "
                    f"{level:,.2f}"
                ),

                annotation_position="bottom left",

                row=1,
                col=1,
            )

    # =================================================================
    # PIVOT POINTS
    # =================================================================

    if opts["pivot"]:

        pivots = (
            calc_pivot_points(
                data
            )
        )

        for name, level in (
            pivots.items()
        ):

            if name == "Pivot":

                color = "#FFD54F"

            elif name.startswith("R"):

                color = (
                    "rgba(239,83,80,0.85)"
                )

            else:

                color = (
                    "rgba(38,166,154,0.85)"
                )

            fig.add_hline(

                y=level,

                line_dash="dash",

                line_color=color,

                line_width=1,

                annotation_text=(
                    f"{name}: "
                    f"{level:,.2f}"
                ),

                annotation_position="top right",

                row=1,
                col=1,
            )

    # =================================================================
    # FIBONACCI
    # =================================================================

    if opts["fibonacci"]:

        fibs = calc_fibonacci(
            data
        )

        fib_colors = {

            "0.0%": "#FFFFFF",

            "23.6%": "#CE93D8",

            "38.2%": "#FFD54F",

            "50.0%": "#FFFFFF",

            "61.8%": "#FFB74D",

            "78.6%": "#64B5F6",

            "100.0%": "#FFFFFF",
        }

        for ratio, level in (
            fibs.items()
        ):

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=(
                    fib_colors.get(
                        ratio,
                        "white"
                    )
                ),

                line_width=1,

                annotation_text=(
                    f"Fib {ratio}: "
                    f"{level:,.2f}"
                ),

                annotation_position="top left",

                row=1,
                col=1,
            )

    # =================================================================
    # ATR ZONES
    # =================================================================

    if opts["atr_zones"]:

        atr_zones = calc_atr_zones(
            data,
            current_price
        )

        support_zone = atr_zones.get(
            "ATR Support Zone"
        )

        resistance_zone = atr_zones.get(
            "ATR Resistance Zone"
        )

        if support_zone:

            fig.add_hrect(

                y0=support_zone[0],

                y1=support_zone[1],

                fillcolor=(
                    "rgba(38,166,154,0.10)"
                ),

                line_width=0,

                annotation_text="ATR Support Zone",

                annotation_position="bottom right",

                row=1,
                col=1,
            )

        if resistance_zone:

            fig.add_hrect(

                y0=resistance_zone[0],

                y1=resistance_zone[1],

                fillcolor=(
                    "rgba(239,83,80,0.10)"
                ),

                line_width=0,

                annotation_text="ATR Resistance Zone",

                annotation_position="top right",

                row=1,
                col=1,
            )

    # =================================================================
    # VOLUME
    # =================================================================

    if has_volume:

        colors = [

            "#26A69A"
            if close >= open_
            else "#EF5350"

            for open_, close
            in zip(
                data["Open"],
                data["Close"]
            )

        ]

        fig.add_trace(

            go.Bar(

                x=data.index,

                y=data["Volume"],

                marker_color=colors,

                name="الحجم",

                showlegend=False,

            ),

            row=rows["volume"],
            col=1,
        )

    # =================================================================
    # RSI
    # =================================================================

    if has_rsi:

        fig.add_trace(

            go.Scatter(

                x=data.index,

                y=data["RSI_14"],

                mode="lines",

                name="RSI 14",

                line=dict(
                    color="#AB47BC",
                    width=1.6,
                ),

            ),

            row=rows["rsi"],
            col=1,
        )

        fig.add_hline(

            y=70,

            line_dash="dash",

            line_color="red",

            row=rows["rsi"],

            col=1,
        )

        fig.add_hline(

            y=30,

            line_dash="dash",

            line_color="green",

            row=rows["rsi"],

            col=1,
        )

    # =================================================================
    # LAYOUT
    # =================================================================

    fig.update_layout(

        template="plotly_dark",

        height=600
        + 150 * (
            len(rows) - 1
        ),

        xaxis_rangeslider_visible=False,

        hovermode="x unified",

        legend=dict(

            orientation="h",

            yanchor="bottom",

            y=1.02,

            xanchor="left",

            x=0,

        ),

        margin=dict(

            l=10,

            r=10,

            t=60,

            b=10,

        ),
    )

    return fig


# =====================================================================
# MAIN INTERFACE
# =====================================================================

st.title(
    "📈 لوحة تحليل الأسهم المصرية "
    "(EGX Smart Dashboard)"
)

st.markdown(
    "موقعك الاحترافي المتقدم لمتابعة "
    "الشموع اليابانية، المؤشرات الفنية، "
    "الدعم والمقاومة وأدوات القياس."
)


# =====================================================================
# STOCK SELECTOR
# =====================================================================

stocks = normalize_stock_list(
    EGX_STOCKS
)

if not stocks:

    st.error(
        "لم يتم العثور على EGX_STOCKS "
        "في config.py"
    )

    st.stop()


col_s1, col_s2, col_s3 = st.columns(
    [3, 1, 1]
)

with col_s1:

    selected_ticker = st.selectbox(
        "🔎 اختر أو ابحث عن السهم:",
        stocks,
        index=0,
    )

with col_s2:

    history_days = st.selectbox(
        "عدد الجلسات",
        [
            60,
            120,
            200,
            365,
            500,
        ],
        index=1,
    )

with col_s3:

    if st.button(
        "🔄 تحديث البيانات",
        use_container_width=True,
    ):

        st.cache_data.clear()

        st.rerun()


# =====================================================================
# LOAD DATA
# =====================================================================

st.markdown("---")

mubasher_prices = load_mubasher()

with st.spinner(
    f"جاري جلب وتحليل بيانات "
    f"{selected_ticker}..."
):

    try:

        df, analysis = load_analysis(
            selected_ticker,
            mubasher_prices
        )

    except Exception as e:

        st.error(
            f"⚠️ حدث خطأ أثناء تحليل "
            f"{selected_ticker}: {e}"
        )

        st.stop()


if df is None or df.empty:

    st.error(
        f"⚠️ تعذر جلب بيانات كافية "
        f"للسهم {selected_ticker}"
    )

    st.stop()


# =====================================================================
# CURRENT DATA
# =====================================================================

historical_close = safe_float(
    df.attrs.get(
        "historical_close"
    )
)

current_price = safe_float(
    df.attrs.get(
        "current_price"
    )
)

price_source = df.attrs.get(
    "price_source",
    "غير محدد"
)

is_realtime = df.attrs.get(
    "is_realtime",
    False
)

current_vs_close_pct = safe_float(
    df.attrs.get(
        "current_vs_close_pct"
    )
)

if np.isnan(
    historical_close
):

    historical_close = safe_float(
        df["Close"].iloc[-1]
    )

if np.isnan(
    current_price
):

    current_price = (
        historical_close
    )


last = df.iloc[-1]

rsi = safe_float(
    last.get("RSI_14")
)

volume_ratio = safe_float(
    last.get("Volume_Ratio")
)

risk_score = calculate_risk_score(
    df,
    current_price
)

structure_data = (
    detect_market_structure(
        df
    )
)

supports, resistances = (
    find_support_resistance(
        df,
        current_price
    )
)


# =====================================================================
# DATA SOURCE STATUS
# =====================================================================

if is_realtime:

    st.success(
        f"📡 السعر الحالي: "
        f"{fmt(current_price, 2)} ج.م — "
        f"المصدر: {price_source}"
    )

else:

    st.warning(
        f"⚠️ Mubasher غير متاح — "
        f"يتم استخدام آخر إغلاق Yahoo: "
        f"{fmt(current_price, 2)} ج.م"
    )


# =====================================================================
# TOP METRICS
# =====================================================================

c1, c2, c3, c4, c5, c6 = (
    st.columns(6)
)

with c1:

    st.metric(
        "السعر الحالي",
        fmt(
            current_price,
            2,
            " ج.م"
        ),

        (
            f"{current_vs_close_pct:+.2f}%"
            if not np.isnan(
                current_vs_close_pct
            )
            else None
        ),
    )


with c2:

    st.metric(
        "آخر إغلاق Yahoo",
        fmt(
            historical_close,
            2,
            " ج.م"
        ),
    )


with c3:

    if analysis:

        st.metric(
            "التقييم (Score)",
            f"{analysis.get('score', '—')} / 100",
            analysis.get(
                "rec",
                ""
            ),
            delta_color="off",
        )

    else:

        st.metric(
            "التقييم (Score)",
            "—"
        )


with c4:

    st.metric(
        "مؤشر RSI",
        fmt(
            rsi,
            1
        ),
    )


with c5:

    if analysis:

        st.metric(
            "الدعم الاستراتيجي",
            fmt(
                analysis.get(
                    "support"
                ),
                2,
                " ج.م"
            ),
        )

    else:

        st.metric(
            "الدعم الاستراتيجي",
            "—"
        )


with c6:

    st.metric(
        "درجة المخاطرة",
        f"{risk_score}/100",
        risk_label(
            risk_score
        ),
        delta_color="off",
    )


# =====================================================================
# MARKET STRUCTURE
# =====================================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">'
    '📐 هيكل السوق'
    '</div>',
    unsafe_allow_html=True
)

m1, m2, m3 = st.columns(3)

with m1:

    st.info(
        f"**الاتجاه الحالي:** "
        f"{structure_data['trend']}"
    )

with m2:

    st.info(
        f"**RSI:** "
        f"{fmt(rsi, 1)}"
    )

with m3:

    st.info(
        f"**Volume Ratio:** "
        f"{fmt(volume_ratio, 2)}"
    )


# =====================================================================
# ANALYSIS TOOLS
# =====================================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">'
    '🎛️ أدوات القياس والتحليل على الشارت'
    '</div>',
    unsafe_allow_html=True
)

st.caption(
    "يمكنك تشغيل أكثر من أداة في نفس الوقت."
)


# ---------------------------------------------------------------------
# PRICE LEVEL TOOLS
# ---------------------------------------------------------------------

st.markdown(
    "**📍 مستويات السعر**"
)

t1, t2, t3, t4 = st.columns(4)

with t1:

    show_sr = st.toggle(
        "الدعم والمقاومة",
        value=True,
    )

with t2:

    show_swing = st.toggle(
        "Swing High / Low",
        value=False,
    )

with t3:

    show_rolling = st.toggle(
        "20D / 50D High-Low",
        value=False,
    )

with t4:

    show_previous = st.toggle(
        "Previous High / Low",
        value=False,
    )


# ---------------------------------------------------------------------
# MEASUREMENT TOOLS
# ---------------------------------------------------------------------

st.markdown(
    "**📏 أدوات القياس**"
)

t5, t6, t7 = st.columns(3)

with t5:

    show_fibonacci = st.toggle(
        "Fibonacci",
        value=False,
    )

with t6:

    show_pivot = st.toggle(
        "Pivot Points",
        value=False,
    )

with t7:

    show_atr_zones = st.toggle(
        "ATR Zones",
        value=False,
    )


# ---------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------

st.markdown(
    "**📊 المؤشرات الفنية**"
)

i1, i2, i3, i4 = st.columns(4)

with i1:

    show_ema20 = st.toggle(
        "EMA 20",
        value=True,
    )

with i2:

    show_ema50 = st.toggle(
        "EMA 50",
        value=False,
    )

with i3:

    show_ma200 = st.toggle(
        "MA 200",
        value=True,
    )

with i4:

    show_bollinger = st.toggle(
        "Bollinger Bands",
        value=False,
    )


i5, i6 = st.columns(2)

with i5:

    show_volume = st.toggle(
        "حجم التداول",
        value=True,
    )

with i6:

    show_rsi = st.toggle(
        "RSI 14",
        value=True,
    )


# =====================================================================
# OPTIONS DICT
# =====================================================================

opts = {

    "support_resistance":
        show_sr,

    "swing":
        show_swing,

    "rolling_levels":
        show_rolling,

    "previous_day":
        show_previous,

    "fibonacci":
        show_fibonacci,

    "pivot":
        show_pivot,

    "atr_zones":
        show_atr_zones,

    "ema20":
        show_ema20,

    "ema50":
        show_ema50,

    "ma200":
        show_ma200,

    "bollinger":
        show_bollinger,

    "volume":
        show_volume,

    "rsi":
        show_rsi,
}


# =====================================================================
# CHART
# =====================================================================

st.markdown("---")

chart_df = (
    df
    .tail(history_days)
    .copy()
)

chart_df.attrs.update(
    df.attrs
)

sr_data = {

    "supports":
        supports,

    "resistances":
        resistances,
}


fig = build_chart(

    chart_df,

    selected_ticker,

    opts,

    analysis,

    sr_data,
)


st.plotly_chart(
    fig,
    use_container_width=True,
)


# =====================================================================
# LEVEL TABLE
# =====================================================================

if show_sr:

    st.markdown("---")

    st.subheader(
        "📊 أقرب مناطق الدعم والمقاومة"
    )

    level_rows = []

    for i, zone in enumerate(
        supports,
        start=1
    ):

        low, high, center = zone

        level_rows.append({

            "النوع":
                f"Support {i}",

            "من":
                round(low, 2),

            "إلى":
                round(high, 2),

            "المتوسط":
                round(center, 2),

            "المسافة من السعر %":
                round(
                    (
                        (
                            current_price
                            - center
                        )
                        / current_price
                    ) * 100,
                    2,
                ),
        })


    for i, zone in enumerate(
        resistances,
        start=1
    ):

        low, high, center = zone

        level_rows.append({

            "النوع":
                f"Resistance {i}",

            "من":
                round(low, 2),

            "إلى":
                round(high, 2),

            "المتوسط":
                round(center, 2),

            "المسافة من السعر %":
                round(
                    (
                        (
                            center
                            - current_price
                        )
                        / current_price
                    ) * 100,
                    2,
                ),
        })


    if level_rows:

        st.dataframe(
            pd.DataFrame(
                level_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "لم يتم العثور على مستويات "
            "قريبة وموثوقة من السعر الحالي."
        )


# =====================================================================
# RECOMMENDATIONS + RISK MANAGEMENT
# =====================================================================

if analysis:

    st.markdown("---")

    col_a, col_b = st.columns(2)

    # -----------------------------------------------------------------
    # TARGETS
    # -----------------------------------------------------------------

    with col_a:

        st.subheader(
            "🎯 التوصيات والأهداف"
        )

        st.info(
            f"**منطقة الدخول المقترحة:** "
            f"{analysis.get('ideal_entry', '—')}"
            f" - "
            f"{analysis.get('entry_high', '—')}"
            f" ج.م"
        )

        st.success(
            f"**الهدف الأول TP1:** "
            f"{analysis.get('tp1', '—')} "
            f"ج.م "
            f"({analysis.get('days_tp1_text', '—')})"
        )

        st.success(
            f"**الهدف الثاني TP2:** "
            f"{analysis.get('tp2', '—')} "
            f"ج.م "
            f"({analysis.get('days_tp2_text', '—')})"
        )

    # -----------------------------------------------------------------
    # RISK
    # -----------------------------------------------------------------

    with col_b:

        st.subheader(
            "🛑 إدارة المخاطر والخروج"
        )

        st.warning(
            f"**وقف الخسارة:** "
            f"{analysis.get('stop_loss', '—')} "
            f"ج.م "
            f"({fmt(analysis.get('stop_loss_pct'), 2, '%')})"
        )

        st.error(
            f"**خطة الخروج:** "
            f"{analysis.get('exit_strategy', '—')}"
        )


    # -----------------------------------------------------------------
    # REASONS
    # -----------------------------------------------------------------

    st.subheader(
        "💡 الأسباب والتحليل الفني"
    )

    reasons = analysis.get(
        "reasons",
        []
    )

    if reasons:

        for reason in reasons:

            st.write(
                f"- {reason}"
            )

    else:

        st.info(
            "لا توجد أسباب إضافية."
        )


# =====================================================================
# DATA QUALITY
# =====================================================================

st.markdown("---")

validation = validate_market_data(
    df
)

if validation["warnings"]:

    for warning in (
        validation["warnings"]
    ):

        st.warning(
            warning
        )


# =====================================================================
# DATA SOURCE FOOTER
# =====================================================================

st.markdown("---")

source_text = (
    "Mubasher Current + Yahoo Historical"
    if is_realtime
    else
    "Yahoo Historical + Yahoo Last Close"
)

st.caption(
    f"📡 مصدر السعر الحالي: {price_source} | "
    f"📊 مصدر البيانات التاريخية: Yahoo Finance | "
    f"🔎 Data Source: {source_text}"
)

st.caption(
    "⚠️ أدوات التحليل الفني تعتمد على البيانات "
    "التاريخية ولا تمثل ضمانًا لحركة السعر المستقبلية."
)
