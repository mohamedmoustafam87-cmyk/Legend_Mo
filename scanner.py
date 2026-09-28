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

MUBASHER_MARKET_API = "https://www.mubasher.info/api/1/market/stocks?country=eg"


# ==========================================================
# جلب كل أسعار مباشر مرة واحدة
# ==========================================================

def fetch_mubasher_prices():
    prices = {}

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        resp = requests.get(
            MUBASHER_MARKET_API,
            headers=headers,
            timeout=10
        )

        if resp.status_code == 200:
            stocks_list = resp.json().get("data", [])

            for stock in stocks_list:
                symbol_key = stock.get("symbol") or stock.get("ric")
                last_price = stock.get("lastPrice")

                if symbol_key and last_price:
                    try:
                        prices[symbol_key] = float(last_price)
                    except (TypeError, ValueError):
                        continue

            print(
                f"✅ [مباشر] تم جلب {len(prices)} سعر لحظي بنجاح"
            )
        else:
            print(
                f"⚠️ [مباشر] فشل الطلب - status code: {resp.status_code}"
            )

    except requests.exceptions.Timeout:
        print("⏱️ [مباشر] Timeout أثناء جلب أسعار السوق")

    except requests.exceptions.RequestException as e:
        print(f"🌐 [مباشر] خطأ في الشبكة: {e}")

    except Exception as e:
        print(f"❌ [مباشر] خطأ غير متوقع: {e}")

    return prices


# ==========================================================
# Get Stock Data (Hybrid: Mubasher Realtime First, Yahoo Fallback)
# ==========================================================

def get_stock_data(symbol, mubasher_prices=None):
    clean_symbol = symbol.replace(".CA", "")
    data_source = "Yahoo Finance"

    mubasher_price = None
    if mubasher_prices:
        mubasher_price = mubasher_prices.get(clean_symbol)

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
            print(f"Yahoo error for {symbol}: {error}")
            return None

        results = chart.get(
            "result"
        )

        if not results:
            print(f"No Yahoo data available for {symbol}")
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
            print(f"Invalid Yahoo data for {symbol}")
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

        if mubasher_price and mubasher_price > 0:
            df.iloc[-1, df.columns.get_loc("Close")] = mubasher_price
            data_source = "مباشر (Mubasher Realtime - تأخير ~15 دقيقة)"
            print(f"🚀 [مصدر البيانات]: السهم {symbol} تم تحديث سعره من (مباشر)")
        else:
            data_source = "Yahoo Finance (إغلاق سابق)"
            print(f"📈 [مصدر البيانات]: الأسعار للسهم {symbol} من (Yahoo Finance)")

        if len(df) < 220:
            print(
                f"Not enough data for {symbol}: "
                f"{len(df)} rows"
            )
            return None

        # تخزين مصدر البيانات داخل الـ DataFrame لضمان التوافق وعدم إرجاع Tuple
        df.attrs["data_source"] = data_source

        return df

    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout while fetching {symbol}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error for {symbol}: {e}")
        return None

    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError
    ) as e:
        print(f"📊 Data parsing error for {symbol}: {e}")
        return None

    except Exception as e:
        print(f"❌ Unexpected error for {symbol}: {e}")
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

    mubasher_prices = fetch_mubasher_prices()

    for index, symbol in enumerate(
        EGX_STOCKS,
        start=1
    ):

        print(
            f"[{index}/{total_stocks}] "
            f"📊 Scanning {symbol}..."
        )

        if symbol not in sharia_stocks:
            print(
                f"☪️ {symbol} "
                f"→ غير موجود في قائمة التوافق الشرعي"
            )
            continue

        df = get_stock_data(
            symbol,
            mubasher_prices
        )

        if df is None or df.empty:
            print(
                f"⚠️ Skipping {symbol}"
            )
            continue

        data_source = df.attrs.get("data_source", "Yahoo Finance")

        if not passes_liquidity_filter(
            df
        ):
            print(
                f"💧 {symbol} "
                f"→ السيولة أقل من الحد المطلوب"
            )
            continue

        df = calculate_indicators(
            df
        )

        if df is None or df.empty:
            print(
                f"⚠️ Could not calculate indicators "
                f"for {symbol}"
            )
            continue

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

        analysis["data_source"] = data_source

        score = int(
            analysis.get(
                "score",
                0
            )
        )

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

    opportunities.sort(
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse=True
    )

    top_opportunities = opportunities[:5]

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
        f"🎯 Final Opportunities (Top 5): "
        f"{len(top_opportunities)}"
    )

    print(
        "====================================\n"
    )

    return top_opportunities
