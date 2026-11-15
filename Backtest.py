"""
backtest.py
===========
Backtest شامل لكل الـ Setups على بيانات EGX التاريخية (جديد - يحل محل backtest_short_term.py).

المنهجية:
- الإشارة بعد إغلاق اليوم t، الدخول على افتتاح t+1، ومفيش مطاردة لو الجاب أعلى من MAX_ENTRY_GAP_PCT.
- Triple Barrier (López de Prado): هدف / وقف (بوحدات ATR) / أقصى مدة احتفاظ، بعد خصم التكلفة.
- لو الوقف والهدف في نفس الشمعة: نفترض الوقف الأول (متحفظ). فجوة الافتتاح تُنفّذ على الافتتاح.
- صفقات غير متداخلة لكل سهم/Setup (cooldown = مدة الاحتفاظ).
- تقسيم زمني: أول 70% train، آخر 30% test (مع Embargo)، ولا يُعتمد Setup إلا لو
  ربحه إيجابي في الفترتين وعدّى الحد الأدنى للصفقات في test.
- النموذج الإحصائي (Meta-Model) يُدرّب على train ويُقاس على test، ولا يُستخدم إلا لو نجح.

التشغيل:
    python backtest.py            # 5 سنين من Yahoo (مع كاش)
    python backtest.py 3y
النتيجة: model_stats.json (يقرأه البوت تلقائياً).
"""

import math
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from config import (
    SHARIA_EGX_STOCKS,
    ROUND_TRIP_COST_PCT,
    MODEL_STATS_FILE,
    MAX_WORKERS,
)
from indicators import calculate_indicators
from signals import SETUPS, FEATURES, compute_signals, feature_frame, market_context, regime_from_breadth
from ml import MetaModel, auc, clean_json

import json

# ==========================================================
# Settings
# ==========================================================

MAX_ENTRY_GAP_PCT = 3.0
TRAIN_FRACTION = 0.70
EMBARGO_DAYS = 30
MIN_TRADES_TEST = 30
MIN_PROFIT_FACTOR = 1.1
META_MIN_TRAIN = 300
CACHE_DIR = "backtest_cache"
CACHE_MAX_AGE_HOURS = 24


# ==========================================================
# Data
# ==========================================================

def _load_one(symbol, period):
    import scanner

    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{symbol}_{period}.csv")

    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_MAX_AGE_HOURS * 3600

    if fresh:
        raw = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        raw = scanner.fetch_yahoo_history(symbol, period=period)
        if raw is None:
            return symbol, None
        raw.to_csv(path)

    return symbol, calculate_indicators(raw)


def load_universe(symbols=None, period="5y"):
    symbols = list(symbols or SHARIA_EGX_STOCKS)
    dfs = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for symbol, df in pool.map(lambda s: _load_one(s, period), symbols):
            if df is not None:
                dfs[symbol] = df

    return dfs


# ==========================================================
# Triple barrier
# ==========================================================

def _shift_back(a, k):
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[: len(a) - k] = a[k:]
    return out


def barrier_outcomes(df, horizon, target_atr, stop_atr):
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    v = df["Volume"].to_numpy(float)
    atr = df["ATR_14"].to_numpy(float)

    n = len(df)
    entry = _shift_back(o, 1)
    stop = entry - stop_atr * atr
    target = entry + target_atr * atr

    exit_px = np.full(n, np.nan)
    hit = np.zeros(n, bool)
    bars = np.zeros(n, int)
    done = np.zeros(n, bool)

    for k in range(1, horizon + 1):
        ok, hk, lk, ck = _shift_back(o, k), _shift_back(h, k), _shift_back(l, k), _shift_back(c, k)
        live = (~done) & ~np.isnan(hk)

        if k > 1:
            gap_dn = live & (ok <= stop)
            gap_up = live & ~gap_dn & (ok >= target)
            g = gap_dn | gap_up
            exit_px[g] = ok[g]
            hit[gap_up] = True
            bars[g] = k
            done |= g
            live &= ~done

        s_hit = live & (lk <= stop)
        t_hit = live & ~s_hit & (hk >= target)
        exit_px[s_hit] = stop[s_hit]
        exit_px[t_hit] = target[t_hit]
        hit[t_hit] = True
        bars[s_hit | t_hit] = k
        done |= s_hit | t_hit

        if k == horizon:
            rest = (~done) & ~np.isnan(ck)
            exit_px[rest] = ck[rest]
            bars[rest] = k
            done |= rest

    ret = (exit_px / entry - 1) * 100 - ROUND_TRIP_COST_PCT
    gap = (entry / c - 1) * 100
    v1 = _shift_back(v, 1)

    valid = (
        ~np.isnan(ret) & ~np.isnan(gap) & (gap <= MAX_ENTRY_GAP_PCT)
        & (v1 > 0) & (atr > 0) & (entry > 0)
    )

    return pd.DataFrame({"ret": ret, "hit": hit, "bars": bars, "valid": valid}, index=df.index)


def dedupe(mask, horizon):
    """صفقات غير متداخلة: بعد كل إشارة نتجاهل الإشارات خلال مدة الاحتفاظ."""
    idx = np.flatnonzero(mask)
    keep, nxt = [], -1
    for i in idx:
        if i >= nxt:
            keep.append(i)
            nxt = i + horizon + 1
    out = np.zeros(len(mask), bool)
    out[keep] = True
    return out


# ==========================================================
# Panel
# ==========================================================

def build_panel(dfs):
    market_context(dfs)

    rows, baseline = [], []

    for ticker, df in dfs.items():
        sigs = compute_signals(df)
        feats = feature_frame(df)

        for name, cfg in SETUPS.items():
            out = barrier_outcomes(df, cfg["horizon"], cfg["target_atr"], cfg["stop_atr"])
            valid = out["valid"].to_numpy()

            baseline.append(pd.DataFrame({
                "date": df.index[valid], "setup": name, "ret": out["ret"].to_numpy()[valid],
            }))

            mask = dedupe(sigs[name].to_numpy() & valid, cfg["horizon"])
            if not mask.any():
                continue

            part = feats.loc[mask].copy()
            part["date"] = df.index[mask]
            part["ticker"] = ticker
            part["setup"] = name
            part["ret"] = out["ret"].to_numpy()[mask]
            part["hit"] = out["hit"].to_numpy()[mask]
            part["bars"] = out["bars"].to_numpy()[mask]
            rows.append(part.reset_index(drop=True))

    panel = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    base = pd.concat(baseline, ignore_index=True) if baseline else pd.DataFrame()
    return panel, base


# ==========================================================
# Stats
# ==========================================================

def wilson_lower(wins, n, z=1.96):
    if n == 0:
        return float("nan")
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - adj) / denom


def summarize(df):
    n = len(df)
    if n == 0:
        return {"trades": 0}

    r = df["ret"].to_numpy(float)
    wins = r > 0
    gross_win = r[wins].sum()
    gross_loss = abs(r[~wins].sum())

    return {
        "trades": int(n),
        "win_rate": float(wins.mean() * 100),
        "wilson_low": float(wilson_lower(int(wins.sum()), n) * 100),
        "hit_rate": float(df["hit"].mean() * 100) if "hit" in df else None,
        "avg_ret": float(r.mean()),
        "avg_win": float(r[wins].mean()) if wins.any() else None,
        "avg_loss": float(r[~wins].mean()) if (~wins).any() else None,
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else None,
        "avg_bars": float(df["bars"].mean()) if "bars" in df else None,
    }


def regime_table(panel_setup):
    reg = panel_setup["breadth"].map(regime_from_breadth)
    return {k: summarize(panel_setup[reg == k]) for k in ("low", "mid", "high") if (reg == k).any()}


# ==========================================================
# Meta model
# ==========================================================

def meta_matrix(panel):
    X = panel[FEATURES].copy()
    for k in SETUPS:
        X[f"setup_{k}"] = (panel["setup"] == k).astype(float)
    return X


def fit_meta(panel, split, embargo):
    train = panel[panel["date"] < split - embargo]
    test = panel[panel["date"] >= split]

    if len(train) < META_MIN_TRAIN or len(test) < 60:
        return {"validated": False, "reason": f"عينة صغيرة (train={len(train)}, test={len(test)})"}

    y_tr = (train["ret"] > 0).astype(float).to_numpy()
    y_te = (test["ret"] > 0).astype(float).to_numpy()

    model = MetaModel.fit(meta_matrix(train), y_tr)
    p_te = model.predict(meta_matrix(test))

    test_auc = auc(y_te, p_te)

    order = np.argsort(-p_te)
    top = test.iloc[order[: max(len(test) // 3, 20)]]
    bottom = test.iloc[order[-max(len(test) // 3, 20):]]

    top_exp = float(top["ret"].mean())
    bottom_exp = float(bottom["ret"].mean())
    overall_exp = float(test["ret"].mean())

    validated = bool(test_auc >= 0.55 and top_exp > overall_exp and top_exp > 0 and top_exp > bottom_exp)

    final = MetaModel.fit(meta_matrix(panel), (panel["ret"] > 0).astype(float).to_numpy())

    return {
        "validated": validated,
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "test_auc": test_auc,
        "test_win_rate_overall": float((test["ret"] > 0).mean() * 100),
        "test_win_rate_top_third": float((top["ret"] > 0).mean() * 100),
        "test_avg_ret_overall": overall_exp,
        "test_avg_ret_top_third": top_exp,
        "test_avg_ret_bottom_third": bottom_exp,
        "model": final.to_dict(),
    }


# ==========================================================
# Runner
# ==========================================================

def run(dfs, path=None):
    path = path or MODEL_STATS_FILE

    panel, base = build_panel(dfs)

    if panel.empty:
        print("⚠️ لا توجد إشارات في البيانات.")
        return None

    all_dates = pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in dfs.values()))))
    split = all_dates[int(len(all_dates) * TRAIN_FRACTION)]
    embargo = pd.Timedelta(days=EMBARGO_DAYS)

    print(f"أسهم: {len(dfs)} | تقسيم: {split.date()} | آخر تاريخ: {all_dates[-1].date()}")

    setups_out = {}
    months_test = max((all_dates[-1] - split).days / 30.4, 1)

    print("\n" + "=" * 98)
    print(f"{'setup':15} {'split':6} {'n':>5} {'win%':>6} {'wilson':>7} {'avg%':>7} {'PF':>5} {'bars':>5}   baseline win% / avg%")
    print("=" * 98)

    for name in SETUPS:
        ps = panel[panel["setup"] == name]
        bs = base[base["setup"] == name]

        train = ps[ps["date"] < split - embargo]
        test = ps[ps["date"] >= split]

        s_tr, s_te = summarize(train), summarize(test)
        b_tr = summarize(bs[bs["date"] < split - embargo])
        b_te = summarize(bs[bs["date"] >= split])

        validated = bool(
            s_te.get("trades", 0) >= MIN_TRADES_TEST
            and (s_te.get("avg_ret") or 0) > 0
            and (s_tr.get("avg_ret") or 0) > 0
            and (s_te.get("profit_factor") or 0) >= MIN_PROFIT_FACTOR
        )

        setups_out[name] = {
            "label": SETUPS[name]["label"],
            "train": s_tr,
            "test": s_te,
            "baseline_test": b_te,
            "by_regime": regime_table(ps),
            "signals_per_month_test": s_te.get("trades", 0) / months_test,
            "validated": validated,
        }

        for tag, s, b in (("train", s_tr, b_tr), ("test", s_te, b_te)):
            if s.get("trades", 0) == 0:
                print(f"{name:15} {tag:6} {0:>5}")
                continue
            pf = s["profit_factor"] if s["profit_factor"] is not None else float("inf")
            print(
                f"{name:15} {tag:6} {s['trades']:>5} {s['win_rate']:>6.1f} {s['wilson_low']:>7.1f} "
                f"{s['avg_ret']:>+7.2f} {pf:>5.2f} {s['avg_bars']:>5.1f}   "
                f"{b.get('win_rate', float('nan')):.1f} / {b.get('avg_ret', float('nan')):+.2f}"
                + ("   ✅ validated" if (tag == "test" and validated) else "")
            )

    meta = fit_meta(panel, split, embargo)

    print("\nMeta-model:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in meta.items() if k != "model"})

    payload = clean_json({
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "split": str(split.date()),
        "settings": {
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "max_entry_gap_pct": MAX_ENTRY_GAP_PCT,
            "embargo_days": EMBARGO_DAYS,
            "n_stocks": len(dfs),
            "setups": {k: {x: v[x] for x in ("horizon", "target_atr", "stop_atr")} for k, v in SETUPS.items()},
        },
        "setups": setups_out,
        "meta": meta,
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    ok = [k for k, v in setups_out.items() if v["validated"]]
    print(f"\nاتحفظ: {path}")
    print("Setups المُتحقق منها:", ok if ok else "لا يوجد (البوت مش هيطلع إشارات 'مُتحقق منها')")

    return payload


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else "5y"
    dfs = load_universe(period=period)

    if not dfs:
        sys.exit("مفيش بيانات صالحة (تأكد من الاتصال بالإنترنت).")

    run(dfs)


if __name__ == "__main__":
    main()
