import numpy as np
import pandas as pd

from config import (
    MIN_SCORE_THRESHOLD,
    MAX_DISTANCE_FROM_EMA20,
    MAX_ALLOWABLE_RSI,
    REGIME_SIZE_MULT,
)

from risk import calculate_risk_management
from indicators import analyze_candlesticks
from signals import (
    SETUPS,
    FEATURES,
    compute_signals,
    feature_frame,
    regime_from_breadth,
)
from ml import load_model_stats, get_meta_model


# ==========================================================
# Helpers
# ==========================================================

def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default
        value = float(value)
        return default if pd.isna(value) else value
    except (TypeError, ValueError):
        return default


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def _ok(x):
    return not np.isnan(x)


def _sessions(n):
    n = int(n)
    if n == 1:
        return "جلسة واحدة"
    if n == 2:
        return "جلستين"
    return f"{n} جلسات" if 3 <= n <= 10 else f"{n} جلسة"


# ==========================================================
# Legacy composite score (كما هو - يُستخدم كمقياس صحة فنية عام)
# ==========================================================

def calculate_trend_score(last):
    score, reasons = 0, []
    close, ema20, ema50, ma200 = (safe_float(last.get(k)) for k in ("Close", "EMA_20", "EMA_50", "MA_200"))
    ema50_slope = safe_float(last.get("EMA50_Slope_10D"))
    ma200_slope = safe_float(last.get("MA200_Slope_20D"))
    adx, plus_di, minus_di = (safe_float(last.get(k)) for k in ("ADX_14", "PLUS_DI", "MINUS_DI"))

    if _ok(close) and _ok(ma200) and close > ma200:
        score += 4; reasons.append("السعر أعلى من MA200")
    if _ok(ema20) and _ok(ema50) and ema20 > ema50:
        score += 4; reasons.append("EMA20 أعلى من EMA50")
    if _ok(ema50_slope) and ema50_slope > 0:
        score += 3; reasons.append("ميل EMA50 إيجابي")
    if _ok(ma200_slope) and ma200_slope > 0:
        score += 3; reasons.append("ميل MA200 إيجابي")
    if _ok(adx):
        if adx >= 25:
            score += 3; reasons.append("ADX يشير إلى اتجاه قوي")
        elif adx >= 20:
            score += 2; reasons.append("ADX يشير إلى اتجاه متوسط")
    if _ok(plus_di) and _ok(minus_di) and plus_di > minus_di:
        score += 3; reasons.append("قوة المشترين أعلى من البائعين (DI+ > DI-)")

    return clamp(score, 0, 20), reasons


def calculate_momentum_score(last):
    score, reasons = 0, []
    rsi = safe_float(last.get("RSI_14"))
    macd, macd_signal, macd_hist = (safe_float(last.get(k)) for k in ("MACD", "MACD_Signal", "MACD_Hist"))
    roc20, roc60 = safe_float(last.get("ROC_20D")), safe_float(last.get("ROC_60D"))

    if _ok(rsi):
        if 50 <= rsi <= 65:
            score += 5; reasons.append(f"RSI إيجابي ومتوازن ({rsi:.1f})")
        elif 45 <= rsi < 50:
            score += 3
        elif 65 < rsi <= 70:
            score += 3; reasons.append(f"RSI قوي لكن قريب من التشبع ({rsi:.1f})")
        elif 35 <= rsi < 45:
            score += 1
        elif rsi < 35:
            score += 2; reasons.append(f"RSI منخفض ({rsi:.1f})")

    if _ok(macd) and _ok(macd_signal):
        if macd > macd_signal:
            score += 4; reasons.append("MACD أعلى من Signal")
        if _ok(macd_hist) and macd_hist > 0:
            score += 1

    if _ok(roc20):
        if roc20 > 5:
            score += 2; reasons.append(f"العائد خلال 20 جلسة إيجابي ({roc20:.1f}%)")
        elif roc20 > 0:
            score += 1

    if _ok(roc60):
        score += 3 if roc60 > 10 else (1 if roc60 > 0 else 0)

    return clamp(score, 0, 15), reasons


def calculate_volume_score(last):
    score, reasons = 0, []
    vr = safe_float(last.get("Volume_Ratio"))

    if _ok(vr):
        if vr >= 2:
            score += 8; reasons.append(f"حجم تداول قوي جدًا ({vr:.2f}x)")
        elif vr >= 1.5:
            score += 6; reasons.append(f"حجم التداول أعلى من المتوسط ({vr:.2f}x)")
        elif vr >= 1.0:
            score += 4
        elif vr >= 0.7:
            score += 2

    if bool(last.get("Breakout_With_Volume", False)):
        score += 7; reasons.append("اختراق مؤكد بحجم تداول مرتفع")

    return clamp(score, 0, 15), reasons


def calculate_price_action_score(last):
    score, reasons = 0, []
    g = lambda k: bool(last.get(k, False))

    if g("Bullish_Candle"):
        score += 2
    if g("Strong_Bullish_Candle"):
        score += 4; reasons.append("شمعة صاعدة قوية")
    if g("Hammer"):
        score += 3; reasons.append("ظهور Hammer")
    if g("Bullish_Engulfing"):
        score += 4; reasons.append("ظهور Bullish Engulfing")
    if g("Breakout_20"):
        score += 2; reasons.append("السعر فوق مقاومة 20 جلسة")
    if g("Breakdown_20"):
        score -= 5; reasons.append("السعر كسر دعم 20 جلسة")

    return clamp(score, 0, 15), reasons


def calculate_sr_score(last):
    score, reasons = 0, []
    close = safe_float(last.get("Close"))
    support20, resistance20 = safe_float(last.get("Support_20")), safe_float(last.get("Resistance_20"))
    d_sup = safe_float(last.get("Distance_From_Support_Pct"))
    d_res = safe_float(last.get("Distance_From_Resistance_Pct"))

    if np.isnan(close):
        return 0, reasons

    if _ok(d_sup) and 0 <= d_sup <= 3:
        score += 6; reasons.append("السعر قريب من منطقة دعم")
    elif _ok(d_sup) and 3 < d_sup <= 6:
        score += 3

    if _ok(d_res) and d_res > 5:
        score += 4; reasons.append("مساحة جيدة نسبيًا حتى المقاومة")
    elif _ok(d_res) and 2 <= d_res <= 5:
        score += 2

    if _ok(support20) and close > support20:
        score += 2
    if _ok(resistance20) and close < resistance20:
        score += 3

    return clamp(score, 0, 15), reasons


def calculate_money_flow_score(last):
    score, reasons = 0, []
    obv_slope = safe_float(last.get("OBV_Slope_10D"))
    cmf, mfi = safe_float(last.get("CMF_20")), safe_float(last.get("MFI_14"))
    ad_slope = safe_float(last.get("AD_Slope_20D"))

    if bool(last.get("OBV_Bullish", False)):
        score += 3; reasons.append("OBV يدعم الاتجاه الصاعد")
    if _ok(obv_slope) and obv_slope > 0:
        score += 1

    if _ok(cmf):
        if cmf > 0.10:
            score += 3; reasons.append(f"CMF يشير إلى دخول سيولة ({cmf:.2f})")
        elif cmf > 0:
            score += 2
        elif cmf < -0.10:
            score -= 2; reasons.append(f"CMF يشير إلى ضغط بيعي ({cmf:.2f})")

    if _ok(mfi):
        if 50 <= mfi <= 70:
            score += 2
        elif mfi > 80:
            score -= 1
        elif mfi < 25:
            score += 1

    if _ok(ad_slope) and ad_slope > 0:
        score += 1; reasons.append("خط التجميع/التصريف في اتجاه إيجابي")

    return clamp(score, 0, 10), reasons


def calculate_volatility_score(last):
    score, reasons = 0, []
    atr_pct, bb = safe_float(last.get("ATR_Pct")), safe_float(last.get("BB_POSITION"))

    if _ok(atr_pct):
        if 1.5 <= atr_pct <= 4:
            score += 3
        elif atr_pct < 1.5:
            score += 2
        elif atr_pct <= 6:
            score += 1
        else:
            reasons.append(f"تذبذب مرتفع (ATR {atr_pct:.1f}%)")

    if _ok(bb):
        if 30 <= bb <= 70:
            score += 2
        elif bb < 20:
            score += 1
        elif bb > 90:
            reasons.append("السعر قريب من الحد العلوي لبولينجر")

    return clamp(score, 0, 5), reasons


def calculate_price_strength_score(last):
    score = 0
    pos52, r20, r60 = (safe_float(last.get(k)) for k in ("Position_52W", "Return_20D", "Return_60D"))

    if _ok(pos52):
        score += 2 if pos52 >= 70 else (1 if (pos52 >= 50 or pos52 < 25) else 0)
    if _ok(r20):
        score += 1 if r20 > 5 else (0.5 if r20 > 0 else 0)
    if _ok(r60):
        score += 2 if r60 > 10 else (1 if r60 > 0 else 0)

    return clamp(score, 0, 5), []


# ==========================================================
# Forecast (مؤشر مركب - ليس احتمالاً) / Exit
# ==========================================================

def calculate_forecast_scores(total_score, momentum_score, trend_score, volume_score):
    # أوزان معاد تطبيعها بحيث يصل المؤشر فعلاً إلى 100 (القديم كان سقفه ~77)
    tp, mp, vp = trend_score / 20 * 100, momentum_score / 15 * 100, volume_score / 15 * 100
    s1 = 0.40 * total_score + 0.30 * tp + 0.20 * mp + 0.10 * vp
    s2 = 0.40 * total_score + 0.40 * tp + 0.15 * mp + 0.05 * vp
    return round(clamp(s1)), round(clamp(s2))


def forecast_status(score):
    if score >= 75:
        return "🟢 صاعد قوي"
    if score >= 60:
        return "🟢 صاعد"
    if score >= 45:
        return "🟡 عرضي / محايد"
    if score >= 30:
        return "🟠 ضعيف"
    return "🔴 هابط"


def calculate_exit_strategy(rsi, score, macd_hist, price, ema20, chandelier=np.nan):
    if _ok(chandelier) and price < chandelier:
        return "🔴 السعر كسر وقف المطاردة (Chandelier)؛ فكّر في الخروج أو التخفيف."
    if np.isnan(rsi):
        return "مراقبة المؤشرات قبل الخروج"
    if rsi >= 80:
        return "تشبع شرائي مرتفع جدًا؛ راقب جني الأرباح أو ظهور إشارة انعكاس."
    if rsi >= 75:
        return "السهم في منطقة تشبع شرائي؛ راقب ضعف الزخم أو كسر EMA20."
    if _ok(macd_hist) and macd_hist < 0:
        return "الزخم يضعف؛ راقب استمرار انخفاض MACD Histogram."
    if _ok(ema20) and price < ema20:
        return "السعر تحت EMA20؛ راقب كسر الدعم القريب."
    if score < 45:
        return "ضعف واضح في المؤشرات؛ تجنب زيادة المخاطرة."
    return "استمرار المراقبة مع الالتزام بمستوى وقف الخسارة."


# ==========================================================
# Setups + احتمالية تاريخية
# ==========================================================

def _active_setups(df, stats, regime):
    """الإعدادات النشطة على آخر شمعة + إحصاءاتها التاريخية."""
    last_sig = compute_signals(df.tail(300)).iloc[-1]
    model = get_meta_model()
    feats_last = feature_frame(df.tail(1))

    out = []

    for name, cfg in SETUPS.items():
        if not bool(last_sig[name]):
            continue

        st = ((stats or {}).get("setups") or {}).get(name) or {}
        test = st.get("test") or {}
        validated = bool(st.get("validated", False))

        # بوابة البيئة: لو الإعداد خسران تاريخياً في حالة السوق الحالية (n>=20) نمنعه
        reg_stats = (st.get("by_regime") or {}).get(regime) or {}
        regime_ok = not (
            reg_stats.get("trades", 0) >= 20 and (reg_stats.get("avg_ret") or 0) <= 0
        )

        prob = None
        if model is not None:
            row = feats_last.copy()
            for k in SETUPS:
                row[f"setup_{k}"] = 1.0 if k == name else 0.0
            prob = float(model.predict(row)[0])

        out.append({
            "name": name,
            "label": cfg["label"],
            "horizon": cfg["horizon"],
            "validated": validated,
            "regime_ok": regime_ok,
            "hist_win": test.get("win_rate"),
            "hist_exp": test.get("avg_ret"),
            "hist_n": test.get("trades"),
            "hist_wilson": test.get("wilson_low"),
            "probability": prob,
        })

    return out


# ==========================================================
# Main Strategy
# ==========================================================

def evaluate_stock_strategy(df, ticker=None):

    if df is None or df.empty:
        return None

    required = [
        "Close", "EMA_20", "EMA_50", "MA_200", "RSI_14", "ATR_14",
        "MACD", "MACD_Signal", "ADX_14", "Volume_Ratio",
    ]
    if any(col not in df.columns for col in required):
        return None

    if len(df) < 60:
        return None

    last = df.iloc[-1]

    price = safe_float(last.get("Close"))
    atr = safe_float(last.get("ATR_14"))
    rsi = safe_float(last.get("RSI_14"))
    ema20, ema50, ma200 = (safe_float(last.get(k)) for k in ("EMA_20", "EMA_50", "MA_200"))
    macd_hist = safe_float(last.get("MACD_Hist"))
    adx = safe_float(last.get("ADX_14"))
    volume_ratio = safe_float(last.get("Volume_Ratio"))
    chandelier = safe_float(last.get("Chandelier_22"))

    if np.isnan(price) or price <= 0:
        return None

    # ---------------- legacy score ----------------
    trend_score, r1 = calculate_trend_score(last)
    momentum_score, r2 = calculate_momentum_score(last)
    volume_score, r3 = calculate_volume_score(last)
    price_action_score, r4 = calculate_price_action_score(last)
    sr_score, r5 = calculate_sr_score(last)
    money_flow_score, r6 = calculate_money_flow_score(last)
    volatility_score, r7 = calculate_volatility_score(last)
    price_strength_score, r8 = calculate_price_strength_score(last)

    score = int(round(clamp(
        trend_score + momentum_score + volume_score + price_action_score
        + sr_score + money_flow_score + volatility_score + price_strength_score
    )))

    reasons = list(dict.fromkeys(r1 + r2 + r3 + r4 + r5 + r6 + r7 + r8))

    score_1m, score_2m = calculate_forecast_scores(
        score, momentum_score, trend_score, volume_score
    )

    # ---------------- trend status ----------------
    if _ok(ema20) and _ok(ema50) and _ok(ma200):
        if price > ema20 > ema50 > ma200:
            trend_status = "📈 صاعد قوي"
        elif price > ema50 > ma200:
            trend_status = "📈 صاعد"
        elif price < ema20 < ema50 < ma200:
            trend_status = "📉 هابط قوي"
        elif price < ma200:
            trend_status = "📉 تحت MA200"
        else:
            trend_status = "↔️ عرضي / انتقالي"
    else:
        trend_status = "غير محدد"

    dist_ema20 = safe_float(last.get("EMA20_Distance_Pct"))
    overextended = _ok(dist_ema20) and dist_ema20 > MAX_DISTANCE_FROM_EMA20
    too_far_below_ema = _ok(dist_ema20) and dist_ema20 < -10

    support = safe_float(last.get("Support_20"))
    resistance = safe_float(last.get("Resistance_20"))

    # ---------------- setups / regime ----------------
    stats = load_model_stats()
    breadth = safe_float(last.get("Breadth_50"))
    regime = regime_from_breadth(breadth)

    setups = _active_setups(df, stats, regime)

    def rank_key(s):
        p = s["probability"]
        return (
            s["validated"] and s["regime_ok"],
            p if p is not None else (s["hist_win"] or 0) / 100,
        )

    setups.sort(key=rank_key, reverse=True)
    best = setups[0] if setups else None

    if stats is not None:
        actionable = bool(best and best["validated"] and best["regime_ok"])
    else:
        actionable = bool(best and score >= MIN_SCORE_THRESHOLD)

    # ---------------- trade plan ----------------
    if best:
        cfg = SETUPS[best["name"]]
        rr = cfg["target_atr"] / cfg["stop_atr"]
        risk_data = (
            calculate_risk_management(
                price, atr, support=None,
                stop_atr=cfg["stop_atr"], tp1_r=rr, tp2_r=rr * 1.6,
            ) if _ok(atr) else None
        ) or {}
    else:
        risk_data = (
            calculate_risk_management(price, atr, support=support) if _ok(atr) else None
        ) or {}

    stop_loss = safe_float(risk_data.get("stop_loss"))
    if np.isnan(stop_loss):
        stop_loss = max(price - 2 * atr, price * 0.5) if _ok(atr) else price * 0.95

    risk_per_share = price - stop_loss
    if risk_per_share <= 0:
        risk_per_share = price * 0.05

    tp1 = safe_float(risk_data.get("tp1"), price + 2 * risk_per_share)
    tp2 = safe_float(risk_data.get("tp2"), price + 3 * risk_per_share)
    rr1 = (tp1 - price) / risk_per_share
    rr2 = (tp2 - price) / risk_per_share
    stop_loss_pct = (stop_loss - price) / price * 100

    shares = int(risk_data.get("shares", 0))
    mult = REGIME_SIZE_MULT.get(regime, 0.75)
    shares = int(shares * mult)
    position_value = round(shares * price, 2)
    actual_risk = round(shares * risk_per_share, 2)

    # ideal entry
    max_drop = price * 0.985
    realistic_support = (
        max(support, max_drop) if (_ok(support) and 0 < support < price) else max_drop
    )

    # days
    if best:
        days_tp1 = best["horizon"]
        days_tp2 = best["horizon"]
        days_tp1_text = f"حتى {_sessions(days_tp1)} (أقصى مدة احتفاظ)"
        days_tp2_text = days_tp1_text
    elif _ok(atr) and atr > 0:
        days_tp1 = max(2, int(round((tp1 - price) / atr)))
        days_tp2 = max(3, int(round((tp2 - price) / atr)))
        days_tp1_text = f"{days_tp1} جلسة تقريبًا"
        days_tp2_text = f"{days_tp2} جلسة تقريبًا"
    else:
        days_tp1, days_tp2 = 10, 20
        days_tp1_text, days_tp2_text = "10 جلسة تقريبًا", "20 جلسة تقريبًا"

    # ---------------- entry status / recommendation ----------------
    too_hot = _ok(rsi) and rsi > MAX_ALLOWABLE_RSI
    is_pullback = bool(best and best["name"] in ("pullback", "mean_reversion"))

    if actionable and not too_hot and (is_pullback or not overextended):
        entry_status = "🟢 دخول مناسب"
    elif best:
        entry_status = "🟡 انتظر نقطة دخول أفضل"
    else:
        entry_status = "🔴 لا توجد إشارة"

    if actionable:
        rec = f"🟢 {best['label']}"
    elif best:
        rec = f"🟡 إشارة غير مُتحقق منها ({best['label']})"
    elif score >= 60:
        rec = "👀 مراقبة"
    else:
        rec = "⚪ لا توجد إشارة"

    # ---------------- ranking value ----------------
    if best and best["probability"] is not None:
        edge_score = best["probability"] * 100
    elif best and best["hist_win"] is not None:
        edge_score = float(best["hist_win"])
    else:
        edge_score = float(score)

    # ---------------- reasons / exit ----------------
    if best:
        reasons.insert(0, f"إعداد نشط: {best['label']}")

    exit_strategy = calculate_exit_strategy(
        rsi, score, macd_hist, price, ema20, chandelier
    )

    for reason in analyze_candlesticks(df):
        if reason not in reasons:
            reasons.append(reason)

    ema50_slope = safe_float(last.get("EMA50_Slope_10D"))
    ma200_slope = safe_float(last.get("MA200_Slope_20D"))

    return {
        "ticker": ticker,
        "score": score,
        "rec": rec,
        "actionable": actionable,
        "edge_score": round(edge_score, 1),
        "entry_status": entry_status,
        "setups": setups,
        "best_setup": best["name"] if best else None,
        "probability": best["probability"] if best else None,
        "regime": regime,
        "breadth": None if np.isnan(breadth) else round(breadth, 1),
        "rs_rank": safe_float(last.get("RS_Rank_60")),
        "trailing_stop": None if np.isnan(chandelier) else round(chandelier, 2),
        "supertrend_up": bool(safe_float(last.get("Supertrend_Dir"), 0) > 0),

        "score_breakdown": {
            "trend": trend_score, "momentum": momentum_score, "volume": volume_score,
            "price_action": price_action_score, "support_resistance": sr_score,
            "money_flow": money_flow_score, "volatility": volatility_score,
            "price_strength": price_strength_score,
        },
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "volume_score": volume_score,
        "price_action_score": price_action_score,
        "sr_score": sr_score,
        "money_flow_score": money_flow_score,
        "volatility_score": volatility_score,
        "price_strength_score": price_strength_score,

        "price": price,
        "strategy_price": price,
        "trend_status": trend_status,

        "forecast_1m_score": score_1m,
        "forecast_2m_score": score_2m,
        "forecast_1m_status": forecast_status(score_1m),
        "forecast_2m_status": forecast_status(score_2m),
        "score_1m": score_1m,
        "score_2m": score_2m,

        "rsi": rsi,
        "adx": adx,
        "atr": atr,
        "volume_ratio": volume_ratio,
        "ema20": ema20,
        "ema50": ema50,
        "ma200": ma200,
        "ema20_distance_pct": dist_ema20,
        "distance_from_ema": dist_ema20,
        "ema50_slope": (ema50_slope / ema50 * 100) if (_ok(ema50_slope) and _ok(ema50) and ema50) else 0.0,
        "ma200_slope": (ma200_slope / ma200 * 100) if (_ok(ma200_slope) and _ok(ma200) and ma200) else 0.0,
        "support": support,
        "resistance": resistance,

        "ideal_entry": round(realistic_support, 2),
        "entry_high": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "stop_loss_pct": round(stop_loss_pct, 2),
        "risk_per_share": round(risk_per_share, 2),
        "shares": shares,
        "position_value": position_value,
        "actual_risk": actual_risk,
        "size_multiplier": mult,
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "rr1": round(rr1, 2),
        "rr2": round(rr2, 2),
        "days_tp1": days_tp1,
        "days_tp2": days_tp2,
        "days_tp1_text": days_tp1_text,
        "days_tp2_text": days_tp2_text,

        "overextended": overextended,
        "too_far_below_ema": too_far_below_ema,
        "reasons": reasons,
        "exit_strategy": exit_strategy,

        "historical_close": df.attrs.get("historical_close"),
        "current_price": df.attrs.get("current_price"),
        "price_source": df.attrs.get("price_source"),
        "is_realtime": df.attrs.get("is_realtime", False),
        "current_vs_close_pct": df.attrs.get("current_vs_close_pct"),
        "data_source": df.attrs.get("data_source"),
    }
