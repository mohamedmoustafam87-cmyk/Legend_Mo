import requests
import pandas as pd

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

            "Open": quote.get("open"),

            "High": quote.get("high"),

            "Low": quote.get("low"),

            "Close": quote.get("close"),

            "Volume": quote.get("volume")

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

        recent = df.tail(20).copy()

        average_volume = (
            recent["Volume"]
            .mean()
        )

        average_daily_value = (
            recent["Close"] *
            recent["Volume"]
        ).mean()

        if (
            average_volume <
            MIN_AVG_VOLUME
        ):

            return False

        if (
            average_daily_value <
            MIN_AVG_DAILY_VALUE
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
        f"📊 EGX Universe: {total_stocks} stocks"
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
                f"⚠️ Skipping {symbol}"
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
        # Evaluate Complete Strategy
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
                f"Score={score}"
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
