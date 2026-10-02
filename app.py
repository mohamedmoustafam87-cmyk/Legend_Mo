# ============================================================
# legend-Mo LENS
# EGX Technical Intelligence Dashboard
# Premium Black Edition
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ------------------------------------------------------------
# PROJECT IMPORTS
# ------------------------------------------------------------
from scanner import (
    fetch_mubasher_prices,
    get_stock_data,
)

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="legend-Mo LENS",
    page_icon="🖤",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PREMIUM BLACK CSS
# ============================================================

st.markdown(
    """
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 15% 10%, rgba(255,255,255,0.035), transparent 25%),
        radial-gradient(circle at 85% 20%, rgba(0,255,170,0.025), transparent 25%),
        #050607;
    color: #F5F7FA;
}

/* Main container */
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1600px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #080A0C;
    border-right: 1px solid #181C21;
}

section[data-testid="stSidebar"] * {
    color: #E8EBEF;
}

/* Headers */
h1, h2, h3, h4 {
    color: #F7F8FA !important;
}

/* Cards */
.lm-card {
    background: linear-gradient(
        145deg,
        #0C0F12 0%,
        #090B0E 100%
    );
    border: 1px solid #1B2026;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
    box-shadow:
        0 8px 30px rgba(0,0,0,0.28),
        inset 0 1px 0 rgba(255,255,255,0.015);
}

.lm-card:hover {
    border-color: #292F36;
}

/* Brand */
.brand {
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -1px;
}

.brand span {
    color: #FFFFFF;
}

.brand-sub {
    color: #737B86;
    font-size: 12px;
    letter-spacing: 2px;
    margin-top: -4px;
}

/* Small label */
.label {
    color: #727A84;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.3px;
    font-weight: 600;
}

/* Big value */
.big-value {
    color: #FFFFFF;
    font-size: 34px;
    font-weight: 800;
    line-height: 1;
    margin-top: 8px;
}

/* Metric */
.metric-value {
    color: #F5F7FA;
    font-size: 21px;
    font-weight: 700;
    margin-top: 5px;
}

.metric-sub {
    color: #6F7781;
    font-size: 11px;
}

/* Status */
.green {
    color: #00E676 !important;
}

.red {
    color: #FF4D5A !important;
}

.yellow {
    color: #FFC857 !important;
}

.blue {
    color: #55A7FF !important;
}

.gray {
    color: #8A929D !important;
}

/* Score */
.score-number {
    font-size: 62px;
    font-weight: 800;
    line-height: 0.9;
}

.score-label {
    color: #858D98;
    font-size: 11px;
    letter-spacing: 2px;
}

/* Progress */
.progress-bg {
    width: 100%;
    height: 7px;
    background: #171B20;
    border-radius: 20px;
    overflow: hidden;
    margin-top: 8px;
}

.progress-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(
        90deg,
        #FFFFFF,
        #777F89
    );
}

/* Scenario */
.scenario {
    background: #0A0D10;
    border: 1px solid #1A1F25;
    border-radius: 12px;
    padding: 13px;
}

.scenario-title {
    color: #818995;
    font-size: 10px;
    letter-spacing: 1px;
}

.scenario-value {
    font-size: 25px;
    font-weight: 800;
    margin-top: 5px;
}

/* Signal */
.signal-box {
    padding: 15px;
    border-radius: 12px;
    background: #0B0E11;
    border: 1px solid #1B2026;
}

.signal-title {
    color: #777F89;
    font-size: 10px;
    letter-spacing: 1px;
}

.signal-value {
    font-size: 18px;
    font-weight: 700;
    margin-top: 5px;
}

/* Divider */
.divider {
    height: 1px;
    background: #181C21;
    margin: 15px 0;
}

/* Footer */
.footer {
    text-align: center;
    color: #454C55;
    font-size: 10px;
    padding: 25px 0 10px 0;
    letter-spacing: 1px;
}

/* Streamlit buttons */
.stButton > button {
    background: #0D1013;
    color: #DDE1E6;
    border: 1px solid #242A31;
    border-radius: 10px;
}

.stButton > button:hover {
    border-color: #666F7A;
    color: white;
}

/* Selectbox */
div[data-baseweb="select"] > div {
    background: #0C0F12;
    border-color: #242A31;
}

/* Toggle */
.stToggle label {
    color: #B7BDC5 !important;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return default


def fmt(value, digits=2):
    value = safe_float(value)
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}"


def pct(value, digits=2):
    value = safe_float(value)
    if pd.isna(value):
        return "—"
    return f"{value:.{digits}f}%"


def clamp(value, low=0, high=100):
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return low


def score_color(score):
    score = safe_float(score, 0)

    if score >= 70:
        return "green"
    elif score >= 50:
        return "yellow"
    return "red"


def score_text(score):
    score = safe_float(score, 0)

    if score >= 80:
        return "Very Strong"
    if score >= 70:
        return "Strong"
    if score >= 60:
        return "Positive"
    if score >= 50:
        return "Neutral"
    return "Weak"


def normalize_score(value, maximum):
    value = safe_float(value, 0)
    if maximum <= 0:
        return 0
    return clamp(value / maximum * 100)


# ============================================================
# DATA PREPARATION
# ============================================================

def standardize_ohlcv(df):

    if df is None or df.empty:
        return None

    data = df.copy()

    # Flatten MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [
            c[0] if isinstance(c, tuple) else c
            for c in data.columns
        ]

    rename = {}

    for c in data.columns:
        lc = str(c).lower()

        if lc == "open":
            rename[c] = "Open"
        elif lc == "high":
            rename[c] = "High"
        elif lc == "low":
            rename[c] = "Low"
        elif lc == "close":
            rename[c] = "Close"
        elif lc in ["volume", "vol"]:
            rename[c] = "Volume"

    data = data.rename(columns=rename)

    required = ["Open", "High", "Low", "Close", "Volume"]

    for col in required:
        if col not in data.columns:
            return None

    data = data[required].copy()

    for col in required:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce"
        )

    data = data.dropna()

    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)

    data = data.sort_index()

    return data


# ============================================================
# SCENARIO ENGINE
# ============================================================

def calculate_scenarios(analysis):

    score = clamp(analysis.get("score", 50))

    trend = normalize_score(
        analysis.get("trend_score", 0), 20
    )

    momentum = normalize_score(
        analysis.get("momentum_score", 0), 15
    )

    volume = normalize_score(
        analysis.get("volume_score", 0), 15
    )

    money = normalize_score(
        analysis.get("money_flow_score", 0), 10
    )

    # Transparent heuristic model.
    # These are model scenario estimates, NOT calibrated probabilities.

    bullish = (
        score * 0.45 +
        trend * 0.20 +
        momentum * 0.25 +
        volume * 0.05 +
        money * 0.05
    )

    bearish = (
        (100 - score) * 0.45 +
        (100 - trend) * 0.20 +
        (100 - momentum) * 0.25 +
        (100 - volume) * 0.05 +
        (100 - money) * 0.05
    )

    sideways = (
        100 -
        abs(bullish - bearish)
    )

    bullish = max(1, bullish)
    bearish = max(1, bearish)
    sideways = max(1, sideways)

    total = bullish + bearish + sideways

    return {
        "Bullish": bullish / total * 100,
        "Sideways": sideways / total * 100,
        "Bearish": bearish / total * 100,
    }


# ============================================================
# SELLING PRESSURE
# ============================================================

def calculate_selling_pressure(df):

    if df is None or df.empty:
        return 50

    row = df.iloc[-1]

    pressure = 0
    checks = 0

    rsi = safe_float(row.get("RSI14"))
    mfi = safe_float(row.get("MFI14"))
    cmf = safe_float(row.get("CMF20"))
    obv_bull = row.get("OBV_Bullish")
    di_plus = safe_float(row.get("DI_PLUS"))
    di_minus = safe_float(row.get("DI_MINUS"))
    roc20 = safe_float(row.get("ROC20"))

    if not pd.isna(rsi):
        checks += 1
        if rsi >= 70:
            pressure += 100
        elif rsi >= 60:
            pressure += 55
        elif rsi <= 40:
            pressure += 15
        else:
            pressure += 35

    if not pd.isna(mfi):
        checks += 1
        if mfi >= 80:
            pressure += 100
        elif mfi >= 65:
            pressure += 60
        elif mfi <= 35:
            pressure += 15
        else:
            pressure += 35

    if not pd.isna(cmf):
        checks += 1
        if cmf < -0.10:
            pressure += 90
        elif cmf < 0:
            pressure += 60
        else:
            pressure += 20

    if obv_bull is not None:
        checks += 1
        pressure += 20 if bool(obv_bull) else 75

    if not pd.isna(di_plus) and not pd.isna(di_minus):
        checks += 1
        pressure += 75 if di_minus > di_plus else 20

    if not pd.isna(roc20):
        checks += 1
        pressure += 75 if roc20 < 0 else 20

    if checks == 0:
        return 50

    return clamp(pressure / checks)


# ============================================================
# TREND DESCRIPTION
# ============================================================

def trend_description(df):

    if df is None or df.empty:
        return "Unknown"

    row = df.iloc[-1]
    price = safe_float(row.get("Close"))

    ema20 = safe_float(row.get("EMA20"))
    ema50 = safe_float(row.get("EMA50"))
    ma200 = safe_float(row.get("MA200"))

    bullish = 0
    bearish = 0

    if not pd.isna(price) and not pd.isna(ema20):
        bullish += price > ema20
        bearish += price < ema20

    if not pd.isna(ema20) and not pd.isna(ema50):
        bullish += ema20 > ema50
        bearish += ema20 < ema50

    if not pd.isna(price) and not pd.isna(ma200):
        bullish += price > ma200
        bearish += price < ma200

    if bullish >= 3:
        return "Bullish"

    if bearish >= 2:
        return "Bearish"

    return "Mixed"


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def get_basic_levels(df):

    if df is None or df.empty:
        return np.nan, np.nan

    recent = df.tail(50)

    price = float(df["Close"].iloc[-1])

    supports = []

    resistance = []

    for window in [20, 50]:

        low = recent["Low"].rolling(window).min().iloc[-1]

        high = recent["High"].rolling(window).max().iloc[-1]

        if not pd.isna(low) and low < price:
            supports.append(low)

        if not pd.isna(high) and high > price:
            resistance.append(high)

    support = max(supports) if supports else np.nan
    resist = min(resistance) if resistance else np.nan

    return support, resist


# ============================================================
# CHART
# ============================================================

def build_chart(
    df,
    history_days=120,
    show_sr=True,
    show_swing=False,
    show_rolling=False,
    show_previous=False,
    show_fib=False,
    show_pivot=False,
    show_atr=False,
    show_ema=False,
    show_bollinger=False,
    show_volume=True,
    show_rsi=False,
):

    data = df.tail(history_days).copy()

    rows = 1

    if show_volume:
        rows += 1

    if show_rsi:
        rows += 1

    heights = [0.62]

    if show_volume:
        heights.append(0.20)

    if show_rsi:
        heights.append(0.18)

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=heights,
    )

    # --------------------------------------------------------
    # Candles
    # --------------------------------------------------------

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            increasing_line_color="#00E676",
            decreasing_line_color="#FF4D5A",
            increasing_fillcolor="#00E676",
            decreasing_fillcolor="#FF4D5A",
            name="Price",
        ),
        row=1,
        col=1,
    )

    # --------------------------------------------------------
    # EMA / MA
    # --------------------------------------------------------

    if show_ema:

        for col, name, dash in [
            ("EMA20", "EMA 20", "solid"),
            ("EMA50", "EMA 50", "dot"),
            ("MA200", "MA 200", "dash"),
        ]:

            if col in data.columns:

                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data[col],
                        mode="lines",
                        name=name,
                        line=dict(
                            width=1.4,
                            dash=dash,
                        ),
                    ),
                    row=1,
                    col=1,
                )

    # --------------------------------------------------------
    # Bollinger
    # --------------------------------------------------------

    if show_bollinger:

        if "BB_UPPER" in data.columns:

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["BB_UPPER"],
                    mode="lines",
                    name="BB Upper",
                    line=dict(
                        width=1,
                        dash="dot",
                    ),
                ),
                row=1,
                col=1,
            )

        if "BB_LOWER" in data.columns:

            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data["BB_LOWER"],
                    mode="lines",
                    name="BB Lower",
                    line=dict(
                        width=1,
                        dash="dot",
                    ),
                ),
                row=1,
                col=1,
            )

    price = float(data["Close"].iloc[-1])

    # --------------------------------------------------------
    # S/R
    # --------------------------------------------------------

    support, resistance = get_basic_levels(data)

    if show_sr:

        if not pd.isna(support):

            fig.add_hline(
                y=support,
                line_dash="dot",
                line_width=1,
                annotation_text=f"Support {support:.2f}",
                annotation_position="bottom left",
                row=1,
                col=1,
            )

        if not pd.isna(resistance):

            fig.add_hline(
                y=resistance,
                line_dash="dot",
                line_width=1,
                annotation_text=f"Resistance {resistance:.2f}",
                annotation_position="top left",
                row=1,
                col=1,
            )

    # --------------------------------------------------------
    # 20 / 50 HIGH LOW
    # --------------------------------------------------------

    if show_rolling:

        for n in [20, 50]:

            high = data["High"].rolling(n).max().iloc[-1]
            low = data["Low"].rolling(n).min().iloc[-1]

            if not pd.isna(high):

                fig.add_hline(
                    y=high,
                    line_dash="dot",
                    line_width=0.8,
                    annotation_text=f"{n}D High",
                    row=1,
                    col=1,
                )

            if not pd.isna(low):

                fig.add_hline(
                    y=low,
                    line_dash="dot",
                    line_width=0.8,
                    annotation_text=f"{n}D Low",
                    row=1,
                    col=1,
                )

    # --------------------------------------------------------
    # Previous High / Low
    # --------------------------------------------------------

    if show_previous and len(data) >= 2:

        previous = data.iloc[-2]

        for level, label in [
            (previous["High"], "Prev High"),
            (previous["Low"], "Prev Low"),
        ]:

            fig.add_hline(
                y=level,
                line_dash="dash",
                line_width=1,
                annotation_text=label,
                row=1,
                col=1,
            )

    # --------------------------------------------------------
    # Fibonacci
    # --------------------------------------------------------

    if show_fib:

        swing_high = float(data["High"].max())
        swing_low = float(data["Low"].min())

        diff = swing_high - swing_low

        if diff > 0:

            for ratio in [0.236, 0.382, 0.5, 0.618, 0.786]:

                level = swing_high - diff * ratio

                fig.add_hline(
                    y=level,
                    line_dash="dot",
                    line_width=0.7,
                    annotation_text=f"Fib {ratio:.3f}",
                    row=1,
                    col=1,
                )

    # --------------------------------------------------------
    # Pivot
    # --------------------------------------------------------

    if show_pivot and len(data) >= 2:

        prev = data.iloc[-2]

        pp = (
            prev["High"] +
            prev["Low"] +
            prev["Close"]
        ) / 3

        r1 = 2 * pp - prev["Low"]
        s1 = 2 * pp - prev["High"]

        r2 = pp + (
            prev["High"] -
            prev["Low"]
        )

        s2 = pp - (
            prev["High"] -
            prev["Low"]
        )

        for level, label in [
            (pp, "Pivot"),
            (r1, "R1"),
            (r2, "R2"),
            (s1, "S1"),
            (s2, "S2"),
        ]:

            fig.add_hline(
                y=level,
                line_dash="dot",
                line_width=0.7,
                annotation_text=label,
                row=1,
                col=1,
            )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    if show_atr and "ATR14" in data.columns:

        atr = safe_float(data["ATR14"].iloc[-1])

        if not pd.isna(atr):

            for multiplier, label in [
                (1, "ATR -1"),
                (2, "ATR -2"),
            ]:

                fig.add_hline(
                    y=price - atr * multiplier,
                    line_dash="dash",
                    line_width=0.8,
                    annotation_text=label,
                    row=1,
                    col=1,
                )

            for multiplier, label in [
                (1, "ATR +1"),
                (2, "ATR +2"),
            ]:

                fig.add_hline(
                    y=price + atr * multiplier,
                    line_dash="dash",
                    line_width=0.8,
                    annotation_text=label,
                    row=1,
                    col=1,
                )

    # --------------------------------------------------------
    # Current Price
    # --------------------------------------------------------

    fig.add_hline(
        y=price,
        line_dash="solid",
        line_width=1.2,
        annotation_text=f"Historical Close {price:.2f}",
        annotation_position="top right",
        row=1,
        col=1,
    )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    current_row = 2

    if show_volume:

        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                name="Volume",
                opacity=0.55,
            ),
            row=current_row,
            col=1,
        )

        current_row += 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if show_rsi and "RSI14" in data.columns:

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["RSI14"],
                mode="lines",
                name="RSI 14",
                line=dict(width=1.4),
            ),
            row=current_row,
            col=1,
        )

        fig.add_hline(
            y=70,
            line_dash="dot",
            line_width=0.7,
            row=current_row,
            col=1,
        )

        fig.add_hline(
            y=30,
            line_dash="dot",
            line_width=0.7,
            row=current_row,
            col=1,
        )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    fig.update_layout(
        height=750,
        template="plotly_dark",
        paper_bgcolor="#050607",
        plot_bgcolor="#080A0C",
        font=dict(
            color="#DDE2E8",
            size=11,
        ),
        margin=dict(
            l=10,
            r=10,
            t=35,
            b=10,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#15191E",
        zeroline=False,
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="#15191E",
        zeroline=False,
    )

    return fig


# ============================================================
# RADAR CHART
# ============================================================

def build_radar(analysis):

    categories = [
        "Trend",
        "Momentum",
        "Volume",
        "Price Action",
        "Money Flow",
        "Volatility",
        "Strength",
    ]

    values = [
        normalize_score(
            analysis.get("trend_score"), 20
        ),
        normalize_score(
            analysis.get("momentum_score"), 15
        ),
        normalize_score(
            analysis.get("volume_score"), 15
        ),
        normalize_score(
            analysis.get("price_action_score"), 15
        ),
        normalize_score(
            analysis.get("money_flow_score"), 10
        ),
        normalize_score(
            analysis.get("volatility_score"), 5
        ),
        normalize_score(
            analysis.get("price_strength_score"), 5
        ),
    ]

    categories += [categories[0]]
    values += [values[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name="legend-Mo",
            line=dict(
                width=2,
            ),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0D10",
        plot_bgcolor="#0A0D10",
        height=330,
        margin=dict(
            l=35,
            r=35,
            t=20,
            b=20,
        ),
        polar=dict(
            bgcolor="#0A0D10",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="#252B32",
                linecolor="#252B32",
                tickfont=dict(
                    color="#646C76",
                    size=8,
                ),
            ),
            angularaxis=dict(
                gridcolor="#252B32",
                linecolor="#252B32",
                tickfont=dict(
                    color="#9BA2AB",
                    size=9,
                ),
            ),
        ),
        showlegend=False,
    )

    return fig


# ============================================================
# LOAD ANALYSIS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_market_prices():

    try:
        return fetch_mubasher_prices()
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(symbol, mubasher_prices):

    df, source = get_stock_data(
        symbol,
        mubasher_prices
    )

    if df is None or df.empty:
        return None, None

    historical_close = safe_float(
        df.attrs.get(
            "historical_close",
            df["Close"].iloc[-1]
        )
    )

    current_price = safe_float(
        df.attrs.get(
            "current_price",
            historical_close
        )
    )

    price_source = df.attrs.get(
        "price_source",
        source
    )

    is_realtime = bool(
        df.attrs.get(
            "is_realtime",
            False
        )
    )

    change_pct = (
        (current_price / historical_close - 1) * 100
        if historical_close
        else np.nan
    )

    # IMPORTANT:
    # Indicators remain based on Yahoo historical Close.
    data = calculate_indicators(df.copy())

    analysis = evaluate_stock_strategy(
        data
    )

    if analysis is None:
        return data, None

    # Attach metadata
    analysis["current_price"] = current_price
    analysis["historical_close"] = historical_close
    analysis["price_source"] = price_source
    analysis["is_realtime"] = is_realtime
    analysis["current_vs_close_pct"] = change_pct

    return data, analysis


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div style="display:flex;justify-content:space-between;
            align-items:flex-end;margin-bottom:20px;">

<div>
    <div class="brand">legend-Mo <span>LENS</span></div>
    <div class="brand-sub">
        EGX TECHNICAL INTELLIGENCE
    </div>
</div>

<div style="text-align:right;">
    <div class="label">ANALYTICAL ENGINE</div>
    <div style="font-size:13px;color:#B6BDC6;">
        Technical • Momentum • Flow • Risk
    </div>
</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="
            font-size:20px;
            font-weight:800;
            margin-bottom:15px;
        ">
        🖤 legend-Mo
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Market")

    # EGX universe from config
    try:
        from config import EGX_STOCKS

        stock_list = list(EGX_STOCKS)

    except Exception:

        stock_list = [
            "COMI",
            "SWDY",
            "EFIH",
            "FWRY",
            "TMGH",
            "ORAS",
            "MASR",
            "SPMD",
            "EXPA",
            "ACGC",
            "NIPH",
            "KORA",
            "GTWL",
            "MILS",
            "SIPC",
        ]

    symbol = st.selectbox(
        "Select Stock",
        stock_list,
        index=0,
    )

    st.markdown("---")

    history_days = st.slider(
        "Chart History",
        min_value=30,
        max_value=300,
        value=120,
        step=10,
    )

    st.markdown("### Chart Tools")

    show_sr = st.toggle(
        "Support / Resistance",
        value=True,
    )

    show_swing = st.toggle(
        "Swing High / Low",
        value=False,
    )

    show_rolling = st.toggle(
        "20D / 50D High-Low",
        value=False,
    )

    show_previous = st.toggle(
        "Previous High / Low",
        value=False,
    )

    show_fib = st.toggle(
        "Fibonacci",
        value=False,
    )

    show_pivot = st.toggle(
        "Pivot Points",
        value=False,
    )

    show_atr = st.toggle(
        "ATR Zones",
        value=False,
    )

    show_ema = st.toggle(
        "EMA 20 / 50 / MA 200",
        value=True,
    )

    show_bollinger = st.toggle(
        "Bollinger Bands",
        value=False,
    )

    show_volume = st.toggle(
        "Volume",
        value=True,
    )

    show_rsi = st.toggle(
        "RSI",
        value=False,
    )

    st.markdown("---")

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True,
    ):

        st.cache_data.clear()
        st.rerun()


# ============================================================
# LOAD
# ============================================================

with st.spinner("Loading market intelligence..."):

    try:

        mubasher_prices = load_market_prices()

        df, analysis = load_analysis(
            symbol,
            mubasher_prices
        )

    except Exception as e:

        st.error(
            f"Data error: {e}"
        )

        st.stop()


if df is None or analysis is None:

    st.warning(
        "No valid analysis available for this symbol."
    )

    st.stop()


# ============================================================
# CURRENT PRICE
# ============================================================

current_price = safe_float(
    analysis.get("current_price")
)

historical_close = safe_float(
    analysis.get("historical_close")
)

change_pct = safe_float(
    analysis.get("current_vs_close_pct")
)

source = analysis.get(
    "price_source",
    "Yahoo Finance"
)

realtime = bool(
    analysis.get(
        "is_realtime",
        False
    )
)


# ============================================================
# HERO STOCK CARD
# ============================================================

trend = trend_description(df)

score = clamp(
    analysis.get("score", 0)
)

score_class = score_color(score)

recommendation = analysis.get(
    "recommendation",
    "—"
)

st.markdown(
    f"""
<div class="lm-card">

<div style="
display:flex;
justify-content:space-between;
align-items:center;
">

<div>

<div class="label">EGX EQUITY</div>

<div style="
font-size:34px;
font-weight:800;
margin-top:4px;
">
{symbol}
</div>

<div style="
color:#707883;
font-size:11px;
margin-top:4px;
">
legend-Mo Lens Analysis
</div>

</div>

<div style="text-align:right;">

<div class="label">CURRENT PRICE</div>

<div class="big-value">
{fmt(current_price)}
</div>

<div class="{('green' if change_pct >= 0 else 'red')}"
style="font-size:13px;font-weight:700;margin-top:5px;">

{'▲' if change_pct >= 0 else '▼'}
{pct(abs(change_pct))}

</div>

</div>

</div>

<div class="divider"></div>

<div style="
display:flex;
justify-content:space-between;
align-items:center;
">

<div>

<span class="label">PRICE SOURCE</span><br>

<span style="font-size:12px;color:#B8BEC6;">
{source}
{' • LIVE' if realtime else ' • FALLBACK'}
</span>

</div>

<div>

<span class="label">HISTORICAL CLOSE</span><br>

<span style="font-size:12px;color:#B8BEC6;">
{fmt(historical_close)}
</span>

</div>

<div>

<span class="label">TREND</span><br>

<span class="{('green' if trend == 'Bullish' else 'red' if trend == 'Bearish' else 'yellow')}"
style="font-size:13px;font-weight:700;">
{trend}
</span>

</div>

<div>

<span class="label">SIGNAL</span><br>

<span style="font-size:13px;font-weight:700;color:#EDEFF2;">
{recommendation}
</span>

</div>

</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SCORE + QUICK METRICS
# ============================================================

col1, col2, col3, col4, col5 = st.columns(
    [1.25, 1, 1, 1, 1]
)


with col1:

    st.markdown(
        f"""
        <div class="lm-card" style="height:145px;">

        <div class="score-label">
        LEGEND-MO SCORE
        </div>

        <div class="score-number {score_class}">
        {score:.0f}
        </div>

        <div style="
        color:#737B85;
        font-size:11px;
        margin-top:7px;
        ">
        / 100 • {score_text(score)}
        </div>

        <div class="progress-bg">
            <div class="progress-fill"
                 style="width:{score:.0f}%;">
            </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col2:

    rsi = safe_float(
        df["RSI14"].iloc[-1]
        if "RSI14" in df.columns
        else np.nan
    )

    st.markdown(
        f"""
        <div class="lm-card" style="height:145px;">
        <div class="label">RSI 14</div>
        <div class="metric-value">{fmt(rsi,1)}</div>
        <div class="metric-sub">Momentum</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col3:

    adx = safe_float(
        df["ADX14"].iloc[-1]
        if "ADX14" in df.columns
        else np.nan
    )

    st.markdown(
        f"""
        <div class="lm-card" style="height:145px;">
        <div class="label">ADX</div>
        <div class="metric-value">{fmt(adx,1)}</div>
        <div class="metric-sub">Trend Strength</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col4:

    volume_ratio = safe_float(
        df["Volume_Ratio"].iloc[-1]
        if "Volume_Ratio" in df.columns
        else np.nan
    )

    st.markdown(
        f"""
        <div class="lm-card" style="height:145px;">
        <div class="label">VOLUME RATIO</div>
        <div class="metric-value">{fmt(volume_ratio,2)}x</div>
        <div class="metric-sub">Trading Activity</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col5:

    atr = safe_float(
        df["ATR14"].iloc[-1]
        if "ATR14" in df.columns
        else np.nan
    )

    atr_pct = (
        atr / historical_close * 100
        if historical_close and not pd.isna(atr)
        else np.nan
    )

    st.markdown(
        f"""
        <div class="lm-card" style="height:145px;">
        <div class="label">ATR %</div>
        <div class="metric-value">{fmt(atr_pct,2)}%</div>
        <div class="metric-sub">Volatility</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SCORE BREAKDOWN
# ============================================================

st.markdown("## Score Intelligence")

left, right = st.columns(
    [1.2, 1]
)


with left:

    st.markdown(
        """
        <div class="lm-card">
        <div class="label">LEGEND-MO SCORE BREAKDOWN</div>
        <div style="height:10px;"></div>
        """,
        unsafe_allow_html=True,
    )

    breakdown = {
        "Trend": (
            analysis.get("trend_score", 0),
            20,
        ),
        "Momentum": (
            analysis.get("momentum_score", 0),
            15,
        ),
        "Volume": (
            analysis.get("volume_score", 0),
            15,
        ),
        "Price Action": (
            analysis.get("price_action_score", 0),
            15,
        ),
        "Support / Resistance": (
            analysis.get("sr_score", 0),
            15,
        ),
        "Money Flow": (
            analysis.get("money_flow_score", 0),
            10,
        ),
        "Volatility": (
            analysis.get("volatility_score", 0),
            5,
        ),
        "Price Strength": (
            analysis.get("price_strength_score", 0),
            5,
        ),
    }

    for name, (value, maximum) in breakdown.items():

        val = clamp(
            safe_float(value, 0),
            0,
            maximum
        )

        percentage = (
            val / maximum * 100
            if maximum
            else 0
        )

        st.markdown(
            f"""
            <div style="
                margin-bottom:12px;
            ">

            <div style="
                display:flex;
                justify-content:space-between;
                font-size:12px;
            ">

            <span style="color:#B8BEC6;">
            {name}
            </span>

            <span style="
                color:#F1F3F5;
                font-weight:700;
            ">
            {val:.1f} / {maximum}
            </span>

            </div>

            <div class="progress-bg">
                <div class="progress-fill"
                     style="width:{percentage:.1f}%;">
                </div>
            </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


with right:

    st.markdown(
        """
        <div class="lm-card">
        <div class="label">TECHNICAL RADAR</div>
        """,
        unsafe_allow_html=True,
    )

    st.plotly_chart(
        build_radar(analysis),
        use_container_width=True,
        config={
            "displayModeBar": False
        },
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SCENARIOS
# ============================================================

scenarios = calculate_scenarios(
    analysis
)

st.markdown("## Market Scenario")

c1, c2, c3 = st.columns(3)

for col, title, value, cls in [
    (c1, "BULLISH", scenarios["Bullish"], "green"),
    (c2, "SIDEWAYS", scenarios["Sideways"], "yellow"),
    (c3, "BEARISH", scenarios["Bearish"], "red"),
]:

    with col:

        st.markdown(
            f"""
            <div class="scenario">

            <div class="scenario-title">
            {title}
            </div>

            <div class="scenario-value {cls}">
            {value:.0f}%
            </div>

            <div class="progress-bg">
                <div class="progress-fill"
                     style="width:{value:.0f}%;">
                </div>
            </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

st.caption(
    "Scenario percentages are heuristic model estimates based on the "
    "Legend-Mo scoring engine, not statistically calibrated probabilities."
)


# ============================================================
# PRICE CHART
# ============================================================

st.markdown("## Price Action Lab")

chart = build_chart(
    df=df,
    history_days=history_days,
    show_sr=show_sr,
    show_swing=show_swing,
    show_rolling=show_rolling,
    show_previous=show_previous,
    show_fib=show_fib,
    show_pivot=show_pivot,
    show_atr=show_atr,
    show_ema=show_ema,
    show_bollinger=show_bollinger,
    show_volume=show_volume,
    show_rsi=show_rsi,
)

st.plotly_chart(
    chart,
    use_container_width=True,
    config={
        "displaylogo": False,
        "scrollZoom": True,
        "displayModeBar": True,
    },
)


# ============================================================
# MONEY FLOW + SELLING PRESSURE
# ============================================================

selling_pressure = calculate_selling_pressure(df)

money_col, pressure_col, strength_col = st.columns(3)


with money_col:

    money_score = normalize_score(
        analysis.get("money_flow_score"),
        10
    )

    st.markdown(
        f"""
        <div class="lm-card">

        <div class="label">
        MONEY FLOW
        </div>

        <div class="big-value">
        {money_score:.0f}
        </div>

        <div class="metric-sub">
        / 100
        </div>

        <div class="divider"></div>

        <div class="signal-box">
        <div class="signal-title">
        ACCUMULATION / DISTRIBUTION
        </div>

        <div class="signal-value">
        {
            "Accumulation"
            if money_score >= 60
            else "Distribution"
            if money_score < 40
            else "Neutral"
        }
        </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with pressure_col:

    pressure_class = (
        "red"
        if selling_pressure >= 65
        else "yellow"
        if selling_pressure >= 45
        else "green"
    )

    pressure_text = (
        "High"
        if selling_pressure >= 65
        else "Moderate"
        if selling_pressure >= 45
        else "Low"
    )

    st.markdown(
        f"""
        <div class="lm-card">

        <div class="label">
        SELLING PRESSURE
        </div>

        <div class="big-value {pressure_class}">
        {selling_pressure:.0f}
        </div>

        <div class="metric-sub">
        / 100
        </div>

        <div class="divider"></div>

        <div class="signal-box">
        <div class="signal-title">
        PRESSURE STATUS
        </div>

        <div class="signal-value {pressure_class}">
        {pressure_text}
        </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with strength_col:

    strength = normalize_score(
        analysis.get("price_strength_score"),
        5
    )

    st.markdown(
        f"""
        <div class="lm-card">

        <div class="label">
        PRICE STRENGTH
        </div>

        <div class="big-value">
        {strength:.0f}
        </div>

        <div class="metric-sub">
        / 100
        </div>

        <div class="divider"></div>

        <div class="signal-box">
        <div class="signal-title">
        52 WEEK POSITION
        </div>

        <div class="signal-value">
        {
            fmt(
                df["Position_52W"].iloc[-1] * 100,
                1
            ) + "%"
            if "Position_52W" in df.columns
            else "—"
        }
        </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SUPPORT / RESISTANCE + 52W RANGE
# ============================================================

support, resistance = get_basic_levels(df)

range_col, level_col = st.columns(2)


with range_col:

    if "52W_Low" in df.columns:
        low52 = safe_float(
            df["52W_Low"].iloc[-1]
        )
    else:
        low52 = safe_float(
            df["Low"].tail(252).min()
        )

    if "52W_High" in df.columns:
        high52 = safe_float(
            df["52W_High"].iloc[-1]
        )
    else:
        high52 = safe_float(
            df["High"].tail(252).max()
        )

    position = (
        (historical_close - low52) /
        (high52 - low52) * 100
        if high52 > low52
        else np.nan
    )

    st.markdown(
        f"""
        <div class="lm-card">

        <div class="label">
        52 WEEK RANGE
        </div>

        <div style="
        display:flex;
        justify-content:space-between;
        margin-top:10px;
        ">

        <div>
        <div class="metric-sub">LOW</div>
        <div class="metric-value">
        {fmt(low52)}
        </div>
        </div>

        <div style="text-align:right;">
        <div class="metric-sub">HIGH</div>
        <div class="metric-value">
        {fmt(high52)}
        </div>
        </div>

        </div>

        <div class="progress-bg"
             style="height:9px;margin-top:15px;">

            <div class="progress-fill"
                 style="width:{clamp(position):.1f}%;">
            </div>

        </div>

        <div style="
        text-align:center;
        color:#858D97;
        font-size:11px;
        margin-top:8px;
        ">
        Current Position: {fmt(position,1)}%
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with level_col:

    st.markdown(
        f"""
        <div class="lm-card">

        <div class="label">
        MARKET STRUCTURE
        </div>

        <div style="
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:10px;
        margin-top:15px;
        ">

        <div class="signal-box">
        <div class="signal-title">
        SUPPORT
        </div>

        <div class="signal-value green">
        {fmt(support)}
        </div>
        </div>

        <div class="signal-box">
        <div class="signal-title">
        RESISTANCE
        </div>

        <div class="signal-value red">
        {fmt(resistance)}
        </div>
        </div>

        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown("## Trade Intelligence")

entry = safe_float(
    analysis.get("entry")
)

stop_loss = safe_float(
    analysis.get("stop_loss")
)

tp1 = safe_float(
    analysis.get("take_profit_1")
)

tp2 = safe_float(
    analysis.get("take_profit_2")
)

rr1 = safe_float(
    analysis.get("rr1")
)

rr2 = safe_float(
    analysis.get("rr2")
)

t1, t2, t3, t4, t5 = st.columns(5)


trade_cards = [
    ("ENTRY", entry, ""),
    ("STOP LOSS", stop_loss, ""),
    ("TP1", tp1, ""),
    ("TP2", tp2, ""),
    ("R/R", rr1, f" / {rr2:.2f}" if not pd.isna(rr2) else ""),
]


for col, (title, value, suffix) in zip(
    [t1, t2, t3, t4, t5],
    trade_cards,
):

    with col:

        display_value = (
            f"{value:.2f}{suffix}"
            if not pd.isna(value)
            else "—"
        )

        st.markdown(
            f"""
            <div class="lm-card"
                 style="height:125px;">

            <div class="label">
            {title}
            </div>

            <div class="metric-value"
                 style="font-size:23px;">
            {display_value}
            </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# TECHNICAL MATRIX
# ============================================================

st.markdown("## Technical Matrix")

row = df.iloc[-1]

technical_data = {
    "EMA20": row.get("EMA20"),
    "EMA50": row.get("EMA50"),
    "MA200": row.get("MA200"),
    "RSI14": row.get("RSI14"),
    "ADX14": row.get("ADX14"),
    "DI+": row.get("DI_PLUS"),
    "DI-": row.get("DI_MINUS"),
    "MACD": row.get("MACD"),
    "MACD Signal": row.get("MACD_Signal"),
    "MACD Hist": row.get("MACD_Hist"),
    "ATR14": row.get("ATR14"),
    "CMF20": row.get("CMF20"),
    "MFI14": row.get("MFI14"),
    "ROC20": row.get("ROC20"),
    "Volume Ratio": row.get("Volume_Ratio"),
}

tech_df = pd.DataFrame(
    [
        {
            "Indicator": key,
            "Value": (
                round(float(value), 4)
                if not pd.isna(safe_float(value))
                else "—"
            ),
        }
        for key, value in technical_data.items()
    ]
)

st.dataframe(
    tech_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# REASONS
# ============================================================

reasons = analysis.get(
    "reasons",
    []
)

if reasons:

    st.markdown("## Signal Drivers")

    reason_cols = st.columns(
        min(3, len(reasons))
    )

    for i, reason in enumerate(reasons):

        with reason_cols[i % len(reason_cols)]:

            st.markdown(
                f"""
                <div class="signal-box"
                     style="margin-bottom:8px;">

                <span style="
                color:#DCE1E6;
                font-size:12px;
                ">
                • {reason}
                </span>

                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
    legend-Mo LENS • EGX TECHNICAL INTELLIGENCE
    <br>
    Developed by legend-Mo
    </div>
    """,
    unsafe_allow_html=True,
)
