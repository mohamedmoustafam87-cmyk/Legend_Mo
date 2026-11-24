"""
signals.py
==========
نفس الكود يُستخدم في (1) الـ backtest على كل التاريخ، و(2) البوت الحي على آخر شمعة.
لذلك اللي بيتقاس هو بالظبط اللي بيتنفذ.

الإعدادات (Setups) مبنية على أدبيات معروفة:
  short_term      مضاربة 1-2 جلسة (اتجاه + زخم + حجم + إغلاق قوي + تدفق أموال)
  mean_reversion  ارتداد قصير داخل اتجاه صاعد (Connors RSI2 + IBS)
  pullback        تصحيح لـ EMA20 داخل اتجاه صاعد لسهم قوي نسبياً (Raschke/Minervini)
  breakout        اختراق قمة 20 جلسة بعد انضغاط تذبذب (VCP / TTM Squeeze / Donchian)
  momentum        قيادة سوقية: قوة نسبية + زخم 12-1 + قرب القمة (O'Neil / Jegadeesh-Titman)

كل Setup له حواجز (Triple Barrier) بوحدات ATR: هدف / وقف / أقصى مدة احتفاظ.
"""

import numpy as np
import pandas as pd

from config import MIN_AVG_DAILY_VALUE


# ==========================================================
# Helpers
# ==========================================================

def _s(df, col):
    return df[col] if col in df.columns else pd.Series(np.nan, index=df.index)


def close_location(df):
    rng = df["High"] - df["Low"]
    return (df["Close"] - df["Low"]) / rng.where(rng > 0)


def liquidity_ok(df):
    return (_s(df, "Traded_Value_20D") >= MIN_AVG_DAILY_VALUE) & (
        _s(df, "Zero_Volume_Days_20") <= 2
    )


def regime_from_breadth(breadth):
    """low <40% | mid 40-60% | high >=60% من الأسهم فوق EMA50."""
    if breadth is None or pd.isna(breadth):
        return "mid"
    if breadth < 40:
        return "low"
    if breadth >= 60:
        return "high"
    return "mid"


REGIME_LABELS = {"low": "🔴 ضعيف", "mid": "🟡 محايد", "high": "🟢 قوي"}


# ==========================================================
# Setups
# ==========================================================

def sig_short_term(df):
    c = df["Close"]
    ema20, ema50 = _s(df, "EMA_20"), _s(df, "EMA_50")
    hist = _s(df, "MACD_Hist")

    trend = (c > ema20) & (ema20 > ema50) & (c > _s(df, "MA_200"))
    momentum = (
        (_s(df, "ADX_14") >= 20)
        & (_s(df, "PLUS_DI") > _s(df, "MINUS_DI"))
        & _s(df, "RSI_14").between(50, 68)
        & (hist > 0)
        & (hist > hist.shift(1))
    )
    volume = _s(df, "Volume_Ratio") >= 1.5
    candle = close_location(df) >= 0.75
    flow = (_s(df, "OBV_Slope_10D") > 0) & (_s(df, "CMF_20") > 0)
    risk = (_s(df, "EMA20_Distance_Pct") <= 6) & (_s(df, "ATR_Pct") <= 6)

    return (trend & momentum & volume & candle & flow & risk & liquidity_ok(df)).fillna(False)


def sig_mean_reversion(df):
    c = df["Close"]
    sig = (
        (c > _s(df, "MA_200"))
        & (_s(df, "RSI_2") <= 10)
        & (c < _s(df, "SMA_5"))
        & (close_location(df) <= 0.30)
        & (_s(df, "Breadth_50") >= 30)       # لا نشتري الارتداد وسط انهيار السوق
        & liquidity_ok(df)
    )
    return sig.fillna(False)


def sig_pullback(df):
    c, o = df["Close"], df["Open"]
    ema20, ema50 = _s(df, "EMA_20"), _s(df, "EMA_50")

    trend = (
        (c > _s(df, "MA_200"))
        & (ema20 > ema50)
        & (_s(df, "EMA50_Slope_10D") > 0)
        & (_s(df, "ADX_14") >= 18)
    )
    pullback = (
        (c / c.shift(3) - 1 < 0)
        & _s(df, "RSI_14").between(38, 55)
        & (df["Low"] <= ema20 * 1.01)
        & (c >= ema50)
    )
    confirm = (c > o) & (close_location(df) >= 0.6)
    strong = _s(df, "RS_Rank_60") >= 50

    return (trend & pullback & confirm & strong & liquidity_ok(df)).fillna(False)


def sig_breakout(df):
    c = df["Close"]
    ema50 = _s(df, "EMA_50")

    trend = (c > ema50) & (ema50 > _s(df, "MA_200"))
    breakout = c > _s(df, "Resistance_20")
    volume = _s(df, "Volume_Ratio") >= 1.5
    candle = close_location(df) >= 0.7
    squeeze = _s(df, "BB_Width_Ratio_120").rolling(10).min().shift(1) <= 0.85
    not_extended = (_s(df, "EMA20_Distance_Pct") <= 8) & (_s(df, "RSI_14") <= 75)
    strong = _s(df, "RS_Rank_60") >= 60

    return (
        trend & breakout & volume & candle & squeeze & not_extended & strong & liquidity_ok(df)
    ).fillna(False)


def sig_momentum(df):
    c = df["Close"]
    ema20, ema50 = _s(df, "EMA_20"), _s(df, "EMA_50")

    stack = (c > ema20) & (ema20 > ema50) & (ema50 > _s(df, "MA_200"))
    leader = (
        (_s(df, "RS_Rank_60") >= 80)
        & (_s(df, "Mom_12_1") > 0)
        & (_s(df, "Position_52W") >= 75)
    )
    quality = (
        (_s(df, "ADX_14") >= 20)
        & _s(df, "RSI_14").between(55, 75)
        & (_s(df, "Volume_Ratio") >= 0.8)
        & (_s(df, "EMA20_Distance_Pct") <= 6)
        & (close_location(df) >= 0.5)
    )

    return (stack & leader & quality & liquidity_ok(df)).fillna(False)


SETUPS = {
    "short_term": {
        "label": "مضاربة 1–2 جلسة", "fn": sig_short_term,
        "horizon": 2, "target_atr": 0.8, "stop_atr": 1.0,
    },
    "mean_reversion": {
        "label": "ارتداد قصير (RSI2)", "fn": sig_mean_reversion,
        "horizon": 5, "target_atr": 1.5, "stop_atr": 2.0,
    },
    "pullback": {
        "label": "تصحيح داخل اتجاه صاعد", "fn": sig_pullback,
        "horizon": 10, "target_atr": 2.5, "stop_atr": 1.5,
    },
    "breakout": {
        "label": "اختراق بعد انضغاط", "fn": sig_breakout,
        "horizon": 10, "target_atr": 3.0, "stop_atr": 1.5,
    },
    "momentum": {
        "label": "قيادة سوقية (قوة نسبية)", "fn": sig_momentum,
        "horizon": 20, "target_atr": 4.0, "stop_atr": 2.0,
    },
}


def compute_signals(df):
    """DataFrame بوليان: عمود لكل Setup."""
    return pd.DataFrame(
        {name: cfg["fn"](df).astype(bool) for name, cfg in SETUPS.items()},
        index=df.index,
    )


# ==========================================================
# Features للنموذج الإحصائي (كلها سببية - بدون تسريب)
# ==========================================================

def feature_frame(df):
    c = df["Close"]
    f = pd.DataFrame(index=df.index)
    f["rsi14"] = _s(df, "RSI_14")
    f["adx"] = _s(df, "ADX_14")
    f["di_diff"] = _s(df, "PLUS_DI") - _s(df, "MINUS_DI")
    f["atr_pct"] = _s(df, "ATR_Pct")
    f["vol_ratio"] = np.log1p(_s(df, "Volume_Ratio"))
    f["ema20_dist"] = _s(df, "EMA20_Distance_Pct")
    f["ema50_dist"] = _s(df, "EMA50_Distance_Pct")
    f["ma200_dist"] = _s(df, "MA200_Distance_Pct")
    f["close_loc"] = close_location(df)
    f["cmf"] = _s(df, "CMF_20")
    f["macd_hist_pct"] = _s(df, "MACD_Hist") / c * 100
    f["roc20"] = _s(df, "ROC_20D")
    f["ret5"] = _s(df, "Return_5D")
    f["pos52"] = _s(df, "Position_52W")
    f["bb_width_ratio"] = _s(df, "BB_Width_Ratio_120")
    f["rs_rank"] = _s(df, "RS_Rank_60")
    f["breadth"] = _s(df, "Breadth_50")
    return f


FEATURES = list(feature_frame(pd.DataFrame({
    "Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0],
})).columns)


# ==========================================================
# Market context (عبر الأسهم): Breadth + Relative Strength Rank
# ==========================================================

def market_context(dfs):
    """
    يضيف لكل DataFrame الأعمدة: RS_60D, RS_Rank_60, Breadth_50
    ويرجع ملخص آخر يوم (للبوت الحي والداشبورد).
    القوة النسبية مقاسة مقابل باقي سوق الأسهم نفسه (بدون الحاجة لمؤشر خارجي).
    """
    if not dfs:
        return {}

    ret60 = pd.DataFrame({t: d["Return_60D"] for t, d in dfs.items()})
    above50 = pd.DataFrame({
        t: (d["Close"] > d["EMA_50"]).astype(float).where(d["Return_60D"].notna())
        for t, d in dfs.items()
    })

    breadth = (above50.mean(axis=1) * 100).where(above50.count(axis=1) >= 10)
    median60 = ret60.median(axis=1)
    rank60 = ret60.rank(axis=1, pct=True) * 100

    for t, d in dfs.items():
        d["RS_60D"] = d["Return_60D"] - median60.reindex(d.index)
        d["RS_Rank_60"] = rank60[t].reindex(d.index)
        d["Breadth_50"] = breadth.reindex(d.index)

    valid = breadth.dropna()
    last_breadth = float(valid.iloc[-1]) if len(valid) else float("nan")
    last_ret = ret60.iloc[-1].dropna()

    return {
        "date": str(ret60.index[-1].date()),
        "breadth50": None if np.isnan(last_breadth) else round(last_breadth, 1),
        "regime": regime_from_breadth(last_breadth),
        "rs_quantiles": (
            [float(x) for x in np.percentile(last_ret, range(101))]
            if len(last_ret) >= 10 else []
        ),
        "median60": float(median60.iloc[-1]) if pd.notna(median60.iloc[-1]) else None,
        "n_stocks": int(len(dfs)),
    }


def attach_context(df, ctx):
    """يلصق سياق السوق الحالي على آخر شمعة فقط (للسهم المفرد: داشبورد / محفظة)."""
    df["Breadth_50"] = np.nan
    df["RS_Rank_60"] = np.nan
    df["RS_60D"] = np.nan

    if not ctx or len(df) == 0:
        return df

    last = df.index[-1]
    if str(ctx.get("date", "")) != last.date().isoformat():
        return df

    if ctx.get("breadth50") is not None:
        df.loc[last, "Breadth_50"] = ctx["breadth50"]

    r = df["Return_60D"].iloc[-1] if "Return_60D" in df.columns else np.nan
    q = ctx.get("rs_quantiles") or []

    if pd.notna(r) and len(q) == 101:
        df.loc[last, "RS_Rank_60"] = float(np.interp(r, q, np.arange(101)))
        if ctx.get("median60") is not None:
            df.loc[last, "RS_60D"] = float(r - ctx["median60"])

    return df
