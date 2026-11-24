"""اختبارات آلية لمحرك القياس — تشغيل:
TELEGRAM_TOKEN=x ADMIN_CHAT_ID=x python3 -m analytics.test_engine
"""

import numpy as np
import pandas as pd

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import calculate_indicators
from analytics.backtest_v2 import _trade_outcome, OUTCOME_STOP, OUTCOME_TP1
from analytics.fee_model import order_fees, SCENARIO_STANDARD


def make_trend_df(n=300, start=10.0, drift=0.001, seed=7):
    """إطار OHLCV تركيبي باتجاه صاعد هادئ."""
    rng = np.random.default_rng(seed)
    closes = start * np.cumprod(1 + drift + rng.normal(0, 0.008, n))
    df = pd.DataFrame({
        "Open": closes * (1 + rng.normal(0, 0.002, n)),
        "High": closes * (1 + abs(rng.normal(0.004, 0.002, n))),
        "Low": closes * (1 - abs(rng.normal(0.004, 0.002, n))),
        "Close": closes,
        "Volume": rng.integers(50_000, 200_000, n).astype(float),
    }, index=pd.date_range("2025-01-01", periods=n, freq="B"))
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    return df


def test_causality():
    """قيم المؤشرات عند t محسوبة على السلسلة الكاملة = محسوبة على المقطع المنتهي عند t."""
    df = make_trend_df()
    full = calculate_indicators(df.copy())
    t = 280
    sliced = calculate_indicators(df.iloc[: t + 1].copy())
    cols = ["MA_200", "EMA_20", "EMA_50", "RSI_14", "ATR", "Vol_SMA20",
            "Resistance_20", "Support_20", "MACD", "MACD_signal"]
    for c in cols:
        a, b = full[c].iloc[t], sliced[c].iloc[-1]
        if pd.isna(a) and pd.isna(b):
            continue
        assert abs(a - b) <= 1e-9 * max(1, abs(a)), f"lookahead in {c}: {a} vs {b}"
    print("PASS causality: indicators at t identical full-series vs truncated")


def test_day_order():
    """ترتيب يوم التنفيذ: فجوة فوق الهدف تملأ بالافتتاح؛ فجوة تحت الوقف تملأ بالافتتاح؛ لمسة مزدوجة = وقف."""
    idx = pd.date_range("2026-01-01", periods=3, freq="B")
    # فجوة افتتاح فوق الهدف
    df1 = pd.DataFrame({"Open": [12.0], "High": [12.5], "Low": [11.5], "Close": [12.2]}, index=idx[:1])
    out = _trade_outcome(df1, 0, stop=9.0, tp1=11.0, horizon_end=5, entry_price=12.0)
    assert out[0] == OUTCOME_TP1 and out[1] == 12.0, out
    # فجوة افتتاح أسفل الوقف
    df2 = pd.DataFrame({"Open": [8.0], "High": [8.5], "Low": [7.5], "Close": [8.2]}, index=idx[:1])
    out = _trade_outcome(df2, 0, stop=9.0, tp1=11.0, horizon_end=5, entry_price=10.0)
    assert out[0] == OUTCOME_STOP and out[1] == 8.0, out
    # لمسة مزدوجة بنفس الجلسة = ليس نجاحًا
    df3 = pd.DataFrame({"Open": [10.0], "High": [11.5], "Low": [8.5], "Close": [10.0]}, index=idx[:1])
    out = _trade_outcome(df3, 0, stop=9.0, tp1=11.0, horizon_end=5, entry_price=10.0)
    assert out[0] == OUTCOME_STOP and out[1] == 9.0, out
    print("PASS day-order: gap-above-TP1 fills at open; gap-below-stop fills at open; dual touch = stop")


def test_fee_model():
    """مطابقة مثال المصدر الرسمي + الثوابت/الحدود الدنيا على الأوامر الصغيرة."""
    assert abs(order_fees(5000, SCENARIO_STANDARD) - 11.75) < 1e-9
    small = order_fees(500, SCENARIO_STANDARD)
    # 2 ثابت + 0.5 عمولة + 0.05 (EGX) + 0.05 (MCDR) + 1 (حد FRA الأدنى) + 0.025 (تأمين) + 0.25 (دمغة) = 3.875
    assert abs(small - 3.875) < 1e-9, small
    print("PASS fee model: official example + small-order fixed/minimum components")


if __name__ == "__main__":
    test_causality()
    test_day_order()
    test_fee_model()
    print("ALL TESTS PASSED")
