import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from config import EGX_STOCKS
from scanner import get_stock_data, fetch_mubasher_prices
from indicators import calculate_indicators
from strategy import evaluate_stock_strategy


# =====================================================================
# PAGE CONFIG + CSS
# =====================================================================

st.set_page_config(
    page_title="EGX Smart Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stMarkdown, .stAlert, h1, h2, h3, h4, h5, h6 {
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
    </style>
    """,
    unsafe_allow_html=True,
)


# =====================================================================
# CONSTANTS
# =====================================================================

MIN_HISTORY_ROWS = 60
STALE_DAYS = 7

SR_WINDOW = 80

SUPPORT_TOLERANCE = 0.015
RESISTANCE_TOLERANCE = 0.015

EGX_HOLIDAYS = (
    getattr(config, "EGX_HOLIDAYS", None)
    or getattr(config, "HOLIDAYS", None)
    or []
)


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

    except (TypeError, ValueError):
        return default


def fmt(x, decimals=2, suffix=""):
    value = safe_float(x)

    if np.isnan(value):
        return "—"

    return f"{value:,.{decimals}f}{suffix}"


def normalize_stock_list(stocks):

    if stocks is None:
        return []

    if isinstance(stocks, dict):
        return list(stocks.keys())

    if isinstance(stocks, (list, tuple, set)):
        return list(stocks)

    if isinstance(stocks, pd.DataFrame):

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


def find_column(df, candidates):

    normalized = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:

        key = candidate.strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def standardize_ohlcv(df):
    """
    توحيد أسماء أعمدة OHLCV.
    يحافظ على التاريخ كـ DatetimeIndex.
    """

    if df is None or len(df) == 0:
        return pd.DataFrame()

    # حفظ metadata
    attrs = dict(getattr(df, "attrs", {}))

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

        if col is not None and col != std:
            rename_map[col] = std

    df = df.rename(
        columns=rename_map
    )

    # -------------------------------------------------------------
    # DATE
    # -------------------------------------------------------------

    if "Date" in df.columns:

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        df = (
            df
            .dropna(subset=["Date"])
            .set_index("Date")
        )

    elif (
        not isinstance(
            df.index,
            pd.DatetimeIndex
        )
        and not pd.api.types.is_numeric_dtype(
            df.index
        )
    ):

        try:
            df.index = pd.to_datetime(
                df.index
            )

        except Exception:
            pass

    # -------------------------------------------------------------
    # NUMERIC
    # -------------------------------------------------------------

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
        .dropna(subset=["Close"])
        .sort_index()
    )

    df = df[
        ~df.index.duplicated(
            keep="last"
        )
    ]

    df.index.name = "Date"

    # إعادة metadata
    df.attrs.update(attrs)

    return df


# =====================================================================
# DATA QUALITY
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
            f"فمتوسط MA 200 غير مكتمل."
        )

    # -------------------------------------------------------------
    # DATA AGE
    # -------------------------------------------------------------

    if isinstance(
        df.index,
        pd.DatetimeIndex
    ):

        last_date = df.index.max()

        if pd.notna(last_date):

            age_days = (
                pd.Timestamp.now().normalize()
                - last_date.normalize()
            ).days

            if age_days > STALE_DAYS:

                result["score"] -= 35

                result["warnings"].append(
                    f"البيانات قديمة. "
                    f"آخر جلسة: "
                    f"{last_date.date()}"
                )

    # -------------------------------------------------------------
    # VOLUME
    # -------------------------------------------------------------

    if "Volume" in df.columns:

        zero_share = (
            df["Volume"]
            .fillna(0)
            .le(0)
            .mean()
        )

        if zero_share > 0.2:

            result["score"] -= 5

            result["warnings"].append(
                f"{zero_share:.0%} "
                f"من الجلسات بلا حجم تداول."
            )

    result["score"] = max(
        0,
        min(
            100,
            result["score"]
        )
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
        and ema20.iloc[-1] > ema50.iloc[-1]
        and slope20 > 0
        and slope50 > 0
    ):

        trend = "صاعد"

    elif (
        last < ema20.iloc[-1]
        and ema20.iloc[-1] < ema50.iloc[-1]
        and slope20 < 0
        and slope50 < 0
    ):

        trend = "هابط"

    else:

        trend = "عرضي / انتقالي"

    recent = df.tail(30)

    highs = (
        recent["High"]
        if "High" in recent.columns
        else recent["Close"]
    )

    lows = (
        recent["Low"]
        if "Low" in recent.columns
        else recent["Close"]
    )

    h1 = highs.iloc[:15].max()
    h2 = highs.iloc[15:].max()

    l1 = lows.iloc[:15].min()
    l2 = lows.iloc[15:].min()

    if h2 > h1 and l2 > l1:

        structure = (
            "Higher High / Higher Low"
        )

    elif h2 < h1 and l2 < l1:

        structure = (
            "Lower High / Lower Low"
        )

    else:

        structure = "Mixed Structure"

    return {
        "trend": trend,
        "structure": structure,
    }


# =====================================================================
# SUPPORT / RESISTANCE
# =====================================================================

def _cluster_levels(
    levels,
    tolerance
):

    clusters = []

    for level in sorted(levels):

        if (
            clusters
            and abs(
                level
                - np.mean(clusters[-1])
            )
            / max(
                np.mean(clusters[-1]),
                1e-9
            )
            <= tolerance
        ):

            clusters[-1].append(
                level
            )

        else:

            clusters.append(
                [level]
            )

    return [
        (
            round(
                float(np.mean(c)),
                2
            ),
            len(c)
        )
        for c in clusters
    ]


def find_support_resistance(
    df,
    window=SR_WINDOW
):

    data = df.tail(window)

    close = data["Close"]

    lows = (
        data["Low"]
        if "Low" in data.columns
        else close
    )

    highs = (
        data["High"]
        if "High" in data.columns
        else close
    )

    supports = []
    resistances = []

    for i in range(
        2,
        len(data) - 2
    ):

        if (
            lows.iloc[i]
            <= lows.iloc[i - 2:i].min()
            and
            lows.iloc[i]
            <= lows.iloc[i + 1:i + 3].min()
        ):

            supports.append(
                float(lows.iloc[i])
            )

        if (
            highs.iloc[i]
            >= highs.iloc[i - 2:i].max()
            and
            highs.iloc[i]
            >= highs.iloc[i + 1:i + 3].max()
        ):

            resistances.append(
                float(highs.iloc[i])
            )

    price = float(
        close.iloc[-1]
    )

    sup = _cluster_levels(
        [
            x
            for x in supports
            if x < price
        ],
        SUPPORT_TOLERANCE
    )

    res = _cluster_levels(
        [
            x
            for x in resistances
            if x > price
        ],
        RESISTANCE_TOLERANCE
    )

    sup = sorted(
        sup,
        key=lambda x: x[0],
        reverse=True
    )[:5]

    res = sorted(
        res,
        key=lambda x: x[0]
    )[:5]

    return sup, res


# =====================================================================
# FIBONACCI
# =====================================================================

def calc_fibonacci(data):

    high_val = data["High"].max()
    low_val = data["Low"].min()

    diff = (
        high_val
        - low_val
    )

    if (
        not np.isfinite(diff)
        or diff <= 0
    ):

        return {}

    uptrend = (
        data["Low"].values.argmin()
        <
        data["High"].values.argmax()
    )

    if uptrend:

        return {
            ratio: (
                high_val
                - diff * ratio
            )
            for ratio in (
                0.382,
                0.5,
                0.618,
                0.786,
            )
        }

    return {
        ratio: (
            low_val
            + diff * ratio
        )
        for ratio in (
            0.382,
            0.5,
            0.618,
            0.786,
        )
    }


# =====================================================================
# RISK SCORE
# =====================================================================

def calculate_risk_score(df):

    if df.empty:
        return 100

    close = df["Close"]

    vol = (
        close
        .pct_change()
        .rolling(20)
        .std()
        .iloc[-1]
    )

    atr = (
        safe_float(
            df["ATR14"].iloc[-1]
        )
        if "ATR14" in df.columns
        else np.nan
    )

    price = safe_float(
        close.iloc[-1]
    )

    risk = 40

    if not np.isnan(vol):

        annualized = (
            vol
            * np.sqrt(252)
            * 100
        )

        if annualized > 80:

            risk += 30

        elif annualized > 50:

            risk += 20

        elif annualized > 30:

            risk += 10

        else:

            risk -= 5

    if (
        not np.isnan(atr)
        and price > 0
    ):

        atr_pct = (
            atr
            / price
            * 100
        )

        if atr_pct > 8:

            risk += 20

        elif atr_pct > 5:

            risk += 10

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

    if score >= 70:
        return "مخاطرة عالية"

    if score >= 45:
        return "مخاطرة متوسطة"

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
    prices
):
    """
    تحميل بيانات Yahoo التاريخية
    + السعر الحالي من Mubasher.

    مهم:
    سعر Mubasher لا يدخل في حساب المؤشرات.
    """

    result = get_stock_data(
        ticker,
        prices
    )

    if not result:
        return None, None

    df, data_source = result

    if df is None or df.empty:
        return None, None

    # -------------------------------------------------------------
    # حفظ بيانات السعر الحالي
    # -------------------------------------------------------------

    current_price = df.attrs.get(
        "current_price"
    )

    historical_close = df.attrs.get(
        "historical_close"
    )

    price_source = df.attrs.get(
        "price_source"
    )

    is_realtime = df.attrs.get(
        "is_realtime",
        False
    )

    current_vs_close_pct = df.attrs.get(
        "current_vs_close_pct"
    )

    # -------------------------------------------------------------
    # STANDARDIZE
    # -------------------------------------------------------------

    df = standardize_ohlcv(df)

    if df.empty:
        return None, None

    # -------------------------------------------------------------
    # INDICATORS
    # -------------------------------------------------------------

    df = calculate_indicators(df)

    if df is None or df.empty:
        return None, None

    df = standardize_ohlcv(df)

    if df.empty:
        return None, None

    # -------------------------------------------------------------
    # RESTORE METADATA
    # -------------------------------------------------------------

    df.attrs["current_price"] = (
        current_price
    )

    df.attrs["historical_close"] = (
        historical_close
    )

    df.attrs["price_source"] = (
        price_source
    )

    df.attrs["is_realtime"] = (
        is_realtime
    )

    df.attrs["current_vs_close_pct"] = (
        current_vs_close_pct
    )

    df.attrs["data_source"] = (
        data_source
    )

    # -------------------------------------------------------------
    # STRATEGY
    # -------------------------------------------------------------

    analysis = evaluate_stock_strategy(
        df,
        ticker
    )

    # -------------------------------------------------------------
    # ADD CURRENT PRICE METADATA
    # -------------------------------------------------------------

    if analysis is not None:

        analysis["current_price"] = (
            current_price
        )

        analysis["historical_close"] = (
            historical_close
        )

        analysis["price_source"] = (
            price_source
        )

        analysis["is_realtime"] = (
            is_realtime
        )

        analysis["current_vs_close_pct"] = (
            current_vs_close_pct
        )

        analysis["data_source"] = (
            data_source
        )

    return df, analysis


# =====================================================================
# CHART BUILDER
# =====================================================================

def build_chart(
    data,
    ticker,
    opts,
    analysis,
    supports,
    resistances
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

    heights = [0.6]

    if has_volume:

        rows["volume"] = len(rows) + 1
        heights.append(0.2)

    if has_rsi:

        rows["rsi"] = len(rows) + 1
        heights.append(0.2)

    total = sum(heights)

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

    # -------------------------------------------------------------
    # CANDLESTICK
    # -------------------------------------------------------------

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

    # -------------------------------------------------------------
    # EMA 20
    # -------------------------------------------------------------

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
                    width=1.6
                ),
            ),

            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # EMA 50
    # -------------------------------------------------------------

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
                    color="#66BB6A",
                    width=1.6
                ),
            ),

            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # MA 200
    # -------------------------------------------------------------

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
                    width=1.8
                ),
            ),

            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # CURRENT PRICE
    # -------------------------------------------------------------

    current_price = safe_float(
        data.attrs.get(
            "current_price"
        )
    )

    if not np.isnan(current_price):

        fig.add_hline(

            y=current_price,

            line_dash="dash",

            line_color="#FFFFFF",

            annotation_text=(
                f"السعر الحالي: "
                f"{current_price:,.2f}"
            ),

            annotation_position="top left",

            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # SUPPORT / RESISTANCE
    # -------------------------------------------------------------

    if opts["support"]:

        main_support = (
            safe_float(
                analysis.get("support")
            )
            if analysis
            else np.nan
        )

        if not np.isnan(main_support):

            fig.add_hline(

                y=main_support,

                line_dash="dash",

                line_color="green",

                annotation_text=(
                    f"الدعم الرئيسي: "
                    f"{main_support:,.2f}"
                ),

                annotation_position=(
                    "bottom right"
                ),

                row=1,
                col=1,
            )

        for level, touches in supports:

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=(
                    "rgba(46,204,113,0.55)"
                ),

                annotation_text=(
                    f"S {level:,.2f} "
                    f"({touches})"
                ),

                annotation_position=(
                    "bottom left"
                ),

                row=1,
                col=1,
            )

        for level, touches in resistances:

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=(
                    "rgba(239,83,80,0.55)"
                ),

                annotation_text=(
                    f"R {level:,.2f} "
                    f"({touches})"
                ),

                annotation_position=(
                    "top left"
                ),

                row=1,
                col=1,
            )

    # -------------------------------------------------------------
    # FIBONACCI
    # -------------------------------------------------------------

    if opts["fib"]:

        fib_colors = {
            0.382: "gold",
            0.5: "white",
            0.618: "orange",
            0.786: "tomato",
        }

        for ratio, level in (
            calc_fibonacci(data).items()
        ):

            fig.add_hline(

                y=level,

                line_dash="dot",

                line_color=fib_colors[
                    ratio
                ],

                annotation_text=(
                    f"Fib {ratio * 100:.1f}%"
                ),

                annotation_position=(
                    "top right"
                ),

                row=1,
                col=1,
            )

    # -------------------------------------------------------------
    # VOLUME
    # -------------------------------------------------------------

    if has_volume:

        colors = [
            "#26A69A"
            if c >= o
            else "#EF5350"

            for o, c
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

        fig.update_yaxes(
            title_text="الحجم",
            row=rows["volume"],
            col=1,
        )

    # -------------------------------------------------------------
    # RSI
    # -------------------------------------------------------------

    if has_rsi:

        fig.add_trace(

            go.Scatter(
                x=data.index,
                y=data["RSI_14"],
                mode="lines",
                name="RSI 14",
                line=dict(
                    color="#AB47BC",
                    width=1.6
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

        fig.update_yaxes(
            title_text="RSI",
            range=[0, 100],
            row=rows["rsi"],
            col=1,
        )

    # -------------------------------------------------------------
    # X AXIS / HOLIDAYS
    # -------------------------------------------------------------

    if isinstance(
        data.index,
        pd.DatetimeIndex
    ):

        breaks = [
            dict(
                bounds=["fri", "sat"]
            )
        ]

        if EGX_HOLIDAYS:

            try:

                breaks.append(
                    dict(
                        values=[
                            str(
                                pd.to_datetime(h).date()
                            )
                            for h in EGX_HOLIDAYS
                        ]
                    )
                )

            except Exception:
                pass

        fig.update_xaxes(
            rangebreaks=breaks
        )

    # -------------------------------------------------------------
    # LAYOUT
    # -------------------------------------------------------------

    fig.update_yaxes(
        title_text="السعر (ج.م)",
        row=1,
        col=1
    )

    fig.update_layout(

        template="plotly_dark",

        height=(
            550
            + 150 * (len(rows) - 1)
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
            t=50,
            b=10,
        ),
    )

    return fig


# =====================================================================
# SIDEBAR
# =====================================================================

st.sidebar.title(
    "📊 EGX Smart Dashboard"
)

stocks = normalize_stock_list(
    EGX_STOCKS
)

if not stocks:

    st.error(
        "لم يتم العثور على EGX_STOCKS في config.py"
    )

    st.stop()

selected_ticker = st.sidebar.selectbox(
    "🔎 اختر أو ابحث عن السهم",
    stocks,
    index=0
)

history_days = st.sidebar.slider(
    "عدد الجلسات المعروضة",
    60,
    500,
    120,
    10
)

if st.sidebar.button(
    "🔄 تحديث البيانات"
):

    st.cache_data.clear()
    st.rerun()


# =====================================================================
# HEADER
# =====================================================================

st.title(
    f"📈 {selected_ticker} — EGX Smart Dashboard"
)

st.caption(
    "تحليل فني متعدد العوامل "
    "مع فحص جودة البيانات"
)


# =====================================================================
# LOAD DATA
# =====================================================================

mubasher_prices = load_mubasher()

if not mubasher_prices:

    st.warning(
        "⚠️ تعذر جلب السعر الحالي من مباشر، "
        "سيتم الاعتماد على آخر إغلاق Yahoo."
    )


with st.spinner(
    f"جاري جلب وتحليل بيانات "
    f"السهم {selected_ticker}..."
):

    try:

        df, analysis = load_analysis(
            selected_ticker,
            mubasher_prices
        )

    except Exception as e:

        st.error(
            f"⚠️ حدث خطأ أثناء تحليل "
            f"السهم {selected_ticker}: {e}"
        )

        st.stop()


if df is None or df.empty:

    st.error(
        f"⚠️ تعذر جلب بيانات كافية "
        f"للسهم {selected_ticker}"
    )

    st.stop()


# =====================================================================
# REQUIRED COLUMNS
# =====================================================================

missing = [
    c
    for c in [
        "Open",
        "High",
        "Low",
        "Close",
    ]
    if c not in df.columns
]

if missing:

    st.error(
        "⚠️ أعمدة ناقصة في البيانات: "
        + ", ".join(missing)
    )

    st.stop()


# =====================================================================
# PRICE METADATA
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

if np.isnan(historical_close):

    historical_close = safe_float(
        df["Close"].iloc[-1]
    )

if np.isnan(current_price):

    current_price = historical_close


# =====================================================================
# DATA QUALITY
# =====================================================================

quality = validate_market_data(
    df
)

q = quality["score"]

if q >= 80:

    st.success(
        f"🟢 جودة البيانات: {q}/100"
    )

elif q >= 60:

    st.warning(
        f"🟠 جودة البيانات: {q}/100"
    )

else:

    st.error(
        f"🔴 جودة البيانات منخفضة: "
        f"{q}/100 — "
        f"التوصيات قد لا تكون موثوقة"
    )

if quality["warnings"]:

    with st.expander(
        "تفاصيل جودة البيانات"
    ):

        for warning in quality["warnings"]:

            st.write(
                f"• {warning}"
            )


if analysis is None:

    st.warning(
        "⚠️ لا توجد بيانات كافية "
        "لتشغيل محرك الاستراتيجية "
        "على هذا السهم."
    )


# =====================================================================
# DAILY CHANGE
# =====================================================================

if not np.isnan(
    current_vs_close_pct
):

    daily_change = (
        current_vs_close_pct
    )

else:

    prev_close = (
        safe_float(
            df["Close"].iloc[-2]
        )
        if len(df) >= 2
        else np.nan
    )

    daily_change = (

        (
            current_price
            - prev_close
        )
        / prev_close
        * 100

        if (
            not np.isnan(prev_close)
            and prev_close != 0
        )

        else np.nan
    )


# =====================================================================
# TECHNICAL DATA
# =====================================================================

last = df.iloc[-1]

last_close = safe_float(
    last["Close"]
)

rsi = safe_float(
    last.get("RSI_14")
)

# indicators.py يستخدم Volume_Ratio
volume_ratio = safe_float(
    last.get(
        "Volume_Ratio"
    )
)

# توافق مع أي نسخة قديمة
if np.isnan(volume_ratio):

    volume_ratio = safe_float(
        last.get(
            "VolumeRatio"
        )
    )

risk_score = calculate_risk_score(
    df
)

structure_data = detect_market_structure(
    df
)

supports, resistances = (
    find_support_resistance(df)
)


# =====================================================================
# PRICE SOURCE STATUS
# =====================================================================

if is_realtime:

    st.success(
        f"📡 السعر الحالي من Mubasher: "
        f"**{current_price:,.2f} ج.م**"
    )

else:

    st.warning(
        f"📡 Mubasher غير متاح — "
        f"تم استخدام آخر إغلاق Yahoo: "
        f"**{current_price:,.2f} ج.م**"
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
            f"{daily_change:+.2f}%"
            if not np.isnan(
                daily_change
            )
            else None
        )
    )


with c2:

    st.metric(
        "آخر إغلاق Yahoo",
        fmt(
            historical_close,
            2,
            " ج.م"
        )
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
            delta_color="off"
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
        )
    )


with c5:

    st.metric(
        "الدعم الرئيسي",
        fmt(
            analysis.get(
                "support"
            )
            if analysis
            else None,
            2,
            " ج.م"
        )
    )


with c6:

    st.metric(
        "درجة المخاطرة",
        f"{risk_score}/100",
        risk_label(
            risk_score
        ),
        delta_color="off"
    )


st.markdown("---")


# =====================================================================
# MARKET STRUCTURE
# =====================================================================

st.markdown(
    '<div class="section-title">'
    '📐 هيكل السوق'
    '</div>',
    unsafe_allow_html=True
)

m1, m2, m3 = st.columns(3)

with m1:

    st.info(
        f"الاتجاه الحالي: "
        f"**{structure_data['trend']}**"
    )

with m2:

    st.info(
        f"الهيكل السعري: "
        f"**{structure_data['structure']}**"
    )

with m3:

    st.info(
        f"نسبة الحجم للمتوسط: "
        f"**{fmt(volume_ratio, 2, 'x')}**"
    )


st.markdown("---")


# =====================================================================
# CHART CONTROLS
# =====================================================================

st.markdown(
    '<div class="section-title">'
    '⚙️ تخصيص وعرض أدوات الشارت'
    '</div>',
    unsafe_allow_html=True
)

(
    opt_col1,
    opt_col2,
    opt_col3,
    opt_col4,
    opt_col5,
    opt_col6,
    opt_col7,
) = st.columns(7)

opts = {}

with opt_col1:

    opts["ema20"] = st.checkbox(
        "EMA 20",
        value=True
    )

with opt_col2:

    opts["ema50"] = st.checkbox(
        "EMA 50",
        value=False
    )

with opt_col3:

    opts["ma200"] = st.checkbox(
        "MA 200",
        value=True
    )

with opt_col4:

    opts["support"] = st.checkbox(
        "الدعم والمقاومة",
        value=True
    )

with opt_col5:

    opts["fib"] = st.checkbox(
        "فيبوناتشي",
        value=False
    )

with opt_col6:

    opts["volume"] = st.checkbox(
        "حجم التداول",
        value=True
    )

with opt_col7:

    opts["rsi"] = st.checkbox(
        "مؤشر RSI",
        value=True
    )


# =====================================================================
# CHART
# =====================================================================

chart_df = df.tail(
    history_days
).copy()

# الحفاظ على metadata
chart_df.attrs.update(
    df.attrs
)

fig = build_chart(
    chart_df,
    selected_ticker,
    opts,
    analysis,
    supports,
    resistances
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# =====================================================================
# RECOMMENDATIONS + RISK MANAGEMENT
# =====================================================================

if analysis:

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:

        st.subheader(
            "🎯 التوصيات والأهداف الاستثمارية"
        )

        st.info(
            f"**منطقة الدخول المقترحة:** "
            f"{analysis.get('ideal_entry', '—')} "
            f"- "
            f"{analysis.get('entry_high', '—')} "
            f"ج.م"
        )

        st.success(
            f"**الهدف الأول (TP1):** "
            f"{analysis.get('tp1', '—')} ج.م "
            f"(المدة: "
            f"{analysis.get('days_tp1_text', '—')})"
        )

        st.success(
            f"**الهدف الثاني (TP2):** "
            f"{analysis.get('tp2', '—')} ج.م "
            f"(المدة: "
            f"{analysis.get('days_tp2_text', '—')})"
        )

    with col_b:

        st.subheader(
            "🛑 إدارة المخاطر والخروج"
        )

        st.warning(
            f"**وقف الخسارة (Stop Loss):** "
            f"{analysis.get('stop_loss', '—')} "
            f"ج.م "
            f"({fmt(analysis.get('stop_loss_pct'), 2, '%')})"
        )

        st.error(
            f"**خطة الخروج:** "
            f"{analysis.get('exit_strategy', '—')}"
        )

    st.subheader(
        "💡 الأسباب والتحليل الفني التفصيلي:"
    )

    for reason in analysis.get(
        "reasons",
        []
    ):

        st.write(
            f"- {reason}"
        )


# =====================================================================
# SUPPORT / RESISTANCE TABLE
# =====================================================================

st.markdown(
    '<div class="section-title">'
    '🎯 مستويات الدعم والمقاومة'
    '</div>',
    unsafe_allow_html=True
)

s_col, r_col = st.columns(2)

with s_col:

    st.subheader(
        "🟢 الدعوم"
    )

    if supports:

        for level, touches in supports:

            if current_price != 0:

                dist = (
                    (
                        current_price
                        - level
                    )
                    / current_price
                    * 100
                )

            else:

                dist = np.nan

            st.write(
                f"**{level:,.2f}** "
                f"— المسافة "
                f"{dist:.1f}% "
                f"— لمسات: {touches}"
            )

    else:

        st.write(
            "لا توجد مستويات دعم كافية."
        )


with r_col:

    st.subheader(
        "🔴 المقاومات"
    )

    if resistances:

        for level, touches in resistances:

            if current_price != 0:

                dist = (
                    (
                        level
                        - current_price
                    )
                    / current_price
                    * 100
                )

            else:

                dist = np.nan

            st.write(
                f"**{level:,.2f}** "
                f"— المسافة "
                f"{dist:.1f}% "
                f"— لمسات: {touches}"
            )

    else:

        st.write(
            "لا توجد مستويات مقاومة كافية."
        )


# =====================================================================
# SCENARIOS
# =====================================================================

st.markdown(
    '<div class="section-title">'
    '🔮 السيناريوهات الفنية'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    "### 🟢 السيناريو الإيجابي"
)

if resistances:

    nxt = (
        f" ثم المقاومة التالية "
        f"**{resistances[1][0]:,.2f}**"
        if len(resistances) > 1
        else ""
    )

    st.write(
        f"اختراق المقاومة الأقرب "
        f"**{resistances[0][0]:,.2f}** "
        f"بإغلاق واضح والثبات فوقها، "
        f"تتم مراقبة"
        f"{nxt or ' المستويات الأعلى'}."
    )

else:

    st.write(
        "لا توجد مقاومة آلية كافية."
    )


st.markdown(
    "### 🔴 السيناريو السلبي"
)

if supports:

    st.write(
        f"كسر الدعم الأقرب "
        f"**{supports[0][0]:,.2f}** "
        f"بإغلاق واضح يستدعي "
        f"إعادة تقييم الاتجاه."
    )

else:

    st.write(
        "لا يوجد دعم آلي كافٍ."
    )


# =====================================================================
# INDICATORS TABLE
# =====================================================================

st.markdown(
    '<div class="section-title">'
    '📌 المؤشرات الفنية'
    '</div>',
    unsafe_allow_html=True
)

indicator_rows = [

    (
        "السعر الحالي",
        current_price,
        2
    ),

    (
        "آخر إغلاق Yahoo",
        historical_close,
        2
    ),

    (
        "EMA 20",
        last.get("EMA_20"),
        2
    ),

    (
        "EMA 50",
        last.get("EMA_50"),
        2
    ),

    (
        "MA 200",
        last.get("MA_200"),
        2
    ),

    (
        "RSI 14",
        rsi,
        1
    ),

    (
        "MACD",
        last.get("MACD"),
        4
    ),

    (
        "MACD Signal",
        last.get("MACD_Signal"),
        4
    ),

    (
        "ATR 14",
        last.get("ATR14"),
        3
    ),

    (
        "نسبة الحجم",
        volume_ratio,
        2
    ),

    (
        "عائد 5 جلسات %",
        last.get("Return_5D"),
        2
    ),

    (
        "عائد 20 جلسة %",
        last.get("Return_20D"),
        2
    ),
]

st.dataframe(

    pd.DataFrame({

        "المؤشر": [
            r[0]
            for r in indicator_rows
        ],

        "القيمة": [
            fmt(
                r[1],
                r[2]
            )
            for r in indicator_rows
        ],

    }),

    use_container_width=True,

    hide_index=True,
)


# =====================================================================
# HISTORICAL DATA
# =====================================================================

with st.expander(
    "📋 عرض البيانات التاريخية"
):

    cols = [

        c

        for c in [

            "Open",
            "High",
            "Low",
            "Close",
            "Volume",

            "EMA_20",
            "EMA_50",
            "MA_200",

            "RSI_14",

            "MACD",
            "MACD_Signal",

            "ATR14",

            "Volume_Ratio",

        ]

        if c in df.columns

    ]

    st.dataframe(

        df[
            cols
        ]
        .tail(100)
        .sort_index(
            ascending=False
        ),

        use_container_width=True,
    )


# =====================================================================
# DISCLAIMER
# =====================================================================

st.markdown("---")

st.caption(
    "⚠️ هذه اللوحة أداة مساعدة للتحليل الفني فقط، "
    "وما تعرضه من توصيات وأهداف ليس نصيحة استثمارية. "
    "النتائج تعتمد على جودة البيانات ولا تضمن حركة السعر المستقبلية."
)
