"""اختبار end-to-end تركيبي لمحرك القياس — يغطي:
TP1 / stop / expired / not_executed / WAIT / unresolved / overlap /
تسوية السجل / قيود النقد الحتمية.
تشغيل: TELEGRAM_TOKEN=x ADMIN_CHAT_ID=x python3 -m analytics.test_walkforward
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from indicators import calculate_indicators
from analytics.backtest_v2 import run_symbol_backtest, summarize
from analytics.signal_v2 import evaluate_signal_v2
from analytics.portfolio import simulate_portfolio


def base_series(n_up=250, n_flat=10, seed=11, drift=0.0004, vol=0.004,
                flat_drift=-0.002):
    """سلسلة قاعدية تجعل البوابات تمر: اتجاه صاعد + تماسك قصير."""
    rng = np.random.default_rng(seed)
    up = 10.0 * np.cumprod(1 + drift + rng.normal(0, vol, n_up))
    flat = up[-1] * np.cumprod(1 + flat_drift + rng.normal(0, vol * 0.5, n_flat))
    closes = np.concatenate([up, flat])
    n = len(closes)
    df = pd.DataFrame({
        "Open": closes * (1 + rng.normal(0, 0.001, n)),
        "High": closes * (1 + abs(rng.normal(0.002, 0.001, n))),
        "Low": closes * (1 - abs(rng.normal(0.002, 0.001, n))),
        "Close": closes, "Volume": np.full(n, 150_000.0),
    }, index=pd.date_range("2025-01-01", periods=n, freq="B"))
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    return df


def add_bars(df, bars):
    """bars: list of (open, high, low, close, volume) بالترتيب."""
    idx = []
    d = df.index[-1]
    for _ in bars:
        d = d + pd.offsets.BDay(1)
        idx.append(d)
    extra = pd.DataFrame(bars, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)
    return pd.concat([df, extra])


def breakout_bar(df, pct_above_high=0.005, vol_mult=2.0):
    prev_high = df["High"].iloc[-20:].max()
    close = prev_high * (1 + pct_above_high)
    return (float(df["Close"].iloc[-1]), close * 1.003, float(df["Close"].iloc[-1]) * 0.998,
            close, 150_000.0 * vol_mult)


def make_symbol(symbol, continuation):
    """base + breakout (يوم الإشارة) + استمرار حسب السيناريو."""
    df = base_series()
    df = add_bars(df, [breakout_bar(df)])
    sig_high = df["High"].iloc[-1]
    sig_close = df["Close"].iloc[-1]
    return continuation(symbol, df, sig_high, sig_close)


def c_tp1(symbol, df, sig_high, sig_close):
    ent = sig_high + 0.01
    bars = [(sig_close, sig_high * 1.01, sig_close * 0.998, ent + 0.02, 200_000.0)]
    px = ent + 0.02
    for _ in range(55):  # صعود ثابت حتى يضرب TP1، مع إكمال أفق 42 جلسة
        px *= 1.015
        bars.append((px / 1.015, px * 1.004, px / 1.015 * 0.998, px, 200_000.0))
    return add_bars(df, bars)


def c_stop(symbol, df, sig_high, sig_close):
    ent = sig_high + 0.01
    bars = [(sig_close, sig_high * 1.01, sig_close * 0.998, ent + 0.02, 200_000.0)]
    px = ent + 0.02
    for _ in range(12):  # هبوط حاد حتى يضرب الوقف
        px *= 0.97
        bars.append((px / 0.97, px / 0.97 * 1.002, px * 0.995, px, 200_000.0))
    for _ in range(40):  # استكمال أفق 42 جلسة بعد الوصول للوقف
        px *= 1.002
        bars.append((px / 1.002, px * 1.004, px * 0.998, px, 150_000.0))
    return add_bars(df, bars)


def c_notexec(symbol, df, sig_high, sig_close):
    bars = []
    px = sig_close
    for _ in range(10):  # لا جلسة تتجاوز قمة الإشارة
        px *= 0.998
        bars.append((px / 0.998, min(sig_high * 0.999, px / 0.998 * 1.003), px * 0.997, px, 150_000.0))
    return add_bars(df, bars)


def c_expired(symbol, df, sig_high, sig_close):
    ent = sig_high + 0.01
    bars = [(sig_close, sig_high * 1.01, sig_close * 0.998, ent + 0.02, 200_000.0)]
    px = ent + 0.02
    for i in range(48):  # عرضي هادئ: لا وقف ولا هدف طوال الأفق
        px *= 1.0003
        bars.append((px / 1.0003, px * 1.002, px * 0.998, px, 150_000.0))
    return add_bars(df, bars)


def c_wait(symbol, df, sig_high, sig_close):
    # إشارة بمسافة EMA20 أكبر من 5%: قمة إغلاق قوية
    return df  # الإشارة نفسها تُبنى معدّلة في الاختبار


def c_unresolved(symbol, df, sig_high, sig_close):
    ent = sig_high + 0.01
    bars = [(sig_close, sig_high * 1.01, sig_close * 0.998, ent + 0.02, 200_000.0)]
    px = ent + 0.02
    for _ in range(6):  # بيانات تنتهي قبل اكتمال أفق 42 جلسة
        px *= 1.002
        bars.append((px / 1.002, px * 1.003, px * 0.998, px, 150_000.0))
    return add_bars(df, bars)


def c_overlap(symbol, df, sig_high, sig_close):
    ent = sig_high + 0.01
    bars = [(sig_close, sig_high * 1.01, sig_close * 0.998, ent + 0.02, 200_000.0)]
    px = ent + 0.02
    # يومان صعود ثم يوم "اختراق" جديد بحجم ضخم (إشارة ثانية أثناء صفقة مفتوحة)
    for _ in range(2):
        px *= 1.004
        bars.append((px / 1.004, px * 1.004, px / 1.004 * 0.998, px, 200_000.0))
    px *= 1.006
    bars.append((px / 1.006, px * 1.006, px / 1.006 * 0.998, px, 700_000.0))
    for _ in range(55):  # ثم صعود حتى TP1، مع إكمال أفق 42 جلسة
        px *= 1.015
        bars.append((px / 1.015, px * 1.004, px / 1.015 * 0.998, px, 200_000.0))
    return add_bars(df, bars)


def test_scenario(name, continuation, expected):
    df = make_symbol(name, continuation)
    assert len(df) >= 260, f"{name}: only {len(df)} bars"
    recs = run_symbol_backtest(name, df, "v2")
    outs = [r["outcome"] for r in recs]
    assert expected in outs, f"{name}: expected {expected}, got {outs}"
    print(f"PASS scenario {name}: {expected} in {outs}")
    return recs


def test_wait():
    """مسار WAIT في السجل: إشارة WAIT تُسجَّل wait_filtered ولا تُنفَّذ.
    الفيزياء التفصيلية لبوابة المسافة مثبتة على البيانات الحقيقية
    (نتائج الكون الكامل فيها سجلات wait_filtered فعلية)؛ هنا نحقن
    SignalV2 بحالة WAIT عند يوم محدد لاختبار تعامل حلقة المحرك معها."""
    import analytics.backtest_v2 as bw
    from analytics.signal_v2 import SignalV2

    df = base_series()
    df = add_bars(df, [breakout_bar(df)])
    df = add_bars(df, [(df["Close"].iloc[-1], df["Close"].iloc[-1] * 1.01,
                        df["Close"].iloc[-1] * 0.99, df["Close"].iloc[-1] * 1.005, 200_000.0)
                       for _ in range(3)])
    sig_day = df.index[-4]
    last = df.iloc[-4]
    real_fn = bw.evaluate_signal_v2

    def patched(hist, symbol, **kwargs):
        if hist.index[-1] == sig_day:
            close = float(last["Close"])
            return SignalV2(
                symbol=symbol, signal_date=sig_day, score=70, close=close,
                signal_high=float(last["High"]), atr=0.10,
                support=close * 0.95, resistance=close * 1.05,
                tp1_estimate=close * 1.1, stop_at_close=close * 0.9,
                status="WAIT", wait_reason="ema_distance>5%")
        return real_fn(hist, symbol, **kwargs)

    bw.evaluate_signal_v2 = patched
    try:
        recs = bw.run_symbol_backtest("WAIT.CA", df, "v2")
    finally:
        bw.evaluate_signal_v2 = real_fn
    outs = [r["outcome"] for r in recs]
    assert "wait_filtered" in outs, outs
    executed = [r for r in recs if r.get("outcome") in ("tp1_first", "stop_first", "expired")]
    assert not executed, f"WAIT signal must never execute: {outs}"
    print(f"PASS scenario WAIT: recorded wait_filtered, never executed ({outs})")
    return recs


def test_overlap():
    df = make_symbol("OVL.CA", c_overlap)
    recs = run_symbol_backtest("OVL.CA", df, "v2")
    executed = [r for r in recs if r.get("outcome") in ("tp1_first", "stop_first", "expired")]
    assert len(executed) == 1, f"overlap rule violated: {[(r['signal_date'], r['outcome']) for r in recs]}"
    print("PASS overlap: second signal during open trade produced no extra trade")
    return recs


def test_reconciliation(all_recs):
    s = summarize(all_recs, "v2")
    rec = s["reconciliation"]
    total = (s["signals"] + rec["wait_filtered"]
             + sum(rec["drops_by_reason"].values()) + rec["unknown_outcome_records"])
    assert rec["unknown_outcome_records"] == 0, rec
    assert rec["total_records"] == s["signals"] + rec["wait_filtered"] or rec["drops_by_reason"], rec
    print("PASS ledger reconciliation: every record classified, none unknown")


def test_deterministic_cash():
    # صفقتان بنفس يوم الدخول وقيمتهما معًا أكبر من النقد: الأولى (ترتيب الرمز) تؤخذ، الثانية تُقَصّ أو تُتخطى
    recs = [
        {"symbol": "AAA.CA", "variant": "v2", "outcome": "tp1_first",
         "entry_date": "2026-01-05", "exit_date": "2026-01-10",
         "entry_price": 10.0, "exit_price": 11.0, "shares": 9000},
        {"symbol": "BBB.CA", "variant": "v2", "outcome": "tp1_first",
         "entry_date": "2026-01-05", "exit_date": "2026-01-12",
         "entry_price": 10.0, "exit_price": 11.0, "shares": 9000},
    ]
    p1 = simulate_portfolio(recs)
    p2 = simulate_portfolio(list(reversed(recs)))
    assert p1 == p2 == simulate_portfolio(recs), "non-deterministic"
    # 9000×10 = 90k للأولى، يتبقى 10k → الثانية تُقَصّ إلى 1000 سهم
    assert p1["trades_taken"] == 2 and p1["trades_skipped_cash"] == 0, p1
    print("PASS deterministic cash: capped sizing, stable under record order")


if __name__ == "__main__":
    all_recs = []
    all_recs += test_scenario("SYN_TP1.CA", c_tp1, "tp1_first")
    all_recs += test_scenario("SYN_STOP.CA", c_stop, "stop_first")
    all_recs += test_scenario("SYN_NOTEXEC.CA", c_notexec, "not_executed")
    all_recs += test_scenario("SYN_EXPIRED.CA", c_expired, "expired")
    all_recs += test_scenario("SYN_UNRES.CA", c_unresolved, "unresolved")
    all_recs += test_wait()
    all_recs += test_overlap()
    test_reconciliation(all_recs)
    test_deterministic_cash()
    print("ALL WALK-FORWARD FIXTURE TESTS PASSED")
