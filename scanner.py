import requests
import pandas as pd

from config import (
    EGX_STOCKS,
    SHARIA_EGX_STOCKS,
    MIN_SCORE_THRESHOLD,
    MIN_AVG_DAILY_VALUE,
    MIN_AVG_VOLUME,
)

from indicators import calculate_indicators
from strategy import evaluate_stock_strategy


# ==========================================================
# API Configuration
# ==========================================================

YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/"
)

MUBASHER_URL = (
    "https://www.mubasher.info/api/1/market/stocks?country=eg"
)

REQUEST_TIMEOUT = 15


# ==========================================================
# Helpers
# ==========================================================

def clean_symbol(symbol):
    """
    Convert:
        COMI.CA -> COMI
        NIPH.CA -> NIPH
    """

    if symbol is None:
        return ""

    return str(symbol).upper().replace(".CA", "").strip()


def safe_float(value, default=None):

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
# Mubasher Current Prices
# ==========================================================

def fetch_mubasher_prices():

    try:

        response = requests.get(
            MUBASHER_URL,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64)"
                )
            }
        )

        response.raise_for_status()

        payload = response.json()

        data = payload.get("data", [])

        if not isinstance(data, list):
            return {}

        prices = {}

        for item in data:

            if not isinstance(item, dict):
                continue

            symbol = (
                item.get("symbol")
                or item.get("code")
                or item.get("ticker")
            )

            price = (
                item.get("price")
                or item.get("last")
                or item.get("lastPrice")
                or item.get("close")
            )

            symbol = clean_symbol(symbol)
            price = safe_float(price)

            if symbol and price is not None and price > 0:

                prices[symbol] = price

        return prices

    except Exception:

        return {}


# ==========================================================
# Yahoo Historical Data
# ==========================================================

def fetch_yahoo_history(
    symbol,
    period="2y",
    interval="1d"
):

    try:

        url = (
            YAHOO_CHART_URL
            + symbol
        )

        response = requests.get(
            url,
            params={
                "range": period,
                "interval": interval,
                "events": "history",
                "includeAdjustedClose": "true",
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64)"
                )
            }
        )

        response.raise_for_status()

        payload = response.json()

        result = (
            payload
            .get("chart", {})
            .get("result")
        )

        if not result:
            return None

        result = result[0]

        timestamps = result.get("timestamp")

        indicators = result.get(
            "indicators",
            {}
        )

        quote = indicators.get(
            "quote",
            []
        )

        if not timestamps or not quote:
            return None

        quote = quote[0]

        df = pd.DataFrame(
            {
                "Open": quote.get("open"),
                "High": quote.get("high"),
                "Low": quote.get("low"),
                "Close": quote.get("close"),
                "Volume": quote.get("volume"),
            },
            index=pd.to_datetime(
                timestamps,
                unit="s"
            )
        )

        if df.empty:
            return None

        df.index.name = "Date"

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
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

        df.sort_index(
            inplace=True
        )

        if len(df) < 220:
            return None

        return df

    except Exception:

        return None


# ==========================================================
# Current Price Metadata
# ==========================================================

def get_stock_data(
    symbol,
    mubasher_prices=None
):

    symbol = str(symbol).upper().strip()

    df = fetch_yahoo_history(
        symbol
    )

    if df is None or df.empty:

        return None, "No Data"

    historical_close = safe_float(
        df["Close"].iloc[-1]
    )

    if historical_close is None or historical_close <= 0:

        return None, "Invalid Historical Data"

    # ------------------------------------------------------
    # Current Mubasher Price
    # ------------------------------------------------------

    mubasher_price = None

    if mubasher_prices is not None:

        mubasher_price = mubasher_prices.get(
            clean_symbol(symbol)
        )

    # ------------------------------------------------------
    # Determine Current Price
    # ------------------------------------------------------

    if (
        mubasher_price is not None
        and mubasher_price > 0
    ):

        current_price = mubasher_price

        price_source = (
            "Mubasher Current"
        )

        is_realtime = True

        data_source = (
            "Yahoo Historical + Mubasher Current"
        )

    else:

        current_price = historical_close

        price_source = (
            "Yahoo Last Close"
        )

        is_realtime = False

        data_source = (
            "Yahoo Historical + Yahoo Last Close"
        )

    # ------------------------------------------------------
    # Metadata
    # ------------------------------------------------------

    current_vs_close_pct = (
        (
            current_price -
            historical_close
        )
        /
        historical_close
    ) * 100

    df.attrs["symbol"] = symbol

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

    df.attrs["data_source"] = (
        data_source
    )

    return df, data_source


# ==========================================================
# Validate Current Price
# ==========================================================

def validate_current_price(
    df
):

    if df is None or df.empty:
        return False

    price = safe_float(
        df.attrs.get(
            "current_price"
        )
    )

    return (
        price is not None
        and price > 0
    )


# ==========================================================
# Liquidity Filter
# ==========================================================

def passes_liquidity_filter(
    df
):

    if df is None or df.empty:
        return False

    sample = df.tail(20).copy()

    if len(sample) < 20:
        return False

    sample["DailyValue"] = (
        sample["Close"] *
        sample["Volume"]
    )

    avg_daily_value = (
        sample["DailyValue"]
        .mean()
    )

    avg_volume = (
        sample["Volume"]
        .mean()
    )

    if (
        avg_daily_value <
        MIN_AVG_DAILY_VALUE
    ):
        return False

    if (
        avg_volume <
        MIN_AVG_VOLUME
    ):
        return False

    return True


# ==========================================================
# Scan Market
# ==========================================================

def scan_market():

    mubasher_prices = (
        fetch_mubasher_prices()
    )

    results = []

    for symbol in EGX_STOCKS:

        try:

            # --------------------------------------------------
            # Sharia Filter
            # --------------------------------------------------

            if symbol not in SHARIA_EGX_STOCKS:
                continue

            # --------------------------------------------------
            # Historical Data
            # --------------------------------------------------

            df, data_source = get_stock_data(
                symbol,
                mubasher_prices
            )

            if df is None:
                continue

            # --------------------------------------------------
            # Liquidity
            # --------------------------------------------------

            if not passes_liquidity_filter(df):
                continue

            # --------------------------------------------------
            # Preserve Current Price Metadata
            # --------------------------------------------------

            metadata = {
                "current_price":
                    df.attrs.get(
                        "current_price"
                    ),

                "historical_close":
                    df.attrs.get(
                        "historical_close"
                    ),

                "price_source":
                    df.attrs.get(
                        "price_source"
                    ),

                "is_realtime":
                    df.attrs.get(
                        "is_realtime",
                        False
                    ),

                "current_vs_close_pct":
                    df.attrs.get(
                        "current_vs_close_pct"
                    ),

                "data_source":
                    df.attrs.get(
                        "data_source"
                    ),
            }

            # --------------------------------------------------
            # Indicators
            # --------------------------------------------------

            df = calculate_indicators(
                df
            )

            if df is None:
                continue

            # Restore metadata
            for key, value in metadata.items():

                df.attrs[key] = value

            # --------------------------------------------------
            # Strategy
            # --------------------------------------------------

            analysis = evaluate_stock_strategy(
                df,
                symbol
            )

            if analysis is None:
                continue

            # --------------------------------------------------
            # Current Price Information
            # --------------------------------------------------

            analysis["current_price"] = (
                metadata["current_price"]
            )

            analysis["historical_close"] = (
                metadata["historical_close"]
            )

            analysis["current_vs_close_pct"] = (
                round(
                    metadata[
                        "current_vs_close_pct"
                    ],
                    2
                )
            )

            analysis["price_source"] = (
                metadata["price_source"]
            )

            analysis["is_realtime"] = (
                metadata["is_realtime"]
            )

            analysis["data_source"] = (
                metadata["data_source"]
            )

            # --------------------------------------------------
            # Historical Strategy Price
            # --------------------------------------------------

            analysis["strategy_price"] = (
                analysis["price"]
            )

            # --------------------------------------------------
            # DataFrame
            # --------------------------------------------------

            analysis["_dataframe"] = df

            results.append(
                analysis
            )

        except Exception:

            continue

    # ==========================================================
    # Sort By Score
    # ==========================================================

    results.sort(
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse=True
    )

    # ==========================================================
    # Minimum Score
    # ==========================================================

    filtered_results = [
        item
        for item in results
        if item.get(
            "score",
            0
        ) >= MIN_SCORE_THRESHOLD
    ]

    return filtered_results[:5]
