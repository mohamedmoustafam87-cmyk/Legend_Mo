import requests
import pandas as pd

from datetime import datetime
from zoneinfo import ZoneInfo

from config import (
    EGX_STOCKS,
    SHARIA_EGX_STOCKS,
    MIN_SCORE_THRESHOLD,
    MIN_AVG_DAILY_VALUE,
    MIN_AVG_VOLUME
)

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy


# ==========================================================
# Yahoo Finance API
# ==========================================================

YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/"
)


# ==========================================================
# Cairo Timezone
# ==========================================================

CAIRO_TZ = ZoneInfo(
    "Africa/Cairo"
)


# ==========================================================
# Get Stock Data
# ==========================================================

def get_stock_data(symbol):

    try:

        url = (
            f"{YAHOO_URL}{symbol}"
            f"?interval=1d"
            f"&range=2y"
            f"&events=history"
            f"&includeAdjustedClose=true"
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        chart = data.get(
            "chart",
            {}
        )

        error = chart.get(
            "error"
        )

        if error:

            print(
                f"Yahoo error for {symbol}: {error}"
            )

            return None


        results = chart.get(
            "result"
        )

        if not results:

            print(
                f"No Yahoo data available for {symbol}"
            )

            return None


        result = results[0]


        # ======================================================
        # Yahoo Metadata
        # ======================================================

        meta = result.get(
            "meta",
            {}
        )

        regular_market_price = meta.get(
            "regularMarketPrice"
        )

        regular_market_time = meta.get(
            "regularMarketTime"
        )


        # ======================================================
        # Validate Current Market Price
        # ======================================================

        if regular_market_price is None:

            print(
                f"⚠️ {symbol} → "
                f"Yahoo did not provide regularMarketPrice"
            )

            return None


        if regular_market_time is None:

            print(
                f"⚠️ {symbol} → "
                f"Yahoo did not provide regularMarketTime"
            )

            return None


        try:

            regular_market_price = float(
                regular_market_price
            )

            regular_market_time = int(
                regular_market_time
            )

        except (
            TypeError,
            ValueError
        ):

            print(
                f"⚠️ {symbol} → "
                f"Invalid Yahoo market metadata"
            )

            return None


        if regular_market_price <= 0:

            print(
                f"⚠️ {symbol} → "
                f"Invalid current market price"
            )

            return None


        # ======================================================
        # Convert Yahoo Timestamp To Cairo Time
        # ======================================================

        market_datetime = datetime.fromtimestamp(
            regular_market_time,
            tz=CAIRO_TZ
        )

        market_date = (
            market_datetime.date()
        )

        cairo_now = datetime.now(
            CAIRO_TZ
        )

        cairo_today = (
            cairo_now.date()
        )


        # ======================================================
        # Freshness Check
        # ======================================================

        if market_date != cairo_today:

            print(
                f"⛔ {symbol} → "
                f"STALE SESSION"
            )

            print(
                f"   Yahoo market time: "
                f"{market_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"   Cairo current date: "
                f"{cairo_today}"
            )

            print(
                f"   Current Yahoo price: "
                f"{regular_market_price:.2f}"
            )

            return None


        # ======================================================
        # Get Historical Daily Data
        # ======================================================

        timestamps = result.get(
            "timestamp"
        )

        indicators = result.get(
            "indicators",
            {}
        )

        quotes = indicators.get(
            "quote"
        )


        if not timestamps or not quotes:

            print(
                f"Invalid Yahoo data for {symbol}"
            )

            return None


        quote = quotes[0]


        df = pd.DataFrame({

            "Open": quote.get(
                "open"
            ),

            "High": quote.get(
                "high"
            ),

            "Low": quote.get(
                "low"
            ),

            "Close": quote.get(
                "close"
            ),

            "Volume": quote.get(
                "volume"
            )

        })


        df.index = pd.to_datetime(
            timestamps,
            unit="s"
        )


        df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ],
            inplace=True
        )


        df = df[
            ~df.index.duplicated(
                keep="last"
            )
        ]


        df.sort_index(
            inplace=True
        )


        if len(df) < 220:

            print(
                f"Not enough data for {symbol}: "
                f"{len(df)} rows"
            )

            return None


        # ======================================================
        # Historical Close
        # ======================================================

        historical_close = float(
            df["Close"].iloc[-1]
        )


        # ======================================================
        # Store Yahoo Current Market Data
        #
        # IMPORTANT:
        # لا نعدل df["Close"]
        #
        # Close يظل آخر Daily Close تاريخي.
        #
        # السعر الحالي يتم تخزينه منفصلاً داخل attrs.
        # ======================================================

        df.attrs[
            "regular_market_price"
        ] = regular_market_price

        df.attrs[
            "regular_market_time"
        ] = regular_market_time

        df.attrs[
            "regular_market_datetime"
        ] = market_datetime

        df.attrs[
            "price_status"
        ] = "fresh"


        # ======================================================
        # Display Data Difference
        # ======================================================

        print(
            f"💵 {symbol} → "
            f"Yahoo Current Price: "
            f"{regular_market_price:.2f}"
        )

        print(
            f"📊 {symbol} → "
            f"Latest Daily Close: "
            f"{historical_close:.2f}"
        )


        if historical_close > 0:

            difference_pct = (
                (
                    regular_market_price
                    - historical_close
                )
                / historical_close
            ) * 100

            print(
                f"📈 {symbol} → "
                f"Current vs Daily Close: "
                f"{difference_pct:+.2f}%"
            )


        print(
            f"🕐 {symbol} → "
            f"Market Time: "
            f"{market_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
        )


        return df


    except requests.exceptions.Timeout:

        print(
            f"⏱️ Timeout while fetching {symbol}"
        )

        return None


    except requests.exceptions.RequestException as e:

        print(
            f"🌐 Network error for {symbol}: {e}"
        )

        return None


    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError
    ) as e:

        print(
            f"📊 Data parsing error for {symbol}: {e}"
        )

        return None


    except Exception as e:

        print(
            f"❌ Unexpected error for {symbol}: {e}"
        )

        return None


# ==========================================================
# Liquidity Filter
# ==========================================================

def passes_liquidity_filter(df):

    try:

        if df is None or df.empty:

            return False


        if len(df) < 20:

            return False


        recent = df.tail(
            20
        ).copy()


        average_volume = (
            recent["Volume"]
            .mean()
        )


        average_daily_value = (
            recent["Close"]
            * recent["Volume"]
        ).mean()


        if (
            average_volume
            < MIN_AVG_VOLUME
        ):

            return False


        if (
            average_daily_value
            < MIN_AVG_DAILY_VALUE
        ):

            return False


        return True


    except (
        TypeError,
        ValueError,
        KeyError
    ):

        return False


# ==========================================================
# Scan Market
# ==========================================================

def scan_market():

    opportunities = []


    total_stocks = len(
        EGX_STOCKS
    )


    sharia_stocks = set(
        SHARIA_EGX_STOCKS
    )


    print(
        "\n===================================="
    )

    print(
        "🔎 Starting FULL EGX Market Scan"
    )

    print(
        f"📊 EGX Universe: "
        f"{total_stocks} stocks"
    )

    print(
        f"☪️ Sharia Filter: "
        f"{len(sharia_stocks)} stocks"
    )

    print(
        "====================================\n"
    )


    # ==========================================================
    # Scan Every EGX Stock
    # ==========================================================

    for index, symbol in enumerate(
        EGX_STOCKS,
        start=1
    ):

        print(
            f"[{index}/{total_stocks}] "
            f"📊 Scanning {symbol}..."
        )


        # ======================================================
        # Sharia Filter
        # ======================================================

        if symbol not in sharia_stocks:

            print(
                f"☪️ {symbol} "
                f"→ غير موجود في قائمة التوافق الشرعي"
            )

            continue


        # ======================================================
        # Get Market Data
        # ======================================================

        df = get_stock_data(
            symbol
        )


        if df is None or df.empty:

            print(
                f"⚠️ {symbol} "
                f"→ Skipped بسبب بيانات السعر"
            )

            continue


        # ======================================================
        # Liquidity Filter
        # ======================================================

        if not passes_liquidity_filter(
            df
        ):

            print(
                f"💧 {symbol} "
                f"→ السيولة أقل من الحد المطلوب"
            )

            continue


        # ======================================================
        # Calculate Technical Indicators
        #
        # IMPORTANT:
        # كل المؤشرات يتم حسابها من Daily Historical Data.
        # ======================================================

        df = calculate_indicators(
            df
        )


        if df is None or df.empty:

            print(
                f"⚠️ Could not calculate indicators "
                f"for {symbol}"
            )

            continue


        # ======================================================
        # Validate Current Yahoo Market Price
        #
        # لا نغير Close.
        # strategy.py سيقرأ السعر الحالي من attrs.
        # ======================================================

        current_market_price = (
            df.attrs.get(
                "regular_market_price"
            )
        )


        if (
            current_market_price is None
            or current_market_price <= 0
        ):

            print(
                f"⚠️ {symbol} "
                f"→ Invalid current market price"
            )

            continue


        regular_market_datetime = (
            df.attrs.get(
                "regular_market_datetime"
            )
        )


        if regular_market_datetime is None:

            print(
                f"⚠️ {symbol} "
                f"→ Missing market timestamp"
            )

            continue


        # ======================================================
        # Evaluate Complete Strategy
        #
        # Strategy uses:
        #
        # Historical Daily Data
        # +
        # Current Yahoo Market Price
        #
        # without modifying historical Close.
        # ======================================================

        analysis = evaluate_stock_strategy(
            df,
            symbol
        )


        if analysis is None:

            print(
                f"❌ {symbol} "
                f"→ لا توجد إشارة صالحة"
            )

            continue


        # ======================================================
        # Add Price Validation Information
        # ======================================================

        analysis[
            "price_source"
        ] = (
            "Yahoo Finance regularMarketPrice"
        )


        analysis[
            "price_status"
        ] = df.attrs.get(
            "price_status",
            "unknown"
        )


        analysis[
            "market_datetime"
        ] = (
            regular_market_datetime
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


        analysis[
            "historical_close"
        ] = round(
            float(
                df["Close"].iloc[-1]
            ),
            2
        )


        analysis[
            "current_market_price"
        ] = round(
            float(
                current_market_price
            ),
            2
        )


        # ======================================================
        # Score
        # ======================================================

        score = int(
            analysis.get(
                "score",
                0
            )
        )


        # ======================================================
        # Minimum Score Filter
        # ======================================================

        if score >= MIN_SCORE_THRESHOLD:

            opportunities.append(
                analysis
            )


            print(
                f"✅ Opportunity found: "
                f"{symbol} "
                f"Score={score} "
                f"Price={current_market_price:.2f}"
            )


        else:

            print(
                f"⚪ {symbol} "
                f"Score={score} "
                f"(below threshold)"
            )


    # ==========================================================
    # Sort Opportunities
    # ==========================================================

    opportunities.sort(
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse=True
    )


    # ==========================================================
    # Final Report
    # ==========================================================

    print(
        "\n===================================="
    )

    print(
        "🏆 FULL EGX SCAN COMPLETED"
    )

    print(
        f"📊 Universe: "
        f"{total_stocks} stocks"
    )

    print(
        f"☪️ Sharia Universe: "
        f"{len(sharia_stocks)} stocks"
    )

    print(
        f"🎯 Final Opportunities: "
        f"{len(opportunities)}"
    )

    print(
        "====================================\n"
    )


    return opportunities
