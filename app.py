# ============================================================
# legend-Mo LENS
# EGX Technical Intelligence Dashboard
# Main Search & Full Neon Blue Button Grid Edition
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ============================================================
# PROJECT IMPORTS
# ============================================================

from scanner import (
    fetch_mubasher_prices,
    get_stock_data,
    load_saved_context,
)

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy
from signals import attach_context, REGIME_LABELS


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="legend-Mo LENS",
    page_icon="🖤",
    layout="wide",
)


# ============================================================
# PREMIUM BLACK CSS & FULL NEON BLUE BUTTON STYLING
# ============================================================

st.markdown(
    """
<style>

@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');

html,
body,
.stApp {
    font-family: 'Cairo', sans-serif !important;
    background:
        radial-gradient(circle at 15% 10%, rgba(255,255,255,0.035), transparent 25%),
        radial-gradient(circle at 85% 20%, rgba(0,255,170,0.025), transparent 25%),
        #050607 !important;
    color: #F5F7FA !important;
    direction: rtl;
}

.block-container {
    width: 100% !important;
    max-width: 1600px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    direction: rtl;
}

h1, h2, h3, h4 {
    color: #F7F8FA !important;
    font-family: 'Cairo', sans-serif !important;
    direction: rtl;
    text-align: right;
    line-height: 1.5 !important;
}

.lm-card {
    background: linear-gradient(145deg, #0C0F12 0%, #090B0E 100%);
    border: 1px solid #1B2026;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.28);
    text-align: right;
    direction: rtl;
    width: 100%;
    box-sizing: border-box;
}

.brand {
    font-size: 28px;
    font-weight: 800;
}

.brand span {
    color: #FFFFFF;
}

.brand-sub {
    color: #737B86;
    font-size: 11px;
}

.label {
    color: #727A84;
    font-size: 11px;
    font-weight: 600;
}

.big-value {
    color: #FFFFFF;
    font-size: 30px;
    font-weight: 800;
    line-height: 1;
    margin-top: 8px;
}

.metric-value {
    color: #F5F7FA;
    font-size: 20px;
    font-weight: 700;
    margin-top: 5px;
}

.metric-sub {
    color: #6F7781;
    font-size: 11px;
}

.green { color: #00E676 !important; }
.red { color: #FF4D5A !important; }
.yellow { color: #FFC857 !important; }
.blue { color: #55A7FF !important; }

.score-number {
    font-size: 55px;
    font-weight: 800;
    line-height: 0.9;
}

.score-label {
    color: #858D98;
    font-size: 11px;
}

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
    background: linear-gradient(90deg, #FFFFFF, #777F89);
}

.scenario {
    background: #0A0D10;
    border: 1px solid #1A1F25;
    border-radius: 12px;
    padding: 14px;
    text-align: right;
    direction: rtl;
    width: 100%;
    box-sizing: border-box;
    margin-bottom: 8px;
}

.scenario-title {
    color: #818995;
    font-size: 11px;
    font-weight: 700;
}

.scenario-value {
    font-size: 22px;
    font-weight: 800;
    margin-top: 5px;
}

.signal-box {
    padding: 14px;
    border-radius: 12px;
    background: #0B0E11;
    border: 1px solid #1B2026;
    box-sizing: border-box;
    width: 100%;
}

.divider {
    height: 1px;
    background: #181C21;
    margin: 15px 0;
}

.footer {
    text-align: center;
    color: #454C55;
    font-size: 11px;
    padding: 25px 0 10px 0;
    line-height: 1.8;
}

/* Base button styling */
.stButton > button {
    background: #0D1013 !important;
    color: #8A929D !important;
    border: 1px solid #242A31 !important;
    border-radius: 10px !important;
    font-family: 'Cairo', sans-serif !important;
    width: 100%;
    transition: all 0.2s ease;
}

/* Active tool button (type="primary") = neon blue */
.stButton > button[kind="primary"] {
    background: linear-gradient(145deg, #102B4E 0%, #081628 100%) !important;
    border: 1.5px solid #55A7FF !important;
    color: #55A7FF !important;
    box-shadow: 0 0 15px rgba(85, 167, 255, 0.4), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    font-weight: 700 !important;
}

div[data-baseweb="select"] > div {
    background: #0C0F12 !important;
    border-color: #242A31 !important;
}

/* Mobile Columns Wrapping Fix */
@media (max-width: 768px) {
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        width: 100% !important;
    }
    [data-testid="column"],
    [data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        margin-bottom: 10px;
    }
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
    if score >= 50:
        return "yellow"
    return "red"


def score_text(score):
    score = safe_float(score, 0)
    if score >= 80:
        return "قوي جداً"
    if score >= 70:
        return "قوي"
    if score >= 60:
        return "إيجابي"
    if score >= 50:
        return "حيادي"
    return "ضعيف"


def normalize_score(value, maximum):
    value = safe_float(value, 0)
    if maximum <= 0:
        return 0
    return clamp(value / maximum * 100)


# ============================================================
# TECHNICAL BALANCE (مؤشر مركب - ليس احتمالاً)
# ============================================================

def calculate_scenarios(analysis):
    score = clamp(analysis.get("score", 50))
    trend = normalize_score(analysis.get("trend_score", 0), 20)
    momentum = normalize_score(analysis.get("momentum_score", 0), 15)
    volume = normalize_score(analysis.get("volume_score", 0), 15)
    money = normalize_score(analysis.get("money_flow_score", 0), 10)

    bullish = score * 0.45 + trend * 0.20 + momentum * 0.25 + volume * 0.05 + money * 0.05
    bearish = (100 - score) * 0.45 + (100 - trend) * 0.20 + (100 - momentum) * 0.25 + (100 - volume) * 0.05 + (100 - money) * 0.05
    sideways = 100 - abs(bullish - bearish)

    bullish = max(1, bullish)
    bearish = max(1, bearish)
    sideways = max(1, sideways)

    total = bullish + sideways + bearish

    return {
        "Bullish": bullish / total * 100,
        "Sideways": sideways / total * 100,
        "Bearish": bearish / total * 100,
    }


# ============================================================
# TREND
# ============================================================

def trend_description(df):
    if df is None or df.empty:
        return "غير محدد"

    row = df.iloc[-1]
    price = safe_float(row.get("Close"))
    ema20 = safe_float(row.get("EMA_20"))
    ema50 = safe_float(row.get("EMA_50"))
    ma200 = safe_float(row.get("MA_200"))

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
        return "صاعد 📈"
    if bearish >= 2:
        return "هابط 📉"
    return "متذبذب / عرضي 🔄"


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def get_basic_levels(df):
    if df is None or df.empty:
        return np.nan, np.nan

    recent = df.tail(50)
    price = float(df["Close"].iloc[-1])
    supports = []
    resistances = []

    for window in [20, 50]:
        low = recent["Low"].rolling(window).min().iloc[-1]
        high = recent["High"].rolling(window).max().iloc[-1]
        if not pd.isna(low) and low < price:
            supports.append(low)
        if not pd.isna(high) and high > price:
            resistances.append(high)

    support = max(supports) if supports else np.nan
    resistance = min(resistances) if resistances else np.nan
    return support, resistance


# ============================================================
# CHART BUILDER
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
    if show_volume: rows += 1
    if show_rsi: rows += 1

    heights = [0.62]
    if show_volume: heights.append(0.20)
    if show_rsi: heights.append(0.18)

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=heights,
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            increasing_line_color="#00E676",
            decreasing_line_color="#FF4D5A",
            name="السعر",
        ),
        row=1,
        col=1,
    )

    def hline(y, text, dash="dot", color="#6F7781", pos="bottom left"):
        if y is None or pd.isna(y):
            return
        fig.add_hline(
            y=float(y), line_dash=dash, line_width=1, line_color=color,
            annotation_text=f"{text} {float(y):.2f}", annotation_position=pos,
            row=1, col=1,
        )

    def line(col, name, color=None, dash="solid", width=1.4):
        if col in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data.index, y=data[col], mode="lines", name=name,
                    line=dict(width=width, dash=dash, **({"color": color} if color else {})),
                ),
                row=1, col=1,
            )

    if show_ema:
        line("EMA_20", "EMA 20")
        line("EMA_50", "EMA 50", dash="dot")
        line("MA_200", "MA 200", dash="dash")

    if show_bollinger:
        line("BB_UPPER", "Bollinger علوي", color="#8A929D", dash="dot", width=1)
        line("BB_MIDDLE", "Bollinger وسط", color="#55A7FF", dash="dot", width=1)
        line("BB_LOWER", "Bollinger سفلي", color="#8A929D", dash="dot", width=1)

    if show_atr:
        line("Chandelier_22", "وقف المطاردة (ATR×3)", color="#FFC857", width=1.4)
        line("Supertrend", "Supertrend", color="#C084FC", dash="dot", width=1.2)

    price = float(data["Close"].iloc[-1])
    support, resistance = get_basic_levels(data)

    if show_sr:
        hline(support, "دعم", color="#00E676", pos="bottom left")
        hline(resistance, "مقاومة", color="#FF4D5A", pos="top left")

    if show_rolling:
        last = data.iloc[-1]
        hline(last.get("Resistance_20"), "قمة 20", color="#FF4D5A", pos="top left")
        hline(last.get("Support_20"), "قاع 20", color="#00E676", pos="bottom left")
        hline(last.get("Resistance_50"), "قمة 50", color="#FF8A94", dash="dash", pos="top left")
        hline(last.get("Support_50"), "قاع 50", color="#7CF0B0", dash="dash", pos="bottom left")

    if show_previous and len(data) >= 2:
        prev = data.iloc[-2]
        hline(prev["High"], "قمة الجلسة السابقة", color="#9AA3AF", pos="top right")
        hline(prev["Low"], "قاع الجلسة السابقة", color="#9AA3AF", pos="bottom right")

    if show_pivot:
        last = data.iloc[-1]
        p = (last["High"] + last["Low"] + last["Close"]) / 3
        rng = last["High"] - last["Low"]
        for name, val in (
            ("R2", p + rng), ("R1", 2 * p - last["Low"]), ("P", p),
            ("S1", 2 * p - last["High"]), ("S2", p - rng),
        ):
            hline(val, f"Pivot {name}", color="#C084FC", pos="top right")

    if show_fib:
        hi, lo = float(data["High"].max()), float(data["Low"].min())
        for lvl in (0.236, 0.382, 0.5, 0.618, 0.786):
            hline(hi - (hi - lo) * lvl, f"Fib {lvl:g}", color="#FFC857", pos="top right")

    if show_swing and len(data) >= 11:
        swing_hi = data["High"] == data["High"].rolling(11, center=True).max()
        swing_lo = data["Low"] == data["Low"].rolling(11, center=True).min()
        fig.add_trace(go.Scatter(
            x=data.index[swing_hi], y=data["High"][swing_hi] * 1.005, mode="markers",
            marker=dict(symbol="triangle-down", size=9, color="#FF4D5A"), name="قمة Swing",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index[swing_lo], y=data["Low"][swing_lo] * 0.995, mode="markers",
            marker=dict(symbol="triangle-up", size=9, color="#00E676"), name="قاع Swing",
        ), row=1, col=1)

    fig.add_hline(
        y=price,
        line_dash="solid",
        line_width=1.2,
        annotation_text=f"الإغلاق التاريخي {price:.2f}",
        annotation_position="top right",
        row=1,
        col=1,
    )

    current_row = 2
    if show_volume:
        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                name="حجم التداول",
                opacity=0.55,
            ),
            row=current_row,
            col=1,
        )
        current_row += 1

    if show_rsi and "RSI_14" in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["RSI_14"],
                mode="lines",
                name="RSI 14",
                line=dict(width=1.4),
            ),
            row=current_row,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_width=0.7, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dot", line_width=0.7, row=current_row, col=1)

    fig.update_layout(
        height=750,
        template="plotly_dark",
        paper_bgcolor="#050607",
        plot_bgcolor="#080A0C",
        font=dict(color="#DDE2E8", size=11, family="Cairo"),
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#15191E", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#15191E", zeroline=False)
    return fig


# ============================================================
# RADAR
# ============================================================

def build_radar(analysis):
    categories = ["الاتجاه", "الزخم", "الحجم", "حركة السعر", "السيولة", "التقلبات", "القوة"]
    values = [
        normalize_score(analysis.get("trend_score"), 20),
        normalize_score(analysis.get("momentum_score"), 15),
        normalize_score(analysis.get("volume_score"), 15),
        normalize_score(analysis.get("price_action_score"), 15),
        normalize_score(analysis.get("money_flow_score"), 10),
        normalize_score(analysis.get("volatility_score"), 5),
        normalize_score(analysis.get("price_strength_score"), 5),
    ]
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name="legend-Mo",
            line=dict(width=2),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0D10",
        plot_bgcolor="#0A0D10",
        height=330,
        margin=dict(l=35, r=35, t=20, b=20),
        polar=dict(
            bgcolor="#0A0D10",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="#252B32",
                linecolor="#252B32",
                tickfont=dict(color="#646C76", size=8),
            ),
            angularaxis=dict(
                gridcolor="#252B32",
                linecolor="#252B32",
                tickfont=dict(color="#9BA2AB", size=9, family="Cairo"),
            ),
        ),
        showlegend=False,
    )
    return fig


# ============================================================
# MARKET DATA CACHE
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_market_prices():
    try:
        return fetch_mubasher_prices()
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def load_market_context():
    """سياق السوق (Breadth + القوة النسبية) المحفوظ من آخر تشغيل للسكانر."""
    try:
        return load_saved_context()
    except Exception:
        return None


# ============================================================
# STOCK ANALYSIS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(symbol, mubasher_prices, context):
    try:
        result = get_stock_data(symbol, mubasher_prices)
    except Exception:
        result = None

    if result is None:
        return None, None

    if isinstance(result, tuple):
        df, source = result
    else:
        df = result
        source = "غير معروف"

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None, None

    historical_close = safe_float(df.attrs.get("historical_close", df["Close"].iloc[-1]))
    current_price = safe_float(df.attrs.get("current_price", historical_close))
    price_source = df.attrs.get("price_source", source)
    is_realtime = bool(df.attrs.get("is_realtime", False))
    attrs = dict(df.attrs)

    change_pct = (
        (current_price / historical_close - 1) * 100
        if (historical_close and historical_close > 0)
        else np.nan
    )

    try:
        data = calculate_indicators(df.copy())
    except Exception:
        data = None

    if data is None or data.empty:
        return None, None

    data.attrs.update(attrs)
    data = attach_context(data, context)

    try:
        analysis = evaluate_stock_strategy(data, symbol)
    except Exception:
        analysis = None

    if analysis is None:
        analysis = {
            "score": 50,
            "rec": "حيادي",
            "trend_score": 10,
            "momentum_score": 7,
            "volume_score": 7,
            "price_action_score": 7,
            "sr_score": 7,
            "money_flow_score": 5,
            "volatility_score": 3,
            "price_strength_score": 4,
            "setups": [],
            "reasons": ["تم توليد تحليل افتراضي آمن لعدم توفر بيانات تفصيلية كافية."],
        }

    analysis["current_price"] = current_price
    analysis["historical_close"] = historical_close
    analysis["price_source"] = price_source
    analysis["is_realtime"] = is_realtime
    analysis["current_vs_close_pct"] = change_pct

    return data, analysis


# ============================================================
# HEADER & MAIN SEARCH BAR
# ============================================================

st.markdown(
    """
<div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:15px; direction:rtl; gap:20px; flex-wrap:wrap;">
    <div>
        <div class="brand">legend-Mo <span>LENS</span></div>
        <div class="brand-sub">التحليل الذكي للأسهم المصرية</div>
    </div>
    <div style="text-align:left;">
        <div class="label">محرك التحليل الفني</div>
        <div style="font-size:12px; color:#B6BDC6;">الاتجاه • الزخم • السيولة • المخاطرة</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

control_col1, control_col2, control_col3 = st.columns([2, 2, 1])

with control_col1:
    try:
        from config import EGX_STOCKS
        stock_list = list(EGX_STOCKS)
    except Exception:
        stock_list = [
            s + ".CA" for s in
            ["COMI", "SWDY", "EFIH", "FWRY", "TMGH", "ORAS", "MASR", "SPMD", "EXPA", "ACGC"]
        ]

    symbol = st.selectbox("🔍 ابحث أو اختر السهم:", stock_list, index=0)

with control_col2:
    history_days = st.slider("عدد جلسات الشارت", min_value=30, max_value=300, value=120, step=10)

with control_col3:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")


# ============================================================
# CHART TOOLS STATE & FULL NEON BLUE BUTTONS
# ============================================================

if "tools" not in st.session_state:
    st.session_state.tools = {
        "sr": True,
        "swing": False,
        "rolling": False,
        "previous": False,
        "fib": False,
        "pivot": False,
        "atr": False,
        "ema": True,
        "bollinger": False,
        "volume": True,
        "rsi": False,
    }

with st.expander("🛠️ إعدادات وأدوات الشارت المتقدمة", expanded=False):
    t1, t2, t3, t4 = st.columns(4)

    tools_map = [
        (t1, "sr", "الدعم والمقاومة"),
        (t1, "swing", "قمم وقيعان Swing"),
        (t1, "rolling", "قمة / قاع 20 و 50 جلسة"),
        (t2, "previous", "مستويات الجلسة السابقة"),
        (t2, "fib", "فيبوناتشي"),
        (t2, "pivot", "نقاط الارتكاز Pivot"),
        (t3, "atr", "وقف المطاردة + Supertrend"),
        (t3, "ema", "EMA 20 / 50 + MA 200"),
        (t3, "bollinger", "Bollinger Bands"),
        (t4, "volume", "حجم التداول"),
        (t4, "rsi", "RSI"),
    ]

    for col, key, label in tools_map:
        with col:
            is_active = st.session_state.tools[key]

            # الزر النشط = type primary (أزرق نيون) والباقي عادي
            if st.button(
                label,
                key=f"btn_{key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.tools[key] = not is_active
                st.rerun()

# Assign variables for chart builder
show_sr = st.session_state.tools["sr"]
show_swing = st.session_state.tools["swing"]
show_rolling = st.session_state.tools["rolling"]
show_previous = st.session_state.tools["previous"]
show_fib = st.session_state.tools["fib"]
show_pivot = st.session_state.tools["pivot"]
show_atr = st.session_state.tools["atr"]
show_ema = st.session_state.tools["ema"]
show_bollinger = st.session_state.tools["bollinger"]
show_volume = st.session_state.tools["volume"]
show_rsi = st.session_state.tools["rsi"]


# ============================================================
# LOAD ANALYSIS DATA
# ============================================================

with st.spinner("جاري تحميل بيانات السوق والتحليل..."):
    try:
        mubasher_prices = load_market_prices()
        market_ctx = load_market_context()
        df, analysis = load_analysis(symbol, mubasher_prices, market_ctx)
    except Exception as e:
        st.error(f"حدث خطأ أثناء التحليل: {e}")
        st.stop()

if df is None or analysis is None:
    st.warning("⚠️ لا توجد بيانات تحليلية كافية لهذا السهم حالياً.")
    st.stop()


# ============================================================
# MAIN METADATA & HERO CARD
# ============================================================

current_price = safe_float(analysis.get("current_price"))
historical_close = safe_float(analysis.get("historical_close"))
change_pct = safe_float(analysis.get("current_vs_close_pct"), 0.0)
source = analysis.get("price_source", "Yahoo Finance")
realtime = bool(analysis.get("is_realtime", False))

trend = trend_description(df)
score = clamp(analysis.get("score", 0))
score_class = score_color(score)
recommendation = analysis.get("rec", "حيادي")

st.markdown(
    f"""
<div class="lm-card">
    <div style="display:flex; justify-content:space-between; align-items:center; gap:20px; direction:rtl;">
        <div>
            <div class="label">أسهم البورصة المصرية</div>
            <div style="font-size:30px; font-weight:800; margin-top:4px;">{symbol}</div>
            <div style="color:#707883; font-size:11px; margin-top:4px;">تحليل مخصص عبر legend-Mo LENS</div>
        </div>
        <div style="text-align:left;">
            <div class="label">السعر الحالي</div>
            <div class="big-value">{fmt(current_price)}</div>
            <div class="{'green' if change_pct >= 0 else 'red'}" style="font-size:12px; font-weight:700; margin-top:5px;">
                {'▲' if change_pct >= 0 else '▼'} {pct(abs(change_pct))}
            </div>
        </div>
    </div>
    <div class="divider"></div>
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; direction:rtl; flex-wrap:wrap;">
        <div>
            <span class="label">مصدر السعر</span><br>
            <span style="font-size:11px; color:#B8BEC6;">{source} {' • مباشر' if realtime else ' • إغلاق سابق'}</span>
        </div>
        <div>
            <span class="label">الإغلاق التاريخي</span><br>
            <span style="font-size:11px; color:#B8BEC6;">{fmt(historical_close)}</span>
        </div>
        <div>
            <span class="label">الاتجاه العام</span><br>
            <span class="yellow" style="font-size:12px; font-weight:700;">{trend}</span>
        </div>
        <div>
            <span class="label">التوصية الإشارية</span><br>
            <span style="font-size:12px; font-weight:700; color:#EDEFF2;">{recommendation}</span>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# ACTIVE SETUPS / PROBABILITY / TRADE PLAN
# ============================================================

st.markdown("## الإعدادات النشطة والخطة")

regime = analysis.get("regime")
if market_ctx:
    breadth_txt = analysis.get("breadth")
    st.caption(
        f"حالة السوق: {REGIME_LABELS.get(regime, '—')}"
        + (f" — {breadth_txt:.0f}% من الأسهم فوق EMA50" if breadth_txt is not None else "")
        + f" | سياق بتاريخ {market_ctx.get('date', '—')}"
    )
else:
    st.caption("⚠️ سياق السوق غير متوفر (يُحفظ تلقائياً بعد تشغيل السكانر). بعض الإعدادات تحتاج القوة النسبية فلن تظهر.")

setups = analysis.get("setups") or []

if not setups:
    st.markdown(
        """<div class="signal-box"><span style="color:#DCE1E6; font-size:12px;">لا يوجد إعداد نشط على آخر إغلاق. المراقبة فقط.</span></div>""",
        unsafe_allow_html=True,
    )
else:
    for s in setups:
        prob = s.get("probability")
        tag = "✅ مُتحقق منه" if s.get("validated") else "⚠️ غير مُتحقق منه (لا يوجد backtest أو لم يجتز الاختبار)"
        hist = ""
        if s.get("hist_win") is not None:
            hist = (
                f"تاريخياً (خارج العينة): نجاح {s['hist_win']:.0f}% • متوسط {safe_float(s.get('hist_exp'), 0):+.2f}% "
                f"بعد التكلفة • {int(s.get('hist_n') or 0)} صفقة"
            )
        prob_txt = f" • احتمالية النموذج {prob * 100:.0f}%" if prob is not None else ""
        gate = "" if s.get("regime_ok", True) else " • ⛔ غير مناسب لحالة السوق الحالية تاريخياً"

        st.markdown(
            f"""
<div class="signal-box" style="margin-bottom:8px;">
    <div style="font-size:14px; font-weight:800;">{s['label']} <span style="font-size:11px; color:#8A929D;">• حتى {s['horizon']} جلسات</span></div>
    <div style="font-size:12px; color:#DCE1E6; margin-top:4px;">{tag}{prob_txt}{gate}</div>
    <div style="font-size:11px; color:#8A929D; margin-top:4px;">{hist}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    p1, p2, p3, p4 = st.columns(4)
    for col, label, value, cls in [
        (p1, "وقف الخسارة", fmt(analysis.get("stop_loss")), "red"),
        (p2, "الهدف الأول TP1", fmt(analysis.get("tp1")), "green"),
        (p3, "الهدف الثاني TP2", fmt(analysis.get("tp2")), "green"),
        (p4, "الكمية المقترحة", f"{int(analysis.get('shares') or 0):,}", "blue"),
    ]:
        with col:
            st.markdown(
                f"""<div class="lm-card"><div class="label">{label}</div><div class="metric-value {cls}">{value}</div></div>""",
                unsafe_allow_html=True,
            )


# ============================================================
# QUICK METRICS
# ============================================================

col1, col2, col3, col4, col5 = st.columns([1.25, 1, 1, 1, 1])

with col1:
    st.markdown(
        f"""
<div class="lm-card" style="height:140px;">
    <div class="score-label">تقييم LENS الشامل</div>
    <div class="score-number {score_class}">{score:.0f}</div>
    <div style="color:#737B85; font-size:11px; margin-top:7px;">/ 100 • {score_text(score)}</div>
    <div class="progress-bg"><div class="progress-fill" style="width:{score:.0f}%;"></div></div>
</div>
""",
        unsafe_allow_html=True,
    )

with col2:
    rsi = safe_float(df["RSI_14"].iloc[-1] if "RSI_14" in df.columns else np.nan)
    st.markdown(f"""<div class="lm-card" style="height:140px;"><div class="label">مؤشر القوة RSI 14</div><div class="metric-value">{fmt(rsi, 1)}</div><div class="metric-sub">الزخم الفني</div></div>""", unsafe_allow_html=True)

with col3:
    adx = safe_float(df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else np.nan)
    st.markdown(f"""<div class="lm-card" style="height:140px;"><div class="label">قوة الاتجاه ADX</div><div class="metric-value">{fmt(adx, 1)}</div><div class="metric-sub">قوة الاتجاه</div></div>""", unsafe_allow_html=True)

with col4:
    volume_ratio = safe_float(df["Volume_Ratio"].iloc[-1] if "Volume_Ratio" in df.columns else np.nan)
    st.markdown(f"""<div class="lm-card" style="height:140px;"><div class="label">معدل حجم التداول</div><div class="metric-value">{fmt(volume_ratio, 2)}x</div><div class="metric-sub">نشاط التداول</div></div>""", unsafe_allow_html=True)

with col5:
    atr_pct = safe_float(df["ATR_Pct"].iloc[-1] if "ATR_Pct" in df.columns else np.nan)
    st.markdown(f"""<div class="lm-card" style="height:140px;"><div class="label">معدل التذبذب ATR</div><div class="metric-value">{fmt(atr_pct, 2)}%</div><div class="metric-sub">قياس المخاطرة</div></div>""", unsafe_allow_html=True)


# ============================================================
# SCORE BREAKDOWN & RADAR
# ============================================================

st.markdown("## تحليل تفصيل النقاط")
left, right = st.columns([1.2, 1])

with left:
    breakdown = {
        "الاتجاه": (analysis.get("trend_score", 0), 20),
        "الزخم": (analysis.get("momentum_score", 0), 15),
        "حجم التداول": (analysis.get("volume_score", 0), 15),
        "حركة السعر": (analysis.get("price_action_score", 0), 15),
        "الدعم والمقاومة": (analysis.get("sr_score", 0), 15),
        "تدفق السيولة": (analysis.get("money_flow_score", 0), 10),
        "التقلبات": (analysis.get("volatility_score", 0), 5),
        "قوة السعر": (analysis.get("price_strength_score", 0), 5),
    }

    rows_html = ""
    for name, (value, maximum) in breakdown.items():
        val = clamp(safe_float(value, 0), 0, maximum)
        percentage = (val / maximum * 100) if maximum else 0
        rows_html += f"""
<div style="margin-bottom:12px;">
    <div style="display:flex; justify-content:space-between; font-size:12px;">
        <span style="color:#B8BEC6;">{name}</span>
        <span style="color:#F1F3F5; font-weight:700;">{val:.1f} / {maximum}</span>
    </div>
    <div class="progress-bg">
        <div class="progress-fill" style="width:{percentage:.1f}%;"></div>
    </div>
</div>
"""

    st.markdown(
        f"""
<div class="lm-card">
    <div class="label">مكونات تقييم legend-Mo LENS</div>
    <div style="height:10px;"></div>
    {rows_html}
</div>
""",
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        """
<div class="lm-card">
    <div class="label">الرادار الفني المتقدم</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        build_radar(analysis),
        use_container_width=True,
        config={"displayModeBar": False},
    )


# ============================================================
# TECHNICAL BALANCE
# ============================================================

st.markdown("## ميزان القوى الفني")
st.caption("مؤشر مركب من نقاط التحليل الفني وليس احتمالاً إحصائياً. الاحتمالات التاريخية الفعلية في قسم الإعدادات النشطة أعلاه.")
scenarios = calculate_scenarios(analysis)
c1, c2, c3 = st.columns(3)

for col, title, value, cls in [
    (c1, "ميل صاعد Bullish", scenarios["Bullish"], "green"),
    (c2, "ميل عرضي Sideways", scenarios["Sideways"], "yellow"),
    (c3, "ميل هابط Bearish", scenarios["Bearish"], "red"),
]:
    with col:
        st.markdown(
            f"""
<div class="scenario">
    <div class="scenario-title">{title}</div>
    <div class="scenario-value {cls}">{value:.0f}%</div>
    <div class="progress-bg"><div class="progress-fill" style="width:{value:.0f}%;"></div></div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# PRICE ACTION LAB
# ============================================================

st.markdown("## معمل الشارت وحركة الأسعار")
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
    config={"displaylogo": False, "scrollZoom": True, "displayModeBar": True, "responsive": True},
)


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

support, resistance = get_basic_levels(df)
st.markdown("## مستويات السوق")
level1, level2 = st.columns(2)

with level1:
    st.markdown(
        f"""
<div class="lm-card">
    <div class="label">أقرب دعم</div>
    <div class="metric-value green" style="font-size:26px;">{fmt(support)}</div>
    <div class="metric-sub">أقرب مستوى دعم أسفل السعر التاريخي</div>
</div>
""",
        unsafe_allow_html=True,
    )

with level2:
    st.markdown(
        f"""
<div class="lm-card">
    <div class="label">أقرب مقاومة</div>
    <div class="metric-value red" style="font-size:26px;">{fmt(resistance)}</div>
    <div class="metric-sub">أقرب مستوى مقاومة أعلى السعر التاريخي</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# SIGNAL DRIVERS
# ============================================================

reasons = analysis.get("reasons", [])
if reasons:
    st.markdown("## أسباب الإشارة")
    for reason in reasons:
        st.markdown(
            f"""
<div class="signal-box" style="margin-bottom:8px;">
    <span style="color:#DCE1E6; font-size:12px;">• {reason}</span>
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
    legend-Mo LENS<br>
    EGX Technical Intelligence<br>
    تم التطوير بواسطة محمد مصطفى (legend-Mo)
</div>
""",
    unsafe_allow_html=True,
)
