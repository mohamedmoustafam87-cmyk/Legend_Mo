import pandas as pd

from scanner import (
    get_stock_data,
    fetch_mubasher_prices,
)

from indicators import (
    calculate_indicators,
)

from strategy import (
    evaluate_stock_strategy,
)


# ==========================================================
# MY PORTFOLIO
# ==========================================================

MY_PORTFOLIO = {

    "EFIH": {
        "shares": 736,
        "buy_price": 24.11
    },

    "NIPH": {
        "shares": 75,
        "buy_price": 344.14
    },

    "KORA": {
        "shares": 1430,
        "buy_price": 6.70
    },

    "GTWL": {
        "shares": 84,
        "buy_price": 225.83
    },

    "MILS": {
        "shares": 44,
        "buy_price": 207.65
    },

    "ACGC": {
        "shares": 700,
        "buy_price": 14.785
    },

    "SPMD": {
        "shares": 10000,
        "buy_price": 0.52
    },

    "MASR": {
        "shares": 1104,
        "buy_price": 8.28
    },

    "EXPA": {
        "shares": 200,
        "buy_price": 20.92
    },

    "SIPC": {
        "shares": 614,
        "buy_price": 6.51
    },
}


# ==========================================================
# Helpers
# ==========================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        value = float(value)

        if pd.isna(value):
            return default

        return value

    except (
        TypeError,
        ValueError
    ):

        return default


# ==========================================================
# Analyze Portfolio
# ==========================================================

def analyze_user_portfolio():
    """
    تحليل أسهم المحفظة.

    مصادر البيانات:

    Yahoo:
        - Historical OHLCV
        - Technical Indicators
        - Strategy

    Mubasher:
        - Current Price
        - Current Portfolio Value
        - Current P/L

    في حالة فشل Mubasher:
        يتم استخدام آخر إغلاق من Yahoo.
    """

    portfolio_results = []

    # ======================================================
    # Fetch Mubasher Prices Once
    # ======================================================

    mubasher_prices = (
        fetch_mubasher_prices()
    )

    # ======================================================
    # Portfolio Loop
    # ======================================================

    for ticker, info in MY_PORTFOLIO.items():

        try:

            symbol_full = (
                f"{ticker}.CA"
            )

            # ==================================================
            # Yahoo Historical + Mubasher Current
            # ==================================================

            df, data_source = get_stock_data(
                symbol_full,
                mubasher_prices
            )

            if (
                df is None
                or df.empty
            ):

                print(
                    f"⚠️ لم يتم جلب بيانات كافية للسهم {ticker}"
                )

                continue

            # ==================================================
            # Preserve Price Metadata
            # ==================================================

            current_price = safe_float(
                df.attrs.get(
                    "current_price"
                )
            )

            historical_close = safe_float(
                df.attrs.get(
                    "historical_close"
                )
            )

            price_source = (
                df.attrs.get(
                    "price_source",
                    "Unknown"
                )
            )

            is_realtime = (
                df.attrs.get(
                    "is_realtime",
                    False
                )
            )

            current_vs_close_pct = (
                safe_float(
                    df.attrs.get(
                        "current_vs_close_pct"
                    )
                )
            )

            # ==================================================
            # Indicators
            # ==================================================

            df = calculate_indicators(
                df
            )

            if (
                df is None
                or df.empty
            ):

                print(
                    f"⚠️ فشل حساب المؤشرات للسهم {ticker}"
                )

                continue

            # ==================================================
            # Restore Metadata
            # ==================================================

            df.attrs["current_price"] = (
                current_price
            )

            df.attrs["historical_close"] = (
                historical_close
            )

            df.attrs["price_source"] = (
                price_source
            )

            df.attrs["is_realtime"] = (
                is_realtime
            )

            df.attrs["current_vs_close_pct"] = (
                current_vs_close_pct
            )

            # ==================================================
            # Latest Historical Candle
            # ==================================================

            latest = df.iloc[-1]

            strategy_price = safe_float(
                latest["Close"]
            )

            # ==================================================
            # Validate Current Price
            # ==================================================

            if (
                current_price <= 0
            ):

                current_price = (
                    strategy_price
                )

                price_source = (
                    "Yahoo Last Close"
                )

                is_realtime = False

            # ==================================================
            # Portfolio Information
            # ==================================================

            shares = int(
                info["shares"]
            )

            buy_price = safe_float(
                info["buy_price"]
            )

            if (
                shares <= 0
                or buy_price <= 0
            ):

                continue

            # ==================================================
            # Current Portfolio Value
            # ==================================================

            current_value = (
                current_price *
                shares
            )

            # ==================================================
            # Cost Value
            # ==================================================

            cost_value = (
                buy_price *
                shares
            )

            # ==================================================
            # P/L
            # ==================================================

            pnl_egp = (
                current_price -
                buy_price
            ) * shares

            pnl_pct = (
                (
                    current_price -
                    buy_price
                )
                /
                buy_price
            ) * 100

            # ==================================================
            # Technical Values
            # ==================================================

            ema20 = safe_float(
                latest.get(
                    "EMA_20"
                ),
                strategy_price
            )

            ma200 = safe_float(
                latest.get(
                    "MA_200"
                ),
                strategy_price
            )

            rsi = safe_float(
                latest.get(
                    "RSI_14"
                ),
                50
            )

            support = safe_float(
                latest.get(
                    "Support_20"
                ),
                strategy_price * 0.95
            )

            resistance = safe_float(
                latest.get(
                    "Resistance_20"
                ),
                strategy_price * 1.05
            )

            atr = safe_float(
                latest.get(
                    "ATR"
                ),
                strategy_price * 0.03
            )

            # ==================================================
            # Unified Strategy
            # ==================================================

            strategy = evaluate_stock_strategy(
                df,
                symbol_full
            )

            # ==================================================
            # Strategy Information
            # ==================================================

            if strategy is not None:

                advice = strategy.get(
                    "rec",
                    "مراقبة 🟡"
                )

                reason_list = strategy.get(
                    "reasons",
                    []
                )

                reason = (
                    " | ".join(
                        reason_list[:3]
                    )
                    if reason_list
                    else "لا توجد أسباب كافية."
                )

                score = strategy.get(
                    "score",
                    0
                )

                stop_loss = strategy.get(
                    "stop_loss"
                )

                tp1 = strategy.get(
                    "tp1"
                )

                tp2 = strategy.get(
                    "tp2"
                )

                rr1 = strategy.get(
                    "rr1"
                )

                rr2 = strategy.get(
                    "rr2"
                )

                entry_status = strategy.get(
                    "entry_status"
                )

                exit_strategy = strategy.get(
                    "exit_strategy"
                )

            else:

                advice = (
                    "احتفاظ ومراقبة 🟡"
                )

                reason = (
                    "السهم لا يحقق الحد الأدنى "
                    "الحالي لشروط الاستراتيجية."
                )

                score = 0

                stop_loss = None
                tp1 = None
                tp2 = None
                rr1 = None
                rr2 = None

                entry_status = (
                    "غير متاح"
                )

                exit_strategy = (
                    "لا توجد إشارة خروج مؤكدة."
                )

            # ==================================================
            # Profit Status
            # ==================================================

            if pnl_egp > 0:

                pnl_status = (
                    "🟢 رابح"
                )

            elif pnl_egp < 0:

                pnl_status = (
                    "🔴 خاسر"
                )

            else:

                pnl_status = (
                    "🟡 تعادل"
                )

            # ==================================================
            # Append Result
            # ==================================================

            portfolio_results.append({

                # ----------------------------------------------
                # Basic
                # ----------------------------------------------

                "ticker":
                    ticker,

                "shares":
                    shares,

                "buy_price":
                    round(
                        buy_price,
                        3
                    ),

                # ----------------------------------------------
                # Current Price
                # ----------------------------------------------

                "current_price":
                    round(
                        current_price,
                        2
                    ),

                "historical_close":
                    round(
                        historical_close,
                        2
                    ),

                "strategy_price":
                    round(
                        strategy_price,
                        2
                    ),

                "price_source":
                    price_source,

                "is_realtime":
                    is_realtime,

                "current_vs_close_pct":
                    round(
                        current_vs_close_pct,
                        2
                    ),

                # ----------------------------------------------
                # Portfolio
                # ----------------------------------------------

                "cost_value":
                    round(
                        cost_value,
                        2
                    ),

                "current_value":
                    round(
                        current_value,
                        2
                    ),

                "pnl_egp":
                    round(
                        pnl_egp,
                        2
                    ),

                "pnl_pct":
                    round(
                        pnl_pct,
                        2
                    ),

                "pnl_status":
                    pnl_status,

                # ----------------------------------------------
                # Technical
                # ----------------------------------------------

                "ema20":
                    round(
                        ema20,
                        2
                    ),

                "ma200":
                    round(
                        ma200,
                        2
                    ),

                "rsi":
                    round(
                        rsi,
                        2
                    ),

                "support":
                    round(
                        support,
                        2
                    ),

                "resistance":
                    round(
                        resistance,
                        2
                    ),

                "atr":
                    round(
                        atr,
                        2
                    ),

                # ----------------------------------------------
                # Strategy
                # ----------------------------------------------

                "score":
                    score,

                "advice":
                    advice,

                "reason":
                    reason,

                "entry_status":
                    entry_status,

                "stop_loss":
                    stop_loss,

                "tp1":
                    tp1,

                "tp2":
                    tp2,

                "rr1":
                    rr1,

                "rr2":
                    rr2,

                "exit_strategy":
                    exit_strategy,

                # ----------------------------------------------
                # Source
                # ----------------------------------------------

                "data_source":
                    data_source,
            })

        except Exception as e:

            print(
                f"❌ خطأ أثناء تحليل {ticker}: {e}"
            )

            continue

    return portfolio_results
