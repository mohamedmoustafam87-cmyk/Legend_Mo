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
# APIs Configuration
# ==========================================================

YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/"
)

MUBASHER_MARKET_API = (
    "https://www.mubasher.info/api/1/market/stocks?country=eg"
)

YAHOO_TIMEOUT = 15
MUBASHER_TIMEOUT = 10


# ==========================================================
# Helpers
# ==========================================================

def clean_symbol(symbol):
    """
    تنظيف رمز السهم.

    Examples:
        NIPH.CA -> NIPH
        NIPH    -> NIPH
    """

    if symbol is None:
        return None

    return (
        str(symbol)
        .strip()
        .upper()
        .replace(".CA", "")
    )


def safe_float(value):
    """
    تحويل آمن إلى float.
    """

    try:

        if value is None:
            return None

        if pd.isna(value):
            return None

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# ==========================================================
# Fetch All Mubasher Realtime Prices
# ==========================================================

def fetch_mubasher_prices():

    prices = {}

    try:

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
            MUBASHER_MARKET_API,
            headers=headers,
            timeout=MUBASHER_TIMEOUT
        )

        response.raise_for_status()

        payload = response.json()

        stocks_list = payload.get(
            "data",
            []
        )

        for stock in stocks_list:

            if not isinstance(
                stock,
                dict
            ):
                continue

            symbol_key = (
                stock.get("symbol")
                or stock.get("ric")
            )

            last_price = stock.get(
                "lastPrice"
            )

            symbol_key = clean_symbol(
                symbol_key
            )

            last_price = safe_float(
                last_price
            )

            if (
                symbol_key
                and last_price is not None
                and last_price > 0
            ):

                prices[symbol_key] = last_price

        print(
            f"✅ [مباشر] تم جلب "
            f"{len(prices)} سعر بنجاح"
        )

    except requests.exceptions.Timeout:

        print(
            "⏱️ [مباشر] Timeout "
            "أثناء جلب أسعار السوق"
        )

    except requests.exceptions.RequestException as e:

        print(
            f"🌐 [مباشر] خطأ في الشبكة: {e}"
        )

    except ValueError as e:

        print(
            f"📊 [مباشر] خطأ في قراءة JSON: {e}"
        )

    except Exception as e:

        print(
            f"❌ [مباشر] خطأ غير متوقع: {e}"
        )

    return prices


# ==========================================================
# Fetch Yahoo Historical Data
# ==========================================================

def fetch_yahoo_history(symbol):

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
            timeout=YAHOO_TIMEOUT
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
                f"❌ Yahoo error for "
                f"{symbol}: {error}"
            )

            return None

        results = chart.get(
            "result"
        )

        if not results:

            print(
                f"❌ No Yahoo data "
                f"available for {symbol}"
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

        if (
            not timestamps
            or not quotes
        ):

            print(
                f"❌ Invalid Yahoo data "
                f"for {symbol}"
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

        # ------------------------------------------------------
        # Convert timestamps
        # ------------------------------------------------------

        df.index = pd.to_datetime(
            timestamps,
            unit="s"
        )

        # ------------------------------------------------------
        # Remove duplicates
        # ------------------------------------------------------

        df = df[
            ~df.index.duplicated(
                keep="last"
            )
        ]

        # ------------------------------------------------------
        # Sort
        # ------------------------------------------------------

        df.sort_index(
            inplace=True
        )

        # ------------------------------------------------------
        # Convert numeric columns
        # ------------------------------------------------------

        numeric_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # ------------------------------------------------------
        # Remove invalid rows
        # ------------------------------------------------------

        df.dropna(
            subset=numeric_columns,
            inplace=True
        )

        return df

    except requests.exceptions.Timeout:

        print(
            f"⏱️ Yahoo Timeout: {symbol}"
        )

    except requests.exceptions.RequestException as e:

        print(
            f"🌐 Yahoo Network Error "
            f"{symbol}: {e}"
        )

    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError
    ) as e:

        print(
            f"📊 Yahoo Parsing Error "
            f"{symbol}: {e}"
        )

    except Exception as e:

        print(
            f"❌ Yahoo Unexpected Error "
            f"{symbol}: {e}"
        )

    return None


# ==========================================================
# Get Stock Data
# Hybrid:
# Yahoo Historical + Mubasher Realtime
# Mubasher Failure -> Yahoo Last Close
# ==========================================================

def get_stock_data(
    symbol,
    mubasher_prices=None
):

    clean = clean_symbol(
        symbol
    )

    # ------------------------------------------------------
    # 1. Get Yahoo historical data
    # ------------------------------------------------------

    df = fetch_yahoo_history(
        symbol
    )

    if df is None or df.empty:

        print(
            f"❌ {symbol} "
            f"→ Yahoo historical data unavailable"
        )

        return None, "No Data"

    # ------------------------------------------------------
    # Minimum history
    # ------------------------------------------------------

    if len(df) < 220:

        print(
            f"⚠️ {symbol} "
            f"→ Not enough historical data: "
            f"{len(df)} rows"
        )

        return None, "Insufficient Data"

    # ------------------------------------------------------
    # Last historical
