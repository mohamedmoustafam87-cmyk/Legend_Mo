import pandas as pd
from scanner import get_stock_data, fetch_mubasher_prices
from indicators import calculate_indicators

# قائمة محفظتك المحدثة مع الكميات وأسعار التكلفة
MY_PORTFOLIO = {
    "EFIH": {"shares": 736, "buy_price": 24.11},
    "NIPH": {"shares": 75, "buy_price": 344.14},
    "KORA": {"shares": 1430, "buy_price": 6.70},
    "GTWL": {"shares": 72, "buy_price": 236.85},
    "MILS": {"shares": 44, "buy_price": 207.65},
    "ACGC": {"shares": 700, "buy_price": 14.785},
    "SPMD": {"shares": 10000, "buy_price": 0.52},
    "MASR": {"shares": 1104, "buy_price": 8.28},
    "SIPC": {"shares": 614, "buy_price": 6.51},
}

def analyze_user_portfolio():
    """
    فحص وتحليل أسهم محفظة المستخدم بناءً على أحدث إغلاق مسجل وإعطاء نصيحة ذكية.
    """
    portfolio_results = []
    mubasher_prices = fetch_mubasher_prices()

    for ticker, info in MY_PORTFOLIO.items():
        try:
            symbol_full = f"{ticker}.CA"
            df = get_stock_data(symbol_full, mubasher_prices)

            if df is None or df.empty:
                print(f"⚠️ تحذير: لم يتم جلب بيانات كافية للسهم {ticker}")
                continue

            df = calculate_indicators(df)

            if df is None or df.empty:
                print(f"⚠️ تحذير: فشل حساب المؤشرات للسهم {ticker}")
                continue

            latest = df.iloc[-1]
            close_price = float(latest["Close"])

            ema20 = float(latest["EMA_20"]) if "EMA_20" in df.columns and not pd.isna(latest["EMA_20"]) else close_price
            ma200 = float(latest["MA_200"]) if "MA_200" in df.columns and not pd.isna(latest["MA_200"]) else close_price
            rsi = float(latest["RSI_14"]) if "RSI_14" in df.columns and not pd.isna(latest["RSI_14"]) else 50.0
            support = float(latest["Support_20"]) if "Support_20" in df.columns and not pd.isna(latest["Support_20"]) else close_price * 0.95
            resistance = float(latest["Resistance_20"]) if "Resistance_20" in df.columns and not pd.isna(latest["Resistance_20"]) else close_price * 1.05
            atr = float(latest["ATR"]) if "ATR" in df.columns and not pd.isna(latest["ATR"]) else close_price * 0.03

            shares = info["shares"]
            buy_price = info["buy_price"]

            # حساب المكسب أو الخسارة بدقة
            pnl_egp = (close_price - buy_price) * shares
            pnl_pct = ((close_price - buy_price) / buy_price) * 100
            current_value = close_price * shares

            # منطق النصيحة الذكية واستراتيجية الخروج
            structural_stop = support - (0.5 * atr) if support > 0 else close_price - (2 * atr)

            if close_price <= structural_stop or close_price < ma200 * 0.95:
                advice = "بيع فوري / وقف خسارة 🔴"
                reason = "كسر خط الدفاع الرئيسي أو الدعم الهام."
            elif rsi >= 75 or close_price >= resistance * 0.98:
                advice = "جني أرباح جزئي 💰"
                reason = f"تشبع شرائي (RSI: {rsi:.1f}) أو اقتراب من المقاومة."
            elif close_price > ema20 and ema20 > ma200 and rsi <= 70:
                advice = "احتفاظ قوي 🔥"
                reason = "الاتجاه صاعد بقوة والزخم ممتاز."
            else:
                advice = "احتفاظ ومراقبة 🟡"
                reason = "حركة عرضية طبيعية، استمر بالمتابعة."

            portfolio_results.append({
                "ticker": ticker,
                "shares": shares,
                "buy_price": buy_price,
                "price": round(close_price, 2),
                "pnl_egp": round(pnl_egp, 2),
                "pnl_pct": round(pnl_pct, 2),
                "current_value": round(current_value, 2),
                "advice": advice,
                "reason": reason
            })
        except Exception as e:
            print(f"❌ خطأ أثناء تحليل السهم {ticker}: {e}")
            continue

    return portfolio_results
