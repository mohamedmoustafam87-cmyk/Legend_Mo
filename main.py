from scanner import scan_market
from report import send_scanner_report


def main():

    print(
        "🤖 Smart EGX Bot started..."
    )

    try:

        opportunities = scan_market()

        print(
            f"📊 Scan completed. "
            f"Found {len(opportunities)} opportunities."
        )

        send_scanner_report(
            opportunities
        )

        print(
            "✅ Process completed successfully."
        )

    except Exception as e:

        print(
            f"❌ Error while running bot: {e}"
        )


if __name__ == "__main__":
    main()
