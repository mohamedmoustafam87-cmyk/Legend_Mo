import requests
import pandas as pd
import re
import json
from datetime import datetime

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
# Yahoo Finance
# ==========================================================

YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/"
)


# ==========================================================
# Mubasher
# ==========================================================

MUBASHER_URL = (
    "https://www.mubasher.info/markets/EGX/stocks/"
)


# ==========================================================
# Common Headers
# ==========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Connection": "keep-alive",
}


# ==========================================================
# Get Current Price From Mubasher
# ==========================================================

def get_mubasher_current_price(symbol):

    ticker = (
        symbol
        .replace(".CA", "")
        .strip()
        .upper()
    )

    url = f"{MUBASHER_URL}{ticker}"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        html = response.text

        # --------------------------------------------------
        # Try to find structured JSON values
        # --------------------------------------------------

        patterns = [

            r'"lastPrice"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"last_price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"last"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"Last"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"currentPrice"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"current_price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

            r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',

        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                html,
                flags=re.IGNORECASE
            )

            if matches:

                # --------------------------------------------------
                # Take the first valid positive price
                # --------------------------------------------------

                for value in matches:

                    try:

                        price = float(value)

                        if price > 0:

                            return price

                    except (TypeError, ValueError):

                        continue

        # --------------------------------------------------
        # No price found
        # --------------------------------------------------

        print(
            f"❌ فشل الوصول إلى Mubasher لـ {ticker}"
        )

        return None

    except requests.exceptions.Timeout:

        print(
            f"❌ فشل الوصول إلى Mubasher لـ {ticker} "
            f"(Timeout)"
        )

        return None

    except requests.exceptions.RequestException as e:

        print(
            f"❌ فشل الوصول إلى Mubasher لـ {ticker}: {e}"
        )

        return None

    except Exception as e:

        print(
            f"❌ فشل قراءة بيانات Mubasher لـ {ticker}: {e}"
        )

        return None


# ==========================================================
# Get Historical Data From Yahoo Finance
# ==========================================================

def get_yahoo_stock_data(symbol):

    try:

        url = (
            f"{YAHOO_URL}{symbol}"
            f"?interval=1d"
            f"&range=2y"
            f"&events=history"
            f"&includeAdjustedClose=true"
        )

        response = requests.get(
            url,
            headers=HEADERS,
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
            f"⏱️ Timeout while fetching Yahoo {symbol}"
        )

        return None

    except requests.exceptions.RequestException as e:

        print(
            f"🌐 Yahoo network error for {symbol}: {e}"
        )

        return None

    except Exception as e:

        print(
            f"❌ Yahoo error for {symbol}: {e}"
        )

        return None


# ==========================================================
# Add Current Session Price
# ==========================================================

def add_current_mubasher_price(
    df,
    symbol
):

    try:

        current_price = (
            get_mubasher_current_price(
                symbol
            )
        )

        # --------------------------------------------------
        # Mubasher failed
        # --------------------------------------------------

        if current_price is None:

            print(
                f"⚠️ {symbol}: "
                f"فشل الوصول إلى Mubasher "
                f"→ تم استخدام Yahoo Finance"
            )

            return df

        # --------------------------------------------------
        # Current date
        # --------------------------------------------------

        today = pd.Timestamp.now().normalize()

        # --------------------------------------------------
        # Check whether Yahoo already has today's session
        # --------------------------------------------------

        last_date = (
            pd.Timestamp(
                df.index[-1]
            ).normalize()
        )

        # --------------------------------------------------
        # Yahoo already contains today's row
        # --------------------------------------------------

        if last_date == today:

            df.iloc[
                -1,
                df.columns.get_loc("Close")
            ] = current_price

            print(
                f"✅ {symbol} | "
                f"Mubasher = {current_price:.2f} "
                f"| Updated today's Close"
            )

            return df

        # --------------------------------------------------
        # Yahoo does not have today's row
        # Create a new intraday/current-session row.
        # --------------------------------------------------

        previous_close = float(
            df.iloc[-1]["Close"]
        )

        new_row = pd.DataFrame(
            {
                "Open": [previous_close],

                "High": [
                    max(
                        previous_close,
                        current_price
                    )
                ],

                "Low": [
                    min(
                        previous_close,
                        current_price
                    )
                ],

                "Close": [current_price],

                "Volume": [0]
            },
            index=[today]
        )

        df = pd.concat(
            [
                df,
                new_row
            ]
        )

        print(
            f"✅ {symbol} | "
            f"Mubasher current price = "
            f"{current_price:.2f}"
        )

        return df

    except Exception as e:

        print(
            f"❌ Error updating Mubasher price "
            f"for {symbol}: {e}"
        )

        print(
            f"⚠️ {symbol}: "
            f"فشل الوصول إلى Mubasher "
            f"→ تم استخدام Yahoo Finance"
        )

        return df


# ==========================================================
# Get Stock Data
# ==========================================================

def get_stock_data(symbol):

    # ------------------------------------------------------
    # 1. Historical data from Yahoo
    # ------------------------------------------------------

    df = get_yahoo_stock_data(
        symbol
    )

    if df is None or df.empty:

        return None

    # ------------------------------------------------------
    # 2. Current session price from Mubasher
    # ------------------------------------------------------

    df = add_current_mubasher_price(
        df,
        symbol
    )

    return df


# ==========================================================
# Liquidity Filter
# ==========================================================

def passes_liquidity_filter(df):

    try:

        if df is None or df.empty:

            return False

        if len(df) < 20:

            return False

        recent = (
            df.tail(20)
            .copy()
        )

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

    # ======================================================
    # Scan Every EGX Stock
    # ======================================================

    for index, symbol in enumerate(
        EGX_STOCKS,
        start=1
    ):

        print(
            f"[{index}/{total_stocks}] "
            f"📊 Scanning {symbol}..."
        )

        # ==================================================
        # Sharia Filter
        # ==================================================

        if symbol not in sharia_stocks:

            print(
                f"☪️ {symbol} "
                f"→ غير موجود في قائمة "
                f"التوافق الشرعي"
            )

            continue

        # ==================================================
        # Get Market Data
        # ==================================================

        df = get_stock_data(
            symbol
        )

        if df is None or df.empty:

            print(
                f"⚠️ Skipping {symbol}"
            )

            continue

        # ==================================================
        # Liquidity Filter
        # ==================================================

        if not passes_liquidity_filter(
            df
        ):

            print(
                f"💧 {symbol} "
                f"→ السيولة أقل من الحد المطلوب"
            )

            continue

        # ==================================================
        # Calculate Technical Indicators
        # ==================================================

        df = calculate_indicators(
            df
        )

        if df is None or df.empty:

            print(
                f"⚠️ Could not calculate indicators "
                f"for {symbol}"
            )

            continue

        # ==================================================
        # Evaluate Complete Strategy
        # ==================================================

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

        # ==================================================
        # Score
        # ==================================================

        score = int(
            analysis.get(
                "score",
                0
            )
        )

        # ==================================================
        # Minimum Score Filter
        # ==================================================

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

    # ======================================================
    # Sort and Filter Top 5 Opportunities Only
    # ======================================================

    opportunities.sort(
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse
