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
    .stMarkdown, .stAlert, h1, h2, h3, h4, h5, h6 { direction: rtl; text-align: right; }
    [data-testid="stMetric"] { direction: rtl; text-align: right; }
    .section-title {
        direction: rtl; text-align: right; font-size: 22px;
        font-weight: bold; margin-top: 20px; margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =====================================================================
# CONSTANTS
# =====================================================================
MIN_HISTORY_ROWS = 60
STALE_DAYS = 7              # أكبر من أطول إجازة رسمية عادةً
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
def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def fmt(x, decimals=2, suffix=""):
    v = safe_float(x)
    return "—" if np.isnan(v) else f"{v:,.{decimals}f}{suffix}"


def normalize_stock_list(stocks):
    if stocks is None:
        return []
    if isinstance(stocks, dict):
        return list(stocks.keys())
    if isinstance(stocks, (list, tuple, set)):
        return list(stocks)
    if isinstance(stocks, pd.DataFrame):
        for col in ["ticker", "symbol", "code", "Ticker", "Symbol"]:
            if col in stocks.columns:
                return stocks[col].dropna().astype(str).tolist()
    return []


def find_column(df, candidates):
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def standardize_ohlcv(df):
    """توحيد أسماء الأعمدة مع الحفاظ على التاريخ كـ index (مهم للشارت والفحوصات)."""
    if df is None or len(df) == 0:
        return pd.DataFrame()

    df = df.copy()

    aliases = {
        "Date": ["date", "datetime", "time", "التاريخ"],
        "Open": ["open", "opening", "الفتح"],
        "High": ["high", "الاعلى", "أعلى"],
        "Low": ["low", "الادنى", "أدنى"],
        "Close": ["close", "price", "last", "السعر", "الإغلاق"],
        "Volume": ["volume", "vol", "الحجم", "حجم التداول"],
    }

    rename_map = {}
    for std, cands in aliases.items():
        col = find_column(df, [std] + cands)
        if col is not None and col != std:
            rename_map[col] = std
    df = df.rename(columns=rename_map)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date")
    elif not isinstance(df.index, pd.DatetimeIndex) and not pd.api.types.is_numeric_dtype(df.index):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Close" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["Close"]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "Date"
    return df


def ensure_indicators(df):
    """
    بيكمل أي مؤشر ناقص بعد calculate_indicators (مصدر الحقيقة = indicators.py).
    لا يعيد حساب ولا يكتب فوق أي عمود موجود.
    """
    df = df.copy()
    close = df["Close"]

    if "EMA_20" not in df.columns:
        df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
    if "EMA_50" not in df.columns:
        df["EMA_50"] = close.ewm(span=50, adjust=False).mean()
    if "MA_200" not in df.columns:
        df["MA_200"] = close.rolling(200, min_periods=200).mean()

    if "RSI_14" not in df.columns:
        delta = close.diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI_14"] = 100 - (100 / (1 + rs))

    if "MACD" not in df.columns:
        df["MACD"] = (
            close.ewm(span=12, adjust=False).mean()
            - close.ewm(span=26, adjust=False).mean()
        )
    if "MACD_Signal" not in df.columns:
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    if "ATR14" not in df.columns and all(c in df.columns for c in ["High", "Low"]):
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                df["High"] - df["Low"],
                (df["High"] - prev_close).abs(),
                (df["Low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["ATR14"] = tr.rolling(14).mean()

    if "Volume" in df.columns and "VolumeRatio" not in df.columns:
        vol_ma = df["Volume"].rolling(20).mean()
        df["VolumeRatio"] = df["Volume"] / vol_ma.replace(0, np.nan)

    df["Return_5D"] = close.pct_change(5) * 100
    df["Return_20D"] = close.pct_change(20) * 100
    return df


# =====================================================================
# DATA QUALITY
# =====================================================================
def validate_market_data(df):
    result = {"score": 100, "warnings": []}

    if df is None or df.empty:
        return {"score": 0, "warnings": ["لا توجد بيانات."]}

    if len(df) < MIN_HISTORY_ROWS:
        result["score"] -= 30
        result["warnings"].append(f"عدد الجلسات قليل: {len(df)} جلسة.")
    elif len(df) < 200:
        result["warnings"].append(f"المتاح {len(df)} جلسة فقط، فمتوسط MA 200 غير مكتمل.")

    if isinstance(df.index, pd.DatetimeIndex):
        last_date = df.index.max()
        if pd.notna(last_date):
            age_days = (pd.Timestamp.now().normalize() - last_date.normalize()).days
            if age_days > STALE_DAYS:
                result["score"] -= 35
                result["warnings"].append(f"البيانات قديمة. آخر جلسة: {last_date.date()}")

    if "Volume" in df.columns:
        zero_share = (df["Volume"].fillna(0) <= 0).mean()
        if zero_share > 0.2:
            result["score"] -= 5
            result["warnings"].append(f"{zero_share:.0%} من الجلسات بلا حجم تداول.")

    result["score"] = max(0, min(100, result["score"]))
    return result


# =====================================================================
# MARKET STRUCTURE / SUPPORT-RESISTANCE / RISK
# =====================================================================
def detect_market_structure(df):
    if len(df) < 30:
        return {"trend": "غير كافٍ", "structure": "غير كافٍ"}

    close = df["Close"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    last = close.iloc[-1]
    slope20 = ema20.iloc[-1] - ema20.iloc[-6]
    slope50 = ema50.iloc[-1] - ema50.iloc[-6]

    if last > ema20.iloc[-1] > ema50.iloc[-1] and slope20 > 0 and slope50 > 0:
        trend = "صاعد"
    elif last < ema20.iloc[-1] < ema50.iloc[-1] and slope20 < 0 and slope50 < 0:
        trend = "هابط"
    else:
        trend = "عرضي / انتقالي"

    recent = df.tail(30)
    highs = recent["High"] if "High" in recent.columns else recent["Close"]
    lows = recent["Low"] if "Low" in recent.columns else recent["Close"]

    h1, h2 = highs.iloc[:15].max(), highs.iloc[15:].max()
    l1, l2 = lows.iloc[:15].min(), lows.iloc[15:].min()

    if h2 > h1 and l2 > l1:
        structure = "Higher High / Higher Low"
    elif h2 < h1 and l2 < l1:
        structure = "Lower High / Lower Low"
    else:
        structure = "Mixed Structure"

    return {"trend": trend, "structure": structure}


def _cluster_levels(levels, tolerance):
    """تجميع المستويات المتقاربة. بيرجع [(المستوى, عدد اللمسات)]."""
    clusters = []
    for level in sorted(levels):
        if clusters and abs(level - np.mean(clusters[-1])) / max(np.mean(clusters[-1]), 1e-9) <= tolerance:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    return [(round(float(np.mean(c)), 2), len(c)) for c in clusters]


def find_support_resistance(df, window=SR_WINDOW):
    data = df.tail(window)
    close = data["Close"]
    lows = data["Low"] if "Low" in data.columns else close
    highs = data["High"] if "High" in data.columns else close

    supports, resistances = [], []
    for i in range(2, len(data) - 2):
        if lows.iloc[i] <= lows.iloc[i - 2:i].min() and lows.iloc[i] <= lows.iloc[i + 1:i + 3].min():
            supports.append(float(lows.iloc[i]))
        if highs.iloc[i] >= highs.iloc[i - 2:i].max() and highs.iloc[i] >= highs.iloc[i + 1:i + 3].max():
            resistances.append(float(highs.iloc[i]))

    price = float(close.iloc[-1])

    sup = _cluster_levels([x for x in supports if x < price], SUPPORT_TOLERANCE)
    res = _cluster_levels([x for x in resistances if x > price], RESISTANCE_TOLERANCE)

    sup = sorted(sup, key=lambda x: x[0], reverse=True)[:5]   # الأقرب أولاً
    res = sorted(res, key=lambda x: x[0])[:5]
    return sup, res


def calc_fibonacci(data):
    """تصحيحات فيبوناتشي حسب اتجاه آخر موجة داخل النافذة المعروضة."""
    high_val, low_val = data["High"].max(), data["Low"].min()
    diff = high_val - low_val
    if not np.isfinite(diff) or diff <= 0:
        return {}
    uptrend = data["Low"].values.argmin() < data["High"].values.argmax()
    return {
        r: (high_val - diff * r) if uptrend else (low_val + diff * r)
        for r in (0.382, 0.5, 0.618, 0.786)
    }


def calculate_risk_score(df):
    if df.empty:
        return 100

    close = df["Close"]
    vol = close.pct_change().rolling(20).std().iloc[-1]
    atr = safe_float(df["ATR14"].iloc[-1]) if "ATR14" in df.columns else np.nan
    price = safe_float(close.iloc[-1])

    risk = 40
    if not np.isnan(vol):
        annualized = vol * np.sqrt(252) * 100
        if annualized > 80:
            risk += 30
        elif annualized > 50:
            risk += 20
        elif annualized > 30:
            risk += 10
        else:
            risk -= 5

    if not np.isnan(atr) and price > 0:
        atr_pct = atr / price * 100
        if atr_pct > 8:
            risk += 20
        elif atr_pct > 5:
            risk += 10

    return int(max(0, min(100, risk)))


def risk_label(score):
    if score >= 70:
        return "مخاطرة عالية"
    if score >= 45:
        return "مخاطرة متوسطة"
    return "مخاطرة منخفضة"


# =====================================================================
# DATA LOADING (كاش على التحليل كله)
# =====================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_mubasher():
    try:
        prices = fetch_mubasher_prices()
        return prices if prices else {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(ticker, prices):
    """
    المؤشرات بتتحسب على التاريخ الكامل (مش المعروض بس)،
    والـ strategy بتستلم نفس الـ df ونفس الـ ticker.
    """
    df = standardize_ohlcv(get_stock_data(ticker, prices))
    if df.empty:
        return None, None

    df = calculate_indicators(df)
    df = standardize_ohlcv(df)
    df = ensure_indicators(df)

    analysis = evaluate_stock_strategy(df, ticker)
    return df, analysis


# =====================================================================
# CHART
# =====================================================================
def build_chart(data, ticker, opts, analysis, supports, resistances):
    has_volume = opts["volume"] and "Volume" in data.columns
    has_rsi = opts["rsi"] and "RSI_14" in data.columns

    rows = {"price": 1}
    heights = [0.6]
    if has_volume:
        rows["volume"] = len(rows) + 1
        heights.append(0.2)
    if has_rsi:
        rows["rsi"] = len(rows) + 1
        heights.append(0.2)
    total = sum(heights)
    heights = [h / total for h in heights]

    fig = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=heights,
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index, open=data["Open"], high=data["High"],
            low=data["Low"], close=data["Close"], name=ticker,
        ),
        row=1, col=1,
    )

    if opts["ema20"] and "EMA_20" in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data["EMA_20"], mode="lines",
                                 name="EMA 20", line=dict(color="#FFA726", width=1.6)), row=1, col=1)
    if opts["ema50"] and "EMA_50" in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data["EMA_50"], mode="lines",
                                 name="EMA 50", line=dict(color="#66BB6A", width=1.6)), row=1, col=1)
    if opts["ma200"] and "MA_200" in data.columns and data["MA_200"].notna().any():
        fig.add_trace(go.Scatter(x=data.index, y=data["MA_200"], mode="lines",
                                 name="MA 200", line=dict(color="#29B6F6", width=1.8)), row=1, col=1)

    if opts["support"]:
        main_support = safe_float(analysis.get("support")) if analysis else np.nan
        if not np.isnan(main_support):
            fig.add_hline(y=main_support, line_dash="dash", line_color="green",
                          annotation_text=f"الدعم الرئيسي: {main_support:,.2f}",
                          annotation_position="bottom right", row=1, col=1)
        for level, touches in supports:
            fig.add_hline(y=level, line_dash="dot", line_color="rgba(46,204,113,0.55)",
                          annotation_text=f"S {level:,.2f} ({touches})",
                          annotation_position="bottom left", row=1, col=1)
        for level, touches in resistances:
            fig.add_hline(y=level, line_dash="dot", line_color="rgba(239,83,80,0.55)",
                          annotation_text=f"R {level:,.2f} ({touches})",
                          annotation_position="top left", row=1, col=1)

    if opts["fib"]:
        fib_colors = {0.382: "gold", 0.5: "white", 0.618: "orange", 0.786: "tomato"}
        for ratio, level in calc_fibonacci(data).items():
            fig.add_hline(y=level, line_dash="dot", line_color=fib_colors[ratio],
                          annotation_text=f"Fib {ratio * 100:.1f}%",
                          annotation_position="top right", row=1, col=1)

    if has_volume:
        colors = ["#26A69A" if c >= o else "#EF5350" for o, c in zip(data["Open"], data["Close"])]
        fig.add_trace(go.Bar(x=data.index, y=data["Volume"], marker_color=colors,
                             name="الحجم", showlegend=False), row=rows["volume"], col=1)
        fig.update_yaxes(title_text="الحجم", row=rows["volume"], col=1)

    if has_rsi:
        fig.add_trace(go.Scatter(x=data.index, y=data["RSI_14"], mode="lines",
                                 name="RSI 14", line=dict(color="#AB47BC", width=1.6)),
                      row=rows["rsi"], col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=rows["rsi"], col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=rows["rsi"], col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=rows["rsi"], col=1)

    # إخفاء الجمعة والسبت والعطلات الرسمية
    if isinstance(data.index, pd.DatetimeIndex):
        breaks = [dict(bounds=["fri", "sat"])]
        if EGX_HOLIDAYS:
            try:
                breaks.append(dict(values=[str(pd.to_datetime(h).date()) for h in EGX_HOLIDAYS]))
            except Exception:
                pass
        fig.update_xaxes(rangebreaks=breaks)

    fig.update_yaxes(title_text="السعر (ج.م)", row=1, col=1)
    fig.update_layout(
        template="plotly_dark",
        height=550 + 150 * (len(rows) - 1),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# =====================================================================
# SIDEBAR
# =====================================================================
st.sidebar.title("📊 EGX Smart Dashboard")

stocks = normalize_stock_list(EGX_STOCKS)
if not stocks:
    st.error("لم يتم العثور على EGX_STOCKS في config.py")
    st.stop()

selected_ticker = st.sidebar.selectbox("🔎 اختر أو ابحث عن السهم", stocks, index=0)
history_days = st.sidebar.slider("عدد الجلسات المعروضة", 60, 500, 120, 10)

if st.sidebar.button("🔄 تحديث البيانات"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.header("⚙️ أدوات الشارت")
opts = {
    "ema20": st.sidebar.checkbox("EMA 20", value=True),
    "ema50": st.sidebar.checkbox("EMA 50", value=False),
    "ma200": st.sidebar.checkbox("MA 200", value=True),
    "support": st.sidebar.checkbox("الدعم والمقاومة", value=True),
    "fib": st.sidebar.checkbox("فيبوناتشي (Fibonacci)", value=False),
    "volume": st.sidebar.checkbox("حجم التداول (Volume)", value=True),
    "rsi": st.sidebar.checkbox("مؤشر RSI", value=True),
}


# =====================================================================
# HEADER + LOAD
# =====================================================================
st.title(f"📈 {selected_ticker} — EGX Smart Dashboard")
st.caption("تحليل فني متعدد العوامل مع فحص جودة البيانات")

mubasher_prices = load_mubasher()
if not mubasher_prices:
    st.warning("⚠️ تعذر جلب الأسعار اللحظية من مباشر، سيتم الاعتماد على باقي مصادر البيانات.")

with st.spinner(f"جاري جلب وتحليل بيانات السهم {selected_ticker}..."):
    try:
        df, analysis = load_analysis(selected_ticker, mubasher_prices)
    except Exception as e:
        st.error(f"⚠️ حدث خطأ أثناء تحليل السهم {selected_ticker}: {e}")
        st.stop()

if df is None or df.empty:
    st.error(f"⚠️ تعذر جلب بيانات كافية للسهم {selected_ticker}")
    st.stop()

missing = [c for c in ["Open", "High", "Low", "Close"] if c not in df.columns]
if missing:
    st.error(f"⚠️ أعمدة ناقصة في البيانات: {', '.join(missing)}")
    st.stop()


# =====================================================================
# DATA QUALITY
# =====================================================================
quality = validate_market_data(df)
q = quality["score"]
if q >= 80:
    st.success(f"🟢 جودة البيانات: {q}/100")
elif q >= 60:
    st.warning(f"🟠 جودة البيانات: {q}/100")
else:
    st.error(f"🔴 جودة البيانات منخفضة: {q}/100 — التوصيات قد لا تكون موثوقة")

if quality["warnings"]:
    with st.expander("تفاصيل جودة البيانات"):
        for w in quality["warnings"]:
            st.write(f"• {w}")

if analysis is None:
    st.warning("⚠️ لا توجد بيانات كافية لتشغيل محرك الاستراتيجية على هذا السهم.")


# =====================================================================
# CURRENT VALUES
# =====================================================================
last = df.iloc[-1]
last_close = safe_float(last["Close"])
current_price = safe_float(analysis.get("price")) if analysis else np.nan
if np.isnan(current_price):
    current_price = last_close

prev_close = safe_float(df["Close"].iloc[-2]) if len(df) >= 2 else np.nan
daily_change = (
    (last_close - prev_close) / prev_close * 100
    if not np.isnan(prev_close) and prev_close != 0 else np.nan
)

rsi = safe_float(last.get("RSI_14"))
volume_ratio = safe_float(last.get("VolumeRatio"))
risk_score = calculate_risk_score(df)

structure_data = detect_market_structure(df)
supports, resistances = find_support_resistance(df)


# =====================================================================
# TOP METRICS
# =====================================================================
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("السعر الحالي", fmt(current_price, 2, " ج.م"),
              f"{daily_change:+.2f}%" if not np.isnan(daily_change) else None)
with c2:
    if analysis:
        st.metric("التقييم (Score)", f"{analysis.get('score', '—')} / 100",
                  analysis.get("rec", ""), delta_color="off")
    else:
        st.metric("التقييم (Score)", "—")
with c3:
    st.metric("مؤشر RSI", fmt(rsi, 1))
with c4:
    st.metric("مستوى الدعم الرئيسي", fmt(analysis.get("support") if analysis else None, 2, " ج.م"))
with c5:
    st.metric("درجة المخاطرة", f"{risk_score}/100", risk_label(risk_score), delta_color="off")

st.markdown("---")


# =====================================================================
# MARKET STRUCTURE
# =====================================================================
st.markdown('<div class="section-title">📐 هيكل السوق</div>', unsafe_allow_html=True)
m1, m2, m3 = st.columns(3)
with m1:
    st.info(f"الاتجاه الحالي: **{structure_data['trend']}**")
with m2:
    st.info(f"الهيكل السعري: **{structure_data['structure']}**")
with m3:
    st.info(f"نسبة الحجم للمتوسط: **{fmt(volume_ratio, 2, 'x')}**")


# =====================================================================
# CHART
# =====================================================================
st.subheader(f"📊 الرسم البياني التفاعلي لـ {selected_ticker}")
chart_df = df.tail(history_days)
fig = build_chart(chart_df, selected_ticker, opts, analysis, supports, resistances)
st.plotly_chart(fig, use_container_width=True)


# =====================================================================
# RECOMMENDATIONS + RISK MANAGEMENT (من محرك الاستراتيجية)
# =====================================================================
if analysis:
    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🎯 التوصيات والأهداف الاستثمارية")
        st.info(f"**منطقة الدخول المقترحة:** {analysis.get('ideal_entry', '—')} - {analysis.get('entry_high', '—')} ج.م")
        st.success(f"**الهدف الأول (TP1):** {analysis.get('tp1', '—')} ج.م (المدة: {analysis.get('days_tp1_text', '—')})")
        st.success(f"**الهدف الثاني (TP2):** {analysis.get('tp2', '—')} ج.م (المدة: {analysis.get('days_tp2_text', '—')})")

    with col_b:
        st.subheader("🛑 إدارة المخاطر والخروج")
        st.warning(f"**وقف الخسارة (Stop Loss):** {analysis.get('stop_loss', '—')} ج.م ({fmt(analysis.get('stop_loss_pct'), 2, '%')})")
        st.error(f"**خطة الخروج:** {analysis.get('exit_strategy', '—')}")

    st.subheader("💡 الأسباب والتحليل الفني التفصيلي:")
    for reason in analysis.get("reasons", []):
        st.write(f"- {reason}")


# =====================================================================
# SUPPORT / RESISTANCE TABLE
# =====================================================================
st.markdown('<div class="section-title">🎯 مستويات الدعم والمقاومة</div>', unsafe_allow_html=True)
s_col, r_col = st.columns(2)

with s_col:
    st.subheader("🟢 الدعوم")
    if supports:
        for level, touches in supports:
            dist = (current_price - level) / current_price * 100
            st.write(f"**{level:,.2f}** — المسافة {dist:.1f}% — لمسات: {touches}")
    else:
        st.write("لا توجد مستويات دعم كافية.")

with r_col:
    st.subheader("🔴 المقاومات")
    if resistances:
        for level, touches in resistances:
            dist = (level - current_price) / current_price * 100
            st.write(f"**{level:,.2f}** — المسافة {dist:.1f}% — لمسات: {touches}")
    else:
        st.write("لا توجد مستويات مقاومة كافية.")


# =====================================================================
# SCENARIOS
# =====================================================================
st.markdown('<div class="section-title">🔮 السيناريوهات الفنية</div>', unsafe_allow_html=True)

st.markdown("### 🟢 السيناريو الإيجابي")
if resistances:
    nxt = f" ثم المقاومة التالية **{resistances[1][0]:,.2f}**" if len(resistances) > 1 else ""
    st.write(f"اختراق المقاومة الأقرب **{resistances[0][0]:,.2f}** بإغلاق واضح والثبات فوقها، تتم مراقبة{nxt or ' المستويات الأعلى'}.")
else:
    st.write("لا توجد مقاومة آلية كافية.")

st.markdown("### 🔴 السيناريو السلبي")
if supports:
    st.write(f"كسر الدعم الأقرب **{supports[0][0]:,.2f}** بإغلاق واضح يستدعي إعادة تقييم الاتجاه.")
else:
    st.write("لا يوجد دعم آلي كافٍ.")


# =====================================================================
# INDICATORS TABLE + RAW DATA
# =====================================================================
st.markdown('<div class="section-title">📌 المؤشرات الفنية</div>', unsafe_allow_html=True)

indicator_rows = [
    ("السعر (آخر إغلاق)", last_close, 2),
    ("EMA 20", last.get("EMA_20"), 2),
    ("EMA 50", last.get("EMA_50"), 2),
    ("MA 200", last.get("MA_200"), 2),
    ("RSI 14", rsi, 1),
    ("MACD", last.get("MACD"), 4),
    ("MACD Signal", last.get("MACD_Signal"), 4),
    ("ATR 14", last.get("ATR14"), 3),
    ("نسبة الحجم", volume_ratio, 2),
    ("عائد 5 جلسات %", last.get("Return_5D"), 2),
    ("عائد 20 جلسة %", last.get("Return_20D"), 2),
]
st.dataframe(
    pd.DataFrame({
        "المؤشر": [r[0] for r in indicator_rows],
        "القيمة": [fmt(r[1], r[2]) for r in indicator_rows],   # نصوص كلها لتفادي خطأ Arrow
    }),
    use_container_width=True,
    hide_index=True,
)

with st.expander("📋 عرض البيانات التاريخية"):
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume", "EMA_20", "EMA_50",
                        "MA_200", "RSI_14", "MACD", "MACD_Signal", "ATR14", "VolumeRatio"]
            if c in df.columns]
    st.dataframe(df[cols].tail(100).sort_index(ascending=False), use_container_width=True)


# =====================================================================
# DISCLAIMER
# =====================================================================
st.markdown("---")
st.caption(
    "⚠️ هذه اللوحة أداة مساعدة للتحليل الفني فقط، وما تعرضه من توصيات وأهداف ليس نصيحة "
    "استثمارية. النتائج تعتمد على جودة البيانات ولا تضمن حركة السعر المستقبلية."
)
