import numpy as np
import pandas as pd

from scanner import get_stock_data, fetch_mubasher_prices
from indicators import calculate_indicators
from strategy import evaluate_stock_strategy
from signals import attach_context


# ==========================================================
# MY PORTFOLIO
# ==========================================================

MY_PORTFOLIO = {
    "ETEL": {"shares": 79, "buy_price": 141.133},
    "NIPH": {"shares": 75, "buy_price": 344.14},
    "KORA": {"shares": 2983, "buy_price": 6.524},
    "GTWL": {"shares": 124, "buy_price": 197.859},
    "MILS": {"shares": 44, "buy_price": 207.65},
    "ACGC": {"shares": 700, "buy_price": 14.785},
    "SPMD": {"shares": 10000, "buy_price": 0.52},
    "MASR": {"shares": 1104, "buy_price": 8.28},
    "EXPA": {"shares": 200, "buy_price": 20.92},
    "SIPC": {"shares": 614, "buy_price": 6.51},
    "ALCN": {"shares": 145, "buy_price": 35.133},
}


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = float(value)
        return default if pd.isna(value) else value
    except (TypeError, ValueError):
        return default


# ==========================================================
# Holding advice (منطق إدارة مركز قائم - يختلف عن منطق الدخول)
# ==========================================================

def holding_advice(latest, strategy, current_price, pnl_pct):
    close = current_price
    chandelier = safe_float(latest.get("Chandelier_22"), np.nan)
    ema20, ema50, ma200 = (safe_float(latest.get(k), np.nan) for k in ("EMA_20", "EMA_50", "MA_200"))
    rsi = safe_float(latest.get("RSI_14"), 50)
    dist = safe_float(latest.get("EMA20_Distance_Pct"), 0)
    st_down = safe_float(latest.get("Supertrend_Dir"), 1) < 0

    broke_trail = not np.isnan(chandelier) and close < chandelier
    trend_break = (
        not np.isnan(ma200) and not np.isnan(ema20) and not np.isnan(ema50)
        and close < ma200 and ema20 < ema50
    )

    if broke_trail or trend_break:
        why = []
        if broke_trail:
            why.append(f"كسر وقف المطاردة ({chandelier:.2f})")
        if trend_break:
            why.append("السعر تحت MA200 وEMA20 تحت EMA50")
        return "🔴 خروج / تخفيف", " + ".join(why)

    if rsi >= 78 and dist >= 10:
        return "🟠 جني جزء من الربح", f"تشبع شرائي (RSI {rsi:.0f}) والسعر بعيد {dist:.1f}% عن EMA20"

    if st_down and not np.isnan(ema20) and close < ema20:
        return "🟠 ضعف في الاتجاه", "Supertrend هابط والسعر تحت EMA20؛ ارفع الوقف أو قلّل."

    if strategy and strategy.get("actionable") and strategy.get("best_setup") in ("pullback", "breakout", "momentum"):
        best = strategy["best_setup"]
        label = next((s["label"] for s in strategy["setups"] if s["name"] == best), best)
        return "🟢 احتفاظ / فرصة تعزيز", f"إعداد نشط مُتحقق منه: {label}"

    if not np.isnan(ema20) and not np.isnan(ema50) and close > ema20 > ema50:
        return "🟢 احتفاظ", "الاتجاه سليم (فوق EMA20 وEMA50)."

    return "🟡 احتفاظ ومراقبة", "لا توجد إشارة خروج مؤكدة ولا إشارة تعزيز."


# ==========================================================
# Analyze Portfolio
# ==========================================================

def analyze_user_portfolio(ctx=None):
    """
    ctx: سياق السوق من scan_market (لحساب القوة النسبية). اختياري.
    السعر الحالي: Mubasher، وعند فشله آخر إغلاق من Yahoo.
    """

    results = []
    mubasher_prices = fetch_mubasher_prices()

    for ticker, info in MY_PORTFOLIO.items():
        try:
            symbol_full = f"{ticker}.CA"

            df, data_source = get_stock_data(symbol_full, mubasher_prices)

            if df is None or df.empty:
                print(f"⚠️ لم يتم جلب بيانات كافية للسهم {ticker}")
                continue

            meta = dict(df.attrs)

            df = calculate_indicators(df)
            if df is None or df.empty:
                print(f"⚠️ فشل حساب المؤشرات للسهم {ticker}")
                continue

            df.attrs.update(meta)
            df = attach_context(df, ctx)

            latest = df.iloc[-1]
            strategy_price = safe_float(latest["Close"])

            current_price = safe_float(meta.get("current_price"))
            price_source = meta.get("price_source", "Unknown")
            is_realtime = bool(meta.get("is_realtime", False))

            if current_price <= 0:
                current_price = strategy_price
                price_source = "Yahoo Last Close"
                is_realtime = False

            shares = int(info["shares"])
            buy_price = safe_float(info["buy_price"])

            if shares <= 0 or buy_price <= 0:
                continue

            current_value = current_price * shares
            cost_value = buy_price * shares
            pnl_egp = (current_price - buy_price) * shares
            pnl_pct = (current_price - buy_price) / buy_price * 100

            strategy = evaluate_stock_strategy(df, symbol_full)
            advice, reason = holding_advice(latest, strategy, current_price, pnl_pct)

            chandelier = safe_float(latest.get("Chandelier_22"), np.nan)

            results.append({
                "ticker": ticker,
                "shares": shares,
                "buy_price": round(buy_price, 3),

                "current_price": round(current_price, 2),
                "historical_close": round(safe_float(meta.get("historical_close")), 2),
                "strategy_price": round(strategy_price, 2),
                "price_source": price_source,
                "is_realtime": is_realtime,
                "current_vs_close_pct": round(safe_float(meta.get("current_vs_close_pct")), 2),

                "cost_value": round(cost_value, 2),
                "current_value": round(current_value, 2),
                "pnl_egp": round(pnl_egp, 2),
                "pnl_pct": round(pnl_pct, 2),
                "pnl_status": "🟢 رابح" if pnl_egp > 0 else ("🔴 خاسر" if pnl_egp < 0 else "🟡 تعادل"),

                "ema20": round(safe_float(latest.get("EMA_20"), strategy_price), 2),
                "ma200": round(safe_float(latest.get("MA_200"), strategy_price), 2),
                "rsi": round(safe_float(latest.get("RSI_14"), 50), 2),
                "support": round(safe_float(latest.get("Support_20"), strategy_price * 0.95), 2),
                "resistance": round(safe_float(latest.get("Resistance_20"), strategy_price * 1.05), 2),
                "atr": round(safe_float(latest.get("ATR_14"), strategy_price * 0.03), 2),

                "score": (strategy or {}).get("score", 0),
                "advice": advice,
                "reason": reason,
                "entry_status": (strategy or {}).get("entry_status"),
                # للمحفظة: الوقف = وقف المطاردة (Chandelier)
                "stop_loss": None if np.isnan(chandelier) else round(chandelier, 2),
                "tp1": (strategy or {}).get("tp1"),
                "tp2": (strategy or {}).get("tp2"),
                "rr1": (strategy or {}).get("rr1"),
                "rr2": (strategy or {}).get("rr2"),
                "exit_strategy": (strategy or {}).get("exit_strategy"),
                "data_source": data_source,
            })

        except Exception as e:  # noqa: BLE001
            print(f"❌ خطأ أثناء تحليل {ticker}: {e}")
            continue

    return results
