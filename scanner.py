import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

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

REQUEST_TIMEOUT = 15

# عدد الأسهم اللي بتتفحص بالتوازي
MAX_WORKERS = 6

# أكواد HTTP اللي يستحق نعيد فيها المحاولة
RETRY_STATUS = {429, 500, 502, 503, 504}

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

YAHOO_HEADERS = {
    "User-Agent": BROWSER_UA,
}


# ملاحظة: تمت إزالة جلب أسعار مباشر بالكامل - المصدر الوحيد Yahoo Finance.
# الدالة التالية موجودة للتوافق فقط مع باقي ملفات المشروع (portfolio.py و app.py)
# اللي لسه بتستوردها بالاسم، وبترجع قاموس فاضي بدون أي اتصال خارجي.
def fetch_mubasher_prices():
    return {}

# ==========================================================
# Helpers
# ==========================================================

def clean_symbol(symbol):
    """
    COMI.CA -> COMI
    """

    if symbol is None:
        return ""

    return (
        str(symbol)
        .upper()
        .replace(".CA", "")
        .strip()
    )


def safe_float(value, default=None):

    try:

        if value is None:
            return default

        value = float(value)

        if pd.isna(value):
            return default

        return value

    except (TypeError, ValueError):

        return default


def http_get(url, params=None, headers=None, retries=2):
    """
    GET مع إعادة محاولة عند Timeout / مشاكل شبكة / 429 / أخطاء السيرفر.
    بيرجع Response (حتى لو status مش 200) أو None لو مفيش رد خالص.
    """

    for attempt in range(1, retries + 2):

        try:

            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            if (
                response.status_code in RETRY_STATUS
                and attempt <= retries
            ):
                time.sleep(1.5 * attempt)
                continue

            return response

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        ) as e:

            if attempt > retries:
                print(f"⚠️ Network failure for {url}: {e}")
                return None

            time.sleep(1.5 * attempt)

        except requests.exceptions.RequestException as e:

            print(f"⚠️ Request error for {url}: {e}")
            return None

    return None


# ==========================================================
# Yahoo Historical Data
# ==========================================================

def fetch_yahoo_history(
    symbol,
    period="2y",
    interval="1d"
):

    response = http_get(
        YAHOO_CHART_URL + symbol,
        params={
            "range": period,
            "interval": interval,
            "events": "history",
            "includeAdjustedClose": "true",
        },
        headers=YAHOO_HEADERS
    )

    if response is None:
        return None

    if response.status_code != 200:

        print(f"⚠️ Yahoo {symbol}: status={response.status_code}")
        return None

    try:

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

        quote = (
            result
            .get("indicators", {})
            .get("quote", [])
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
            "Volume",
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
                "Volume",
            ],
            inplace=True
        )

        df = df[~df.index.duplicated(keep="last")]

        df.sort_index(inplace=True)

        if len(df) < 220:
            return None

        return df

    except Exception as e:

        print(f"⚠️ Yahoo parse error for {symbol}: {e}")
        return None


# ==========================================================
# Stock Data (Yahoo History Only)
# ==========================================================

def get_stock_data(symbol, legacy_prices=None):
    """
    بيرجع (df, data_source) من Yahoo Finance فقط.
    السعر المستخدم هو آخر إغلاق متاح من ياهو.
    legacy_prices: معامل قديم لم يعد مستخدمًا (تمت إزالة مباشر).
    """

    symbol = (
        str(symbol)
        .upper()
        .strip()
    )

    df = fetch_yahoo_history(symbol)

    if df is None or df.empty:
        return None, "No Data"

    historical_close = safe_float(
        df["Close"].iloc[-1]
    )

    if (
        historical_close is None
        or historical_close <= 0
    ):
        return None, "Invalid Historical Data"

    # ------------------------------------------------------
    # ------------------------------------------------------
    # Yahoo Last Close هو السعر المعتمد
    # ------------------------------------------------------

    current_price = historical_close
    price_source = "Yahoo Last Close"
    is_realtime = False
    data_source = "Yahoo Finance (إغلاق سابق)"

    # ------------------------------------------------------
    # Metadata
    # ------------------------------------------------------

    df.attrs["symbol"] = symbol
    df.attrs["current_price"] = current_price
    df.attrs["historical_close"] = historical_close
    df.attrs["price_source"] = price_source
    df.attrs["is_realtime"] = is_realtime
    df.attrs["current_vs_close_pct"] = 0.0
    df.attrs["data_source"] = data_source

    return df, data_source


# ==========================================================
# Validate Current Price
# ==========================================================

def validate_current_price(df):

    if df is None or df.empty:
        return False

    price = safe_float(
        df.attrs.get("current_price")
    )

    return (
        price is not None
        and price > 0
    )


# ==========================================================
# Liquidity Filter
# ==========================================================

def passes_liquidity_filter(df):

    if df is None or df.empty:
        return False

    sample = df.tail(20).copy()

    if len(sample) < 20:
        return False

    avg_daily_value = (
        sample["Close"]
        * sample["Volume"]
    ).mean()

    avg_volume = sample["Volume"].mean()

    if avg_daily_value < MIN_AVG_DAILY_VALUE:
        return False

    if avg_volume < MIN_AVG_VOLUME:
        return False

    return True


# ==========================================================
# Process One Symbol
# ==========================================================

def process_symbol(symbol):
    """
    بيفحص سهم واحد ويرجع analysis أو None.
    بيتنفذ جوه threads.
    """

    df, data_source = get_stock_data(symbol)

    if df is None:
        return None

    if not validate_current_price(df):

        print(f"⚠️ Invalid current price: {symbol}")
        return None

    if not passes_liquidity_filter(df):
        return None

    metadata = dict(df.attrs)

    df = calculate_indicators(df)

    if df is None:
        return None

    # شرطا الاتجاه الإلزاميان للترشيح (معتمدان من المستخدم):
    # السعر فوق MA200 و EMA20 فوق EMA50 - شرطان لا تعوّضهما النقاط.
    # القيم الفارغة (NaN) تفشل الشرط تلقائيًا فيُستبعد السهم.
    latest_row = df.iloc[-1]

    if not (
        float(latest_row["Close"]) > float(latest_row["MA_200"])
        and float(latest_row["EMA_20"]) > float(latest_row["EMA_50"])
    ):
        return None

    analysis = evaluate_stock_strategy(
        df,
        symbol
    )

    if analysis is None:
        return None

    analysis["current_price"] = metadata.get("current_price")
    analysis["historical_close"] = metadata.get("historical_close")
    analysis["current_vs_close_pct"] = metadata.get("current_vs_close_pct")
    analysis["price_source"] = metadata.get("price_source")
    analysis["is_realtime"] = metadata.get("is_realtime", False)
    analysis["data_source"] = metadata.get("data_source", data_source)

    # السعر اللي الاستراتيجية استخدمته فعليًا
    analysis["strategy_price"] = analysis.get(
        "price",
        metadata.get("current_price")
    )

    return analysis


# ==========================================================
# Scan Market
# ==========================================================

def scan_market():

    print("🔎 Starting market scan...")

    sharia_set = set(SHARIA_EGX_STOCKS)

    symbols = [
        symbol
        for symbol in EGX_STOCKS
        if symbol in sharia_set
    ]

    print(
        f"📊 Scanning {len(symbols)} stocks "
        f"({MAX_WORKERS} parallel workers)..."
    )

    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {

            executor.submit(
                process_symbol,
                symbol
            ): symbol

            for symbol in symbols
        }

        for future in as_completed(futures):

            symbol = futures[future]

            try:

                analysis = future.result()

            except Exception as e:

                print(f"⚠️ Error scanning {symbol}: {e}")
                continue

            if analysis is not None:
                results.append(analysis)

    # ------------------------------------------------------
    # Sort + Minimum Score
    # ------------------------------------------------------

    results.sort(
        key=lambda x: safe_float(x.get("score", 0), 0),
        reverse=True
    )

    filtered_results = [

        item

        for item in results

        if safe_float(item.get("score", 0), 0)
        >= MIN_SCORE_THRESHOLD
    ]

    print(f"📊 Qualified stocks: {len(filtered_results)}")

    return filtered_results[:5]