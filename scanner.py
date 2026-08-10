import time
import requests
import pandas as pd

from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from config import (
    EGX_STOCKS,
    SHARIA_EGX_STOCKS,
    MIN_SCORE_THRESHOLD,
    MIN_AVG_DAILY_VALUE,
    MIN_AVG_VOLUME,
    EGX_HOLIDAYS_2026
)

from indicators import (
    calculate_indicators,
    analyze_candlesticks
)

from strategy import evaluate_stock_strategy


# ==========================================================
# Yahoo Finance API
#
# مهم: بنستخدم أكتر من subdomain (query1 / query2) كـ fallback،
# لأن IP بتاع GitHub Actions بيضرب أحياناً Cache قديم جداً عند
# Yahoo (لوحظ إرجاع regularMarketTime من سنتين كامل لكل الأسهم
# دفعة واحدة، وده مش طبيعي أبداً ولازم يترفض).
# ==========================================================

YAHOO_HOSTS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/",
    "https://query2.finance.yahoo.com/v8/finance/chart/",
]


# ==========================================================
# Shared HTTP Session + Rate Limiting
#
# مهم: البوت بيعمل ~230 طلب متتالي لـYahoo على كل تشغيل.
# من غير Session وتأخير بسيط بين الطلبات، فيه خطر حقيقي
# إن IP بتاع GitHub Actions يتحظر مؤقتاً أو يحصل timeout
# جماعي لباقي الأسهم.
# ==========================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
})

REQUEST_DELAY_SECONDS = 0.6

MAX_RETRIES = 2


# ==========================================================
# Cairo Timezone
# ==========================================================

CAIRO_TZ = ZoneInfo(
    "Africa/Cairo"
)


# ==========================================================
# EGX Trading Session
#
# EGX trading days:
# Sunday -> Thursday
#
# Normal session:
# 10:00 AM -> 2:30 PM Cairo time
# ==========================================================

EGX_OPEN_TIME = dt_time(
    10,
    0
)

EGX_CLOSE_TIME = dt_time(
    14,
    30
)


# ==========================================================
# Is EGX Holiday
#
# بيتحقق من تقويم عطلات EGX الرسمي (EGX_HOLIDAYS_2026 في
# config.py) بالإضافة إلى الجمعة/السبت. لازم يتحدّث القاموس
# ده كل سنة (راجع الملاحظة في config.py).
# ==========================================================

def is_egx_holiday(date_value):

    date_string = date_value.strftime(
        "%Y-%m-%d"
    )

    return date_string in EGX_HOLIDAYS_2026


# ==========================================================
# Get Last Expected Trading Day
#
# This handles:
#
# Friday
# Saturday
# Official EGX holidays (Eid, national holidays...)
#
# ويتجنب افتراض إن كل يوم تقويمي هو يوم تداول.
# ==========================================================

def get_previous_trading_day(date_value):

    current_date = date_value

    while True:

        current_date -= timedelta(
            days=1
        )

        # EGX trading days:
        # Sunday = 6
        # Monday = 0
        # Tuesday = 1
        # Wednesday = 2
        # Thursday = 3
        #
        # Friday = 4
        # Saturday = 5

        if (
            current_date.weekday() not in (4, 5)
            and not is_egx_holiday(current_date)
        ):

            return current_date


# ==========================================================
# Determine Expected Market Session
# ==========================================================

def get_market_session_status():

    cairo_now = datetime.now(
        CAIRO_TZ
    )

    today = cairo_now.date()

    current_time = cairo_now.time()

    weekday = today.weekday()


    # ======================================================
    # Friday / Saturday / Official EGX Holiday
    # ======================================================

    if (
        weekday in (4, 5)
        or is_egx_holiday(today)
    ):

        return {
            "status": "CLOSED_NON_TRADING_DAY",
            "today": today,
            "expected_date": get_previous_trading_day(
                today
            )
        }


    # ======================================================
    # Before Market Open
    # ======================================================

    if current_time < EGX_OPEN_TIME:

        return {
            "status": "PRE_MARKET",
            "today": today,
            "expected_date": get_previous_trading_day(
                today
            )
        }


    # ======================================================
    # During Market
    # ======================================================

    if (
        current_time >= EGX_OPEN_TIME
        and current_time <= EGX_CLOSE_TIME
    ):

        return {
            "status": "OPEN",
            "today": today,
            "expected_date": today
        }


    # ======================================================
    # After Market Close
    # ======================================================

    return {
        "status": "POST_MARKET",
        "today": today,
        "expected_date": today
    }


# ==========================================================
# Validate Yahoo Market Timestamp
# ==========================================================

def validate_market_freshness(
    market_datetime
):

    try:

        session = get_market_session_status()

        market_date = (
            market_datetime.date()
        )

        market_status = session[
            "status"
        ]

        expected_date = session[
            "expected_date"
        ]

        # ======================================================
        # OPEN MARKET
        #
        # During EGX session:
        # Yahoo price must belong to today's session.
        # ======================================================

        if market_status == "OPEN":

            if market_date != expected_date:

                return (
                    False,
                    "STALE_SESSION"
                )

            return (
                True,
                "FRESH_SESSION"
            )


        # ======================================================
        # POST MARKET
        #
        # After closing:
        # Today's closing/latest price is expected.
        # ======================================================

        if market_status == "POST_MARKET":

            if market_date == expected_date:

                return (
                    True,
                    "FRESH_CLOSED_SESSION"
                )

            # If Yahoo has not updated yet,
            # allow the most recent valid trading session
            # rather than rejecting everything.

            previous_date = (
                get_previous_trading_day(
                    expected_date
                )
            )

            if market_date == previous_date:

                return (
                    True,
                    "LAST_VALID_SESSION"
                )

            return (
                False,
                "STALE_SESSION"
            )


        # ======================================================
        # PRE MARKET
        #
        # Before EGX opens:
        # There cannot be a new EGX session price yet.
        #
        # Therefore the latest valid previous session
        # is accepted.
        # ======================================================

        if market_status == "PRE_MARKET":

            if market_date == expected_date:

                return (
                    True,
                    "PRE_MARKET_LAST_SESSION"
                )

            previous_date = (
                get_previous_trading_day(
                    expected_date
                )
            )

            if market_date == previous_date:

                return (
                    True,
                    "PRE_MARKET_LAST_SESSION"
                )

            return (
                False,
                "STALE_PRE_MARKET_PRICE"
            )


        # ======================================================
        # Friday / Saturday
        #
        # Accept the most recent trading session.
        # ======================================================

        if market_status == "CLOSED_NON_TRADING_DAY":

            if market_date == expected_date:

                return (
                    True,
                    "LAST_TRADING_SESSION"
                )

            previous_date = (
                get_previous_trading_day(
                    expected_date
                )
            )

            if market_date == previous_date:

                return (
                    True,
                    "LAST_TRADING_SESSION"
                )

            return (
                False,
                "STALE_NON_TRADING_DAY"
            )


        return (
            False,
            "UNKNOWN_SESSION"
        )


    except Exception as e:

        print(
            f"⚠️ Freshness validation error: {e}"
        )

        return (
            False,
            "VALIDATION_ERROR"
        )


# ==========================================================
# Fetch With Retry
#
# محاولة إضافية واحدة (Retry) لو حصل Timeout أو خطأ شبكة
# مؤقت، قبل ما نستسلم للسهم ده. ده بيقلل عدد الأسهم اللي
# بتضيع بسبب مشاكل شبكة عابرة.
# ==========================================================

def fetch_with_retry(symbol):

    last_error = None

    attempt = 0

    for host in YAHOO_HOSTS:

        for local_try in range(1, MAX_RETRIES + 1):

            attempt += 1

            # Cache-busting timestamp param — بيمنع أي CDN
            # أو Cache وسيط إنه يرجّع نسخة قديمة مخزّنة.

            cache_buster = int(
                time.time() * 1000
            )

            url = (
                f"{host}{symbol}"
                f"?interval=1d"
                f"&range=2y"
                f"&events=history"
                f"&includeAdjustedClose=true"
                f"&_={cache_buster}"
            )

            try:

                response = SESSION.get(
                    url,
                    timeout=15
                )

                response.raise_for_status()

                return response

            except requests.exceptions.RequestException as e:

                last_error = e

                if local_try < MAX_RETRIES:

                    time.sleep(
                        REQUEST_DELAY_SECONDS * local_try
                    )

    raise last_error


# ==========================================================
# Systemic Stale Cache Detection
#
# لو نفس الطابع الزمني القديم اتكرر لعدد كبير من الأسهم
# ورا بعض، ده مش مصادفة — ده مؤشر قوي إن Yahoo بيرجّع
# نسخة Cache قديمة موحدة (غالباً بسبب IP بتاع GitHub
# Actions). بنطبع تحذير واضح مرة واحدة بس عشان تعرف
# إن المشكلة نظامية مش خاصة بسهم معين.
# ==========================================================

_last_stale_timestamp = None
_consecutive_identical_stale = 0
_systemic_warning_shown = False


def track_systemic_stale_cache(market_time_unix):

    global _last_stale_timestamp
    global _consecutive_identical_stale
    global _systemic_warning_shown

    if market_time_unix == _last_stale_timestamp:

        _consecutive_identical_stale += 1

    else:

        _last_stale_timestamp = market_time_unix
        _consecutive_identical_stale = 1

    if (
        _consecutive_identical_stale >= 10
        and not _systemic_warning_shown
    ):

        _systemic_warning_shown = True

        print(
            "\n🚨 تحذير نظامي: أكثر من 10 أسهم متتالية "
            "رجعوا بنفس الطابع الزمني القديم بالظبط.\n"
            "🚨 ده مش مشكلة سهم واحد — على الأرجح Yahoo بيرجّع "
            "نسخة Cache قديمة لـIP بتاع GitHub Actions.\n"
            "🚨 راجع دعم fetch_with_retry / YAHOO_HOSTS، أو جرب "
            "تشغيل يدوي (workflow_dispatch) في وقت مختلف.\n"
        )


# ==========================================================
# Get Stock Data
# ==========================================================

def get_stock_data(symbol):

    try:

        response = fetch_with_retry(
            symbol
        )

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


        cairo_now = datetime.now(
            CAIRO_TZ
        )


        # ======================================================
        # Session-Aware Freshness Check
        # ======================================================

        freshness_ok, price_status = (
            validate_market_freshness(
                market_datetime
            )
        )


        if not freshness_ok:

            track_systemic_stale_cache(
                regular_market_time
            )

            print(
                f"⛔ {symbol} → "
                f"{price_status}"
            )

            print(
                f"   Yahoo market time: "
                f"{market_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"   Cairo current time: "
                f"{cairo_now.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"   Yahoo price: "
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
        ] = price_status


        df.attrs[
            "historical_close"
        ] = historical_close


        # ======================================================
        # Display Price Information
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


        print(
            f"🛡️ {symbol} → "
            f"Price Status: "
            f"{price_status}"
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
        #
        # ملاحظة: SHARIA_EGX_STOCKS == EGX_STOCKS حالياً،
        # يعني الفلتر ده مش بيستبعد حاجة فعلياً. سايبينه
        # موجود عشان لو حبيت ترجع تفعّل قائمة شرعية حقيقية
        # لاحقاً، البنية جاهزة.
        # ======================================================

        if symbol not in sharia_stocks:

            print(
                f"☪️ {symbol} "
                f"→ غير موجود في قائمة التوافق الشرعي"
            )

            continue


        # ======================================================
        # Rate Limiting
        # ======================================================

        time.sleep(
            REQUEST_DELAY_SECONDS
        )


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
        # المؤشرات تُحسب أولاً باستخدام
        # Daily Historical Data.
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
        # Candlestick Analysis (FIXED)
        #
        # مهم جداً: بيتحسب هنا، قبل ما نستبدل آخر Close
        # بالسعر الحي. لو اتحسب بعد الاستبدال، هيقارن
        # Open/High/Low التاريخية مع Close لحظي، وده بيدي
        # شموع وهمية (Hammer / Engulfing غير حقيقية).
        # ==========================================================

        candle_reasons = analyze_candlesticks(
            df
        )

        df.attrs[
            "candle_reasons"
        ] = candle_reasons


        # ======================================================
        # Get Current Yahoo Market Price
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


        # ======================================================
        # Save Historical Close
        # ======================================================

        historical_close = float(
            df["Close"].iloc[-1]
        )


        # ======================================================
        # IMPORTANT PRICE FIX
        #
        # Strategy.py expects the latest Close
        # to represent the current price.
        #
        # Therefore:
        #
        # 1. Indicators are calculated first.
        # 2. Candlestick patterns are analyzed on the
        #    REAL historical candle (see fix above).
        # 3. Historical Close is saved.
        # 4. ONLY the latest Close is replaced
        #    with Yahoo regularMarketPrice.
        #
        # We do NOT recalculate indicators.
        #
        # This means:
        #
        # Indicators = historical daily data
        #
        # Current price = latest Yahoo price
        #
        # ==========================================================

        df.loc[
            df.index[-1],
            "Close"
        ] = current_market_price


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


        regular_market_datetime = (
            df.attrs.get(
                "regular_market_datetime"
            )
        )


        if regular_market_datetime is not None:

            analysis[
                "market_datetime"
            ] = regular_market_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        else:

            analysis[
                "market_datetime"
            ] = "N/A"


        analysis[
            "historical_close"
        ] = round(
            historical_close,
            2
        )


        analysis[
            "current_market_price"
        ] = round(
            current_market_price,
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
                f"CurrentPrice={current_market_price:.2f}"
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
        f"🎯 Final Opportunities: "
        f"{len(opportunities)}"
    )

    print(
        "====================================\n"
    )


    return opportunities
