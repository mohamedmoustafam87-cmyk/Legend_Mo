"""
محرك القياس التاريخي (walk-forward) — نسخة معزولة للاختبار فقط.

يقيس نسختين على نفس المنهجية الأمينة:
- v1_baseline: إشارة السكانر الحالية (score>=60 + سيولة)، دخول بافتتاح
  الجلسة التالية، وقف/أهداف من سعر الإغلاق كما يفعل التقرير الحالي.
- v2: البوابات الإلزامية + الدخول المشروط (تجاوز قمة جلسة الإشارة خلال
  3 جلسات، التنفيذ بسعر الاختراق أو الافتتاح عند الفجوة) + وقف/أهداف/حجم
  موحدة من سعر التنفيذ الفعلي + بوابة المقاومة.

قواعد القياس المعتمدة:
- أفق 42 جلسة من تاريخ الإشارة.
- النتائج: not_executed / tp1_first / stop_first / expired / unresolved.
- لمس الهدف والوقف في نفس الجلسة ≠ نجاح (يُحسب وقفًا).
- [CANDIDATE-B] صفقة واحدة مفتوحة لكل سهم.
- الرسوم من fee_model (مكونات رسمية بالثوابت والحدود الدنيا) مع سيناريوهات
  حساسية منفصلة؛ الانزلاق معروض منفصلًا عن الرسوم.
"""

import numpy as np
import pandas as pd

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy
from .fee_model import ALL_SCENARIOS, round_trip_fees
from .signal_v2 import (
    ENTRY_WINDOW_SESSIONS,
    MEASUREMENT_HORIZON,
    TICK,
    evaluate_signal_v2,
    liquidity_ok_on,
    position_size,
    stop_rule,
)

OUTCOME_NOT_EXECUTED = "not_executed"
OUTCOME_TP1 = "tp1_first"
OUTCOME_STOP = "stop_first"
OUTCOME_EXPIRED = "expired"
OUTCOME_UNRESOLVED = "unresolved"


def _trade_outcome(df_after, entry_idx, stop, tp1, horizon_end, entry_price=None):
    """
    يفحص الجلسات من يوم التنفيذ حتى horizon_end.
    df_after: الصفوف القابلة للفحص (من يوم التنفيذ).
    يعيد (outcome, exit_price, exit_date, sessions_held).
    نفس-الجلسة هدف+وقف = stop_first (ليس نجاحًا).
    يوم التنفيذ: الوقف مفحوص على كامل مدى الجلسة (تحفظي — قاع اليوم قد
    يسبق الاختراق فعليًا)، وفجوة الافتتاح فوق TP1 تملأ أمر البيع عند
    الافتتاح (exit = max(open, tp1)).
    """
    for i in range(len(df_after)):
        if entry_idx + i > horizon_end:
            break
        row = df_after.iloc[i]
        hi, lo, cl = float(row["High"]), float(row["Low"]), float(row["Close"])
        hit_stop = lo <= stop
        hit_tp1 = hi >= tp1
        if hit_stop and hit_tp1:
            return OUTCOME_STOP, stop, df_after.index[i], i + 1
        if hit_stop:
            return OUTCOME_STOP, stop, df_after.index[i], i + 1
        if hit_tp1:
            exit_px = tp1
            if i == 0 and entry_price is not None and entry_price > tp1:
                exit_px = entry_price  # فجوة فوق الهدف: البيع بسعر التنفيذ
            return OUTCOME_TP1, exit_px, df_after.index[i], i + 1
    if len(df_after) and entry_idx + len(df_after) - 1 >= horizon_end:
        last = df_after.iloc[-1]
        return OUTCOME_EXPIRED, float(last["Close"]), df_after.index[-1], len(df_after)
    return OUTCOME_UNRESOLVED, None, None, len(df_after)


def run_symbol_backtest(symbol, df, variant="v2", ema_max_dist=None):
    """
    يعيد قائمة صفقات/إشارات لسهم واحد عبر التاريخ.
    df: OHLCV كامل (خام من Yahoo).
    """
    if df is None or len(df) < 260:
        return []
    try:
        data = calculate_indicators(df.copy())
    except Exception:
        return []
    if data is None or data.empty:
        return []

    records = []
    drops = {}  # كل مسار استبعاد بعد توليد الإشارة يُحسب صراحة

    def _drop(reason):
        drops[reason] = drops.get(reason, 0) + 1

    n = len(data)
    open_until = -1  # [CANDIDATE-B] صفقة واحدة مفتوحة لكل سهم

    for t in range(220, n):
        if t <= open_until:
            continue
        hist = data.iloc[: t + 1]
        fully_observed = (t + MEASUREMENT_HORIZON) <= (n - 1)
        horizon_end = min(t + MEASUREMENT_HORIZON, n - 1)

        if variant == "v2":
            kwargs = {} if ema_max_dist is None else {"ema_max_dist": ema_max_dist}
            sig = evaluate_signal_v2(hist.copy(), symbol, **kwargs)
            if sig is None:
                continue
            if sig.status != "BUY":
                records.append({
                    "symbol": symbol, "variant": variant,
                    "signal_date": data.index[t], "score": sig.score,
                    "outcome": "wait_filtered",
                })
                continue
            # الدخول المشروط: تجاوز قمة جلسة الإشارة خلال 3 جلسات
            entry_price = None
            entry_idx = None
            for j in range(1, ENTRY_WINDOW_SESSIONS + 1):
                if t + j >= n:
                    break
                bar = data.iloc[t + j]
                if float(bar["High"]) > sig.signal_high:
                    entry_idx = t + j
                    entry_price = max(float(bar["Open"]), sig.signal_high + TICK)
                    break
            if entry_price is None:
                if (t + ENTRY_WINDOW_SESSIONS) <= (n - 1):
                    records.append({
                        "symbol": symbol, "variant": variant,
                        "signal_date": data.index[t], "score": sig.score,
                        "outcome": OUTCOME_NOT_EXECUTED,
                    })
                open_until = min(t + ENTRY_WINDOW_SESSIONS, n - 1)
                continue
            stop = stop_rule(entry_price, sig.support, sig.atr)
            if stop is None:
                _drop("v2_invalid_stop_at_execution")
                continue
            rps = entry_price - stop
            tp1 = entry_price + 2.0 * rps
            tp2 = entry_price + 3.0 * rps
            shares = position_size(entry_price, stop)
            if shares <= 0:
                _drop("v2_zero_position_size")
                continue
        else:  # v1_baseline / v1_advertised
            if not liquidity_ok_on(hist):
                continue
            try:
                analysis = evaluate_stock_strategy(hist.copy(), symbol)
            except Exception:
                analysis = None
            if analysis is None:
                continue
            if t + 1 >= n:
                _drop("v1_no_next_session")
                continue
            if variant == "v1_advertised":
                # الدخول كما يُعلن في التقرير الحالي: حد شراء عند ideal_entry
                ideal = float(analysis["ideal_entry"])
                entry_price = None
                entry_idx = None
                for j in range(1, ENTRY_WINDOW_SESSIONS + 1):
                    if t + j >= n:
                        break
                    bar = data.iloc[t + j]
                    if float(bar["Low"]) <= ideal:
                        entry_idx = t + j
                        entry_price = min(float(bar["Open"]), ideal)
                        break
                if entry_price is None:
                    if (t + ENTRY_WINDOW_SESSIONS) <= (n - 1):
                        records.append({
                            "symbol": symbol, "variant": variant,
                            "signal_date": data.index[t],
                            "score": analysis["score"],
                            "outcome": OUTCOME_NOT_EXECUTED,
                        })
                    open_until = min(t + ENTRY_WINDOW_SESSIONS, n - 1)
                    continue
            else:
                entry_idx = t + 1
                entry_price = float(data.iloc[entry_idx]["Open"])
            stop = float(analysis["stop_loss"])
            tp1 = float(analysis["tp1"])
            tp2 = float(analysis["tp2"])
            shares = int(analysis["shares"])
            sig = type("S", (), {"score": analysis["score"]})()
            if entry_price <= 0 or stop <= 0 or stop >= entry_price or shares <= 0:
                _drop("v1_invalid_entry_or_stop_or_size")
                continue

        if not fully_observed:
            records.append({
                "symbol": symbol, "variant": variant,
                "signal_date": data.index[t], "score": sig.score,
                "entry_date": data.index[entry_idx],
                "outcome": OUTCOME_UNRESOLVED,
            })
            open_until = horizon_end
            continue
        after = data.iloc[entry_idx: horizon_end + 1]
        outcome, exit_price, exit_date, held = _trade_outcome(
            after, entry_idx, stop, tp1, horizon_end, entry_price=entry_price
        )
        open_until = entry_idx + held - 1 if outcome in (
            OUTCOME_TP1, OUTCOME_STOP, OUTCOME_EXPIRED) else horizon_end

        rec = {
            "symbol": symbol, "variant": variant,
            "signal_date": data.index[t], "score": sig.score,
            "entry_date": data.index[entry_idx], "entry_price": round(entry_price, 4),
            "stop": round(stop, 4), "tp1": round(tp1, 4), "tp2": round(tp2, 4),
            "shares": shares, "outcome": outcome,
            "sessions_held": held,
        }
        if outcome in (OUTCOME_TP1, OUTCOME_STOP, OUTCOME_EXPIRED):
            buy_value = shares * entry_price
            sell_value = shares * exit_price
            rec["exit_date"] = exit_date
            rec["exit_price"] = round(exit_price, 4)
            rec["r_multiple"] = round((exit_price - entry_price) / (entry_price - stop), 3)
            rec["gross_pl"] = round(sell_value - buy_value, 2)
            for sc in ALL_SCENARIOS:
                slipped_entry = entry_price * (1 + sc.slippage_pct)
                slipped_exit = exit_price * (1 - sc.slippage_pct)
                fees = round_trip_fees(shares * slipped_entry, shares * slipped_exit, sc)
                rec[f"net_pl_{sc.name}"] = round(
                    shares * (slipped_exit - slipped_entry) - fees, 2)
        records.append(rec)
    for r in records:
        r.setdefault("drops", None)
    if records:
        records[0]["drops"] = drops
    elif drops:
        records.append({"symbol": symbol, "variant": variant,
                        "signal_date": None, "outcome": "meta", "drops": drops})
    return records


KNOWN_OUTCOMES = (OUTCOME_TP1, OUTCOME_STOP, OUTCOME_EXPIRED,
                  OUTCOME_UNRESOLVED, OUTCOME_NOT_EXECUTED)


def summarize(records, variant):
    """ملخص أداء نسخة واحدة بالأرقام المعتمدة + تسوية كاملة للاستبعادات."""
    vrecs = [r for r in records if r["variant"] == variant]
    recs = [r for r in vrecs if r.get("outcome") in KNOWN_OUTCOMES]
    waits = [r for r in vrecs if r.get("outcome") == "wait_filtered"]
    executed = [r for r in recs if r.get("outcome") in (OUTCOME_TP1, OUTCOME_STOP, OUTCOME_EXPIRED)]
    unresolved = [r for r in recs if r.get("outcome") == OUTCOME_UNRESOLVED]
    not_exec = [r for r in recs if r.get("outcome") == OUTCOME_NOT_EXECUTED]
    drops = {}
    for r in vrecs:
        for k, v in (r.get("drops") or {}).items():
            drops[k] = drops.get(k, 0) + v
    unknown = [r for r in vrecs if r.get("outcome") not in KNOWN_OUTCOMES + ("wait_filtered", "meta")]
    tp1 = [r for r in executed if r["outcome"] == OUTCOME_TP1]
    stopped = [r for r in executed if r["outcome"] == OUTCOME_STOP]
    expired = [r for r in executed if r["outcome"] == OUTCOME_EXPIRED]
    out = {
        "variant": variant,
        "signals": len(recs),
        "reconciliation": {
            "total_records": len(vrecs),
            "signals_counted": len(recs),
            "wait_filtered": len(waits),
            "drops_by_reason": drops,
            "unknown_outcome_records": len(unknown),
        },
        "executed": len(executed),
        "not_executed": len(not_exec),
        "unresolved_excluded": len(unresolved),
        "wait_filtered": len(waits),
        "tp1_first": len(tp1),
        "stop_first": len(stopped),
        "expired": len(expired),
        "hit_rate_pct": round(100 * len(tp1) / len(executed), 1) if executed else None,
        "avg_r": round(float(np.mean([r["r_multiple"] for r in executed])), 2) if executed else None,
        "gross_pl_total": round(sum(r["gross_pl"] for r in executed), 2),
    }
    if tp1:
        helds = [r["sessions_held"] for r in tp1]
        out["sessions_to_tp1_median"] = float(np.median(helds))
        out["sessions_to_tp1_p25"] = float(np.percentile(helds, 25))
        out["sessions_to_tp1_p75"] = float(np.percentile(helds, 75))
    for sc in ALL_SCENARIOS:
        key = f"net_pl_{sc.name}"
        out[key] = round(sum(r.get(key, 0) for r in executed), 2)
    return out
