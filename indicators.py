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
    MIN_HISTORY_ROWS,
)


# ==========================================================
# Helpers
# ==========================================================

def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def _wilder(series, n):
    return series.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(close, n):
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0), n)
    loss = _wilder((-delta.clip(upper=0)), n)
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    # لا توجد خسائر نهائياً -> RSI = 100 (النسخة القديمة كانت تعطي NaN)
    return rsi.where(~((loss == 0) & (gain > 0)), 100.0)


def _supertrend(high, low, close, atr, mult=3.0):
    """Supertrend (Olivier Seban). يرجع (الخط، الاتجاه: +1 صاعد / -1 هابط)."""
    hl2 = ((high + low) / 2).to_numpy()
    a = atr.to_numpy()
    c = close.to_numpy()
    upper = hl2 + mult * a
    lower = hl2 - mult * a
    n = len(c)
    fu, fl = upper.copy(), lower.copy()
    trend = np.ones(n, dtype=int)

    for i in range(1, n):
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]

        if trend[i - 1] == -1 and c[i] > fu[i - 1]:
            trend[i] = 1
        elif trend[i - 1] == 1 and c[i] < fl[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    line = np.where(trend == 1, fl, fu)
    return pd.Series(line, index=high.index), pd.Series(trend, index=high.index)


def _pct(a, b):
    return (a / b.replace(0, np.nan) - 1) * 100


# ==========================================================
# Main Indicators
# ==========================================================

def calculate_indicators(df):

    if df is None or df.empty:
        return None

    df = df.copy()
    attrs = dict(getattr(df, "attrs", {}))

    ohlcv = ["Open", "High", "Low", "Close", "Volume"]

    for col in ohlcv:
        if col not in df.columns:
            return None
        df[col] = safe_numeric(df[col])

    df = df.dropna(subset=ohlcv)

    if len(df) < MIN_HISTORY_ROWS:
        return None

    o, h, l, c, v = (df[x] for x in ohlcv)

    # ---------------- Moving averages ----------------
    df["SMA_5"] = c.rolling(5).mean()
    df["SMA_50"] = c.rolling(50).mean()
    df["SMA_200"] = c.rolling(MA_LONG).mean()
    df["MA_200"] = df["SMA_200"]
    df["EMA_20"] = c.ewm(span=EMA_FAST, adjust=False).mean()
    df["EMA_50"] = c.ewm(span=EMA_SLOW, adjust=False).mean()

    # ---------------- RSI ----------------
    df["RSI_14"] = _rsi(c, RSI_PERIOD)
    df["RSI_2"] = _rsi(c, 2)          # Connors RSI(2)

    # ---------------- True range / ATR ----------------
    prev_close = c.shift(1)
    df["True_Range"] = pd.concat(
        [h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1
    ).max(axis=1)
    df["ATR_14"] = _wilder(df["True_Range"], ATR_PERIOD)
    df["ATR_Pct"] = df["ATR_14"] / c * 100

    # ---------------- MACD ----------------
    macd = (
        c.ewm(span=MACD_FAST, adjust=False).mean()
        - c.ewm(span=MACD_SLOW, adjust=False).mean()
    )
    df["MACD"] = macd
    df["MACD_Signal"] = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    df["MACD_Bullish_Cross"] = (df["MACD"] > df["MACD_Signal"]) & (
        df["MACD"].shift(1) <= df["MACD_Signal"].shift(1)
    )
    df["MACD_Bearish_Cross"] = (df["MACD"] < df["MACD_Signal"]) & (
        df["MACD"].shift(1) >= df["MACD_Signal"].shift(1)
    )

    # ---------------- ADX / DI (Wilder) ----------------
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index
    )
    atr_adx = _wilder(df["True_Range"], ADX_PERIOD)
    plus_di = 100 * _wilder(plus_dm, ADX_PERIOD) / atr_adx
    minus_di = 100 * _wilder(minus_dm, ADX_PERIOD) / atr_adx
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di
    df["ADX_14"] = _wilder(dx, ADX_PERIOD)

    # ---------------- Volume ----------------
    df["Volume_SMA_20"] = v.rolling(VOLUME_MA_PERIOD).mean()
    df["Volume_Ratio"] = v / df["Volume_SMA_20"].replace(0, np.nan)
    df["Traded_Value_20D"] = (c * v).rolling(20, min_periods=10).median()
    df["Zero_Volume_Days_20"] = (v <= 0).astype(float).rolling(20, min_periods=10).sum()

    # ---------------- OBV ----------------
    direction = np.sign(c.diff()).fillna(0)
    df["OBV"] = (direction * v).cumsum()
    df["OBV_EMA_20"] = df["OBV"].ewm(span=20, adjust=False).mean()
    df["OBV_Slope_10D"] = df["OBV"] - df["OBV"].shift(10)
    df["OBV_Bullish"] = df["OBV"] > df["OBV_EMA_20"]

    # ---------------- A/D line, CMF ----------------
    hl_range = (h - l).replace(0, np.nan)
    mfm = (((c - l) - (h - c)) / hl_range).fillna(0)
    mfv = mfm * v
    df["AD_LINE"] = mfv.cumsum()
    df["AD_Slope_20D"] = df["AD_LINE"] - df["AD_LINE"].shift(20)
    df["CMF_20"] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    # ---------------- MFI ----------------
    tp = (h + l + c) / 3
    raw_mf = tp * v
    tp_chg = tp.diff()
    pos_flow = raw_mf.where(tp_chg > 0, 0).rolling(14).sum()
    neg_flow = raw_mf.where(tp_chg < 0, 0).abs().rolling(14).sum()
    df["MFI_14"] = 100 - 100 / (1 + pos_flow / neg_flow.replace(0, np.nan))

    # ---------------- ROC / Returns / Momentum ----------------
    for n in (5, 20, 60):
        df[f"ROC_{n}D"] = c.pct_change(n) * 100
        df[f"Return_{n}D"] = df[f"ROC_{n}D"]
    # زخم 12-1 (Jegadeesh & Titman): عائد 12 شهر مع تجاهل آخر شهر
    df["Mom_12_1"] = (c.shift(21) / c.shift(252) - 1) * 100

    # ---------------- 52 week ----------------
    df["High_52W"] = h.rolling(252).max()
    df["Low_52W"] = l.rolling(252).min()
    rng52 = (df["High_52W"] - df["Low_52W"]).replace(0, np.nan)
    df["Position_52W"] = (c - df["Low_52W"]) / rng52 * 100

    # ---------------- Support / Resistance (shift(1) = بدون تسريب) ----------------
    p = SUPPORT_RESISTANCE_PERIOD
    df["Resistance_20"] = h.rolling(p).max().shift(1)
    df["Support_20"] = l.rolling(p).min().shift(1)
    df["Resistance_50"] = h.rolling(50).max().shift(1)
    df["Support_50"] = l.rolling(50).min().shift(1)
    df["Distance_From_Support_Pct"] = (c - df["Support_20"]) / c * 100
    df["Distance_From_Resistance_Pct"] = (df["Resistance_20"] - c) / c * 100

    df["Breakout_20"] = c > df["Resistance_20"]
    df["Breakdown_20"] = c < df["Support_20"]
    df["Breakout_With_Volume"] = df["Breakout_20"] & (df["Volume_Ratio"] >= 1.2)

    # ---------------- Bollinger / Keltner / Squeeze ----------------
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df["BB_MIDDLE"] = bb_mid
    df["BB_UPPER"] = bb_mid + 2 * bb_std
    df["BB_LOWER"] = bb_mid - 2 * bb_std
    bb_width = df["BB_UPPER"] - df["BB_LOWER"]
    df["BB_WIDTH_PCT"] = bb_width / bb_mid * 100
    df["BB_POSITION"] = (c - df["BB_LOWER"]) / bb_width.replace(0, np.nan) * 100
    # انضغاط التذبذب مقارنة بوسيطه خلال 120 جلسة (VCP / TTM Squeeze)
    df["BB_Width_Ratio_120"] = df["BB_WIDTH_PCT"] / df["BB_WIDTH_PCT"].rolling(
        120, min_periods=60
    ).median()
    kc_u = df["EMA_20"] + 1.5 * df["ATR_14"]
    kc_l = df["EMA_20"] - 1.5 * df["ATR_14"]
    df["Squeeze_On"] = (df["BB_UPPER"] < kc_u) & (df["BB_LOWER"] > kc_l)

    # ---------------- Distances / slopes ----------------
    df["EMA20_Distance_Pct"] = _pct(c, df["EMA_20"])
    df["EMA50_Distance_Pct"] = _pct(c, df["EMA_50"])
    df["MA200_Distance_Pct"] = _pct(c, df["MA_200"])
    df["EMA50_Slope_10D"] = df["EMA_50"] - df["EMA_50"].shift(10)
    df["EMA20_Slope_5D"] = df["EMA_20"] - df["EMA_20"].shift(5)
    df["MA200_Slope_20D"] = df["MA_200"] - df["MA_200"].shift(20)
    df["ADX_Slope_5D"] = df["ADX_14"] - df["ADX_14"].shift(5)

    # ---------------- Candles ----------------
    body = c - o
    rng = (h - l).replace(0, np.nan)
    upper_shadow = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_shadow = pd.concat([o, c], axis=1).min(axis=1) - l
    df["Candle_Body_Pct"] = body.abs() / rng * 100
    df["Upper_Shadow_Pct"] = upper_shadow / rng * 100
    df["Lower_Shadow_Pct"] = lower_shadow / rng * 100
    df["Close_Location"] = (c - l) / rng          # IBS
    df["Gap_Pct"] = (o / prev_close - 1) * 100
    df["Bullish_Candle"] = c > o
    df["Bearish_Candle"] = c < o
    df["Hammer"] = (
        (df["Lower_Shadow_Pct"] >= 50)
        & (df["Upper_Shadow_Pct"] <= 25)
        & (df["Candle_Body_Pct"] <= 40)
    )
    df["Strong_Bullish_Candle"] = (c > o) & (df["Candle_Body_Pct"] >= 60)
    prev_open = o.shift(1)
    df["Bullish_Engulfing"] = (
        (prev_close < prev_open) & (c > o) & (o <= prev_close) & (c >= prev_open)
    )

    # ---------------- Trailing exits ----------------
    df["High_22"] = h.rolling(22).max()
    df["Chandelier_22"] = df["High_22"] - 3 * df["ATR_14"]   # LeBeau Chandelier Exit
    st_line, st_dir = _supertrend(h, l, c, df["ATR_14"], 3.0)
    df["Supertrend"] = st_line
    df["Supertrend_Dir"] = st_dir

    # ---------------- Trend / momentum / money-flow flags ----------------
    df["Above_EMA20"] = c > df["EMA_20"]
    df["Above_EMA50"] = c > df["EMA_50"]
    df["Above_MA200"] = c > df["MA_200"]
    df["EMA20_Above_EMA50"] = df["EMA_20"] > df["EMA_50"]
    df["DI_Bullish"] = df["PLUS_DI"] > df["MINUS_DI"]

    df["Momentum_Bullish"] = (
        (df["RSI_14"] > 50) & (df["MACD"] > df["MACD_Signal"]) & (df["ROC_20D"] > 0)
    )
    df["Momentum_Bearish"] = (
        (df["RSI_14"] < 50) & (df["MACD"] < df["MACD_Signal"]) & (df["ROC_20D"] < 0)
    )
    df["Money_Flow_Bullish"] = (
        (df["CMF_20"] > 0) & (df["OBV"] > df["OBV_EMA_20"]) & (df["AD_Slope_20D"] > 0)
    )
    df["Money_Flow_Bearish"] = (
        (df["CMF_20"] < 0) & (df["OBV"] < df["OBV_EMA_20"]) & (df["AD_Slope_20D"] < 0)
    )

    df = df.replace([np.inf, -np.inf], np.nan)
    df.attrs.update(attrs)

    return df


# ==========================================================
# Candlestick Analysis
# ==========================================================

def analyze_candlesticks(df):

    if df is None or df.empty:
        return []

    last = df.iloc[-1]
    reasons = []

    if bool(last.get("Hammer", False)):
        reasons.append("ظهور شمعة Hammer")
    if bool(last.get("Bullish_Engulfing", False)):
        reasons.append("ظهور Bullish Engulfing")
    if bool(last.get("Strong_Bullish_Candle", False)):
        reasons.append("شمعة صاعدة قوية")

    return reasons
