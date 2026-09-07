import pandas as pd
from scanner import get_stock_data

# قائمة محفظتك الجديدة المحدثة مع الكميات وأسعار التكلفة
MY_PORTFOLIO = {
    "EFIH": {"shares": 586, "buy_price": 24.39},
    "NIPH": {"shares": 25, "buy_price": 384.65},
    "KORA": {"shares": 1250, "buy_price": 5.38},
    "GTWL": {"shares": 23, "buy_price": 242.66},
    "MILS": {"shares": 24, "buy_price": 211.08},
    "CIEB": {"shares": 159, "buy_price": 25.63},
    "PHAR": {"shares": 32, "buy_price": 130.70},
    "EGAL": {"shares": 10, "buy_price": 374.64},
    "MASR": {"shares": 300, "buy_price": 8.55},
}

def analyze_user_portfolio():
    """
    فحص وتحليل أسهم محفظة المستخدم الجديدة بناءً على أحدث إغلاق مسجل وإعطاء نصيحة ذكية.
    """
    portfolio_results = []

    for ticker, info in MY_PORTFOLIO.items():
        try:
            symbol_full = f"{ticker}.CA"
            df = get_stock_data(symbol_full)

            if df is None or df.empty or len(df) < 30:
                print(f"⚠️ تحذير: لم يتم جلب بيانات كافية للسهم {ticker}")
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

            # منطق النصيحة الذكية
            structural_stop = support - (0.5 * atr) if support > 0 else close_price - (2 * atr)

            if close_price <= structural_stop or close_price < ma200 * 0.95:
                advice = "بيع فوري / وقف خسارة 🔴"
                reason = "كسر خط الدفاع الرئيسي أو الدعم الهام."
            elif rsi > 75 or close_price >= resistance * 0.98:
                advice = "جني أرباح جزئي 💰"
                reason = "السهم قرب من المقاومة أو ظهر تشبع شرائي."
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
