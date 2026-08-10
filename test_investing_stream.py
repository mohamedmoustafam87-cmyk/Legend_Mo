import requests
import uuid
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


# ==========================================================
# Configuration
# ==========================================================

PAIR_ID = 0

CAIRO_TZ = ZoneInfo("Africa/Cairo")

BASE_URL = (
    "https://tvc6.investing.com/"
    f"{uuid.uuid4().hex}/0/0/0/0/quotes"
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

    "Referer":
        "https://tvc-invdn-com.investing.com/",

    "Content-Type":
        "application/json",

    "Accept":
        "application/json,text/plain,*/*",

}


# ==========================================================
# Search Investing Pair
# ==========================================================

def search_investing():

    print(
        "\n========================================"
    )

    print(
        "🔎 INVESTING INTERNAL API TEST"
    )

    print(
        "========================================"
    )

    print(
        "Searching for NIPH..."
    )


    url = (
        "https://tvc6.investing.com/"
        f"{uuid.uuid4().hex}/0/0/0/0/search"
    )


    params = {

        "query": "NIPH",

        "lang": "en",

        "domain-id": 1

    }


    try:

        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=20
        )


        print(
            f"HTTP Status: "
            f"{response.status_code}"
        )


        print(
            f"Response Size: "
            f"{len(response.text):,} bytes"
        )


        if response.status_code != 200:

            print(
                "❌ Search request rejected."
            )

            print(
                response.text[:500]
            )

            return None


        data = response.json()


        print(
            "\n📊 SEARCH RESULT:"
        )


        print(
            data
        )


        return data


    except Exception as e:

        print(
            f"❌ Search error: {e}"
        )

        return None


# ==========================================================
# Get Quotes
# ==========================================================

def get_quote(pair_id):

    print(
        "\n========================================"
    )

    print(
        "💵 REQUESTING CURRENT QUOTE"
    )

    print(
        "========================================"
    )


    url = (
        "https://tvc6.investing.com/"
        f"{uuid.uuid4().hex}/0/0/0/0/quotes"
    )


    params = {

        "symbol": pair_id

    }


    try:

        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=20
        )


        print(
            f"HTTP Status: "
            f"{response.status_code}"
        )


        print(
            f"Response Size: "
            f"{len(response.text):,} bytes"
        )


        print(
            "\nRAW RESPONSE:"
        )

        print(
            response.text[:2000]
        )


        if response.status_code != 200:

            print(
                "❌ Quote request failed."
            )

            return False


        return True


    except Exception as e:

        print(
            f"❌ Quote error: {e}"
        )

        return False


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "\n🧪 Investing.com Internal Data Test"
    )

    print(
        f"🕐 Cairo Time: "
        f"{datetime.now(CAIRO_TZ).strftime('%Y-%m-%d %H:%M:%S')}"
    )


    result = search_investing()


    if result is None:

        print(
            "\n❌ TEST FAILED"
        )

        sys.exit(1)


    print(
        "\n========================================"
    )

    print(
        "✅ SEARCH REQUEST WORKED"
    )

    print(
        "========================================"
    )


    # ------------------------------------------------------
    # Try to identify NIPH
    # ------------------------------------------------------

    pair_id = None


    if isinstance(result, list):

        for item in result:

            text = str(
                item
            ).upper()


            if (
                "NIPH" in text
                or
                "NILE PHARM" in text
            ):

                print(
                    "\n🎯 POSSIBLE NIPH MATCH:"
                )

                print(
                    item
                )


                if isinstance(
                    item,
                    dict
                ):

                    pair_id = (
                        item.get(
                            "pairId"
                        )
                        or
                        item.get(
                            "pair_id"
                        )
                    )


                break


    elif isinstance(result, dict):

        print(
            "\n⚠️ Search returned "
            "a dictionary."
        )


        # Try common structures

        candidates = []


        for key in (
            "results",
            "data",
            "symbols"
        ):

            value = result.get(
                key
            )

            if isinstance(
                value,
                list
            ):

                candidates.extend(
                    value
                )


        for item in candidates:

            text = str(
                item
            ).upper()


            if (
                "NIPH" in text
                or
                "NILE PHARM" in text
            ):

                print(
                    "\n🎯 POSSIBLE NIPH MATCH:"
                )

                print(
                    item
                )


                if isinstance(
                    item,
                    dict
                ):

                    pair_id = (
                        item.get(
                            "pairId"
                        )
                        or
                        item.get(
                            "pair_id"
                        )
                    )


                break


    # ------------------------------------------------------
    # Pair ID
    # ------------------------------------------------------

    if pair_id is None:

        print(
            "\n⚠️ لم نستطع تحديد Pair ID "
            "تلقائياً."
        )

        print(
            "\nلكن البحث نفسه نجح."
        )

        print(
            "وده معناه إن الـendpoint "
            "ممكن يكون متاح."
        )

        print(
            "\n❌ TEST INCOMPLETE"
        )

        sys.exit(1)


    print(
        "\n========================================"
    )

    print(
        f"🎯 NIPH Pair ID: {pair_id}"
    )

    print(
        "========================================"
    )


    # ------------------------------------------------------
    # Quote Test
    # ------------------------------------------------------

    success = get_quote(
        pair_id
    )


    if success:

        print(
            "\n========================================"
        )

        print(
            "✅ QUOTE REQUEST COMPLETED"
        )

        print(
            "========================================"
        )

        sys.exit(0)


    print(
        "\n❌ QUOTE TEST FAILED"
    )

    sys.exit(1)


if __name__ == "__main__":

    main()
