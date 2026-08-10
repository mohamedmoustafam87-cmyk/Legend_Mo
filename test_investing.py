import requests
import re
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


# ==========================================================
# Configuration
# ==========================================================

SYMBOL = "NIPH"

URL = (
    "https://www.investing.com/equities/"
    "nile-pharmaceu"
)

CAIRO_TZ = ZoneInfo(
    "Africa/Cairo"
)


# ==========================================================
# Headers
# ==========================================================

HEADERS = {

    "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8",

    "Accept-Language":
        "en-US,en;q=0.9",

    "Referer":
        "https://www.investing.com/"
}


# ==========================================================
# Main Test
# ==========================================================

def test_investing():

    print(
        "\n========================================"
    )

    print(
        "🔎 INVESTING.COM PRICE TEST"
    )

    print(
        "========================================"
    )

    print(
        f"📌 Symbol: {SYMBOL}"
    )

    print(
        f"🌐 URL: {URL}"
    )


    # ======================================================
    # Request
    # ======================================================

    try:

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=20
        )

        print(
            f"\n🌐 HTTP Status: "
            f"{response.status_code}"
        )

        print(
            f"📦 Response Size: "
            f"{len(response.text):,} bytes"
        )

        response.raise_for_status()


    except requests.exceptions.Timeout:

        print(
            "⏱️ ERROR: Request timeout"
        )

        return False


    except requests.exceptions.RequestException as e:

        print(
            f"❌ ERROR requesting Investing: {e}"
        )

        return False


    # ======================================================
    # Search For Price
    # ======================================================

    html = response.text

    price_candidates = []


    # ------------------------------------------------------
    # Pattern 1
    # data-test="instrument-header-details"
    # ------------------------------------------------------

    patterns = [

        r'"last"\s*:\s*"([0-9.,]+)"',

        r'"last"\s*:\s*([0-9.]+)',

        r'"last_price"\s*:\s*"([0-9.,]+)"',

        r'"last_price"\s*:\s*([0-9.]+)',

        r'"lastPrice"\s*:\s*"([0-9.,]+)"',

        r'"lastPrice"\s*:\s*([0-9.]+)',

        r'"price"\s*:\s*"([0-9.,]+)"',

        r'"price"\s*:\s*([0-9.]+)',

        r'"close"\s*:\s*"([0-9.,]+)"',

        r'"close"\s*:\s*([0-9.]+)'

    ]


    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        for match in matches:

            try:

                value = float(
                    match.replace(
                        ",",
                        ""
                    )
                )

                if value > 0:

                    price_candidates.append(
                        value
                    )

            except ValueError:

                continue


    # ======================================================
    # Remove Duplicates
    # ======================================================

    unique_prices = []

    for price in price_candidates:

        if price not in unique_prices:

            unique_prices.append(
                price
            )


    # ======================================================
    # Results
    # ======================================================

    print(
        "\n========================================"
    )

    print(
        "📊 PRICE EXTRACTION RESULTS"
    )

    print(
        "========================================"
    )


    if not unique_prices:

        print(
            "❌ لم يتم العثور على سعر مباشر "
            "داخل HTML."
        )

        print(
            "\n⚠️ ده لا يعني إن Investing "
            "مش بيجيب السعر."
        )

        print(
            "قد يكون السعر بيتحمل عن طريق "
            "JavaScript / WebSocket."
        )

        return False


    print(
        f"✅ Found {len(unique_prices)} "
        f"price candidate(s)"
    )


    for index, price in enumerate(
        unique_prices[:20],
        start=1
    ):

        print(
            f"{index}. {price:.4f}"
        )


    # ======================================================
    # Current Time
    # ======================================================

    now = datetime.now(
        CAIRO_TZ
    )


    print(
        "\n========================================"
    )

    print(
        "🕐 TEST TIME"
    )

    print(
        f"Cairo Time: "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )


    print(
        "========================================"
    )


    # ======================================================
    # Important
    # ======================================================

    print(
        "\n⚠️ IMPORTANT:"
    )

    print(
        "النتيجة دي مجرد اختبار لاستخراج السعر."
    )

    print(
        "لسه مش هنستخدم Investing داخل البوت."
    )


    return True


# ==========================================================
# Run
# ==========================================================

if __name__ == "__main__":

    success = test_investing()

    if success:

        print(
            "\n✅ TEST COMPLETED"
        )

        sys.exit(0)

    else:

        print(
            "\n❌ TEST FAILED"
        )

        sys.exit(1)
