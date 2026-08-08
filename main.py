from scanner import scan_market
from report import send_scanner_report


def main():

    print(
        "🤖 Smart EGX Bot started..."
    )

    try:

        # ==========================================================
        # Scan Full EGX Market
        # ==========================================================

        opportunities = scan_market()

        print(
            f"📊 Scan completed. "
            f"Found {len(opportunities)} opportunities."
        )

        # ==========================================================
        # Send Telegram Report
        # ==========================================================

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
