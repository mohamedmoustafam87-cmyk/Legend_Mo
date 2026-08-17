from scanner import scan_market
from report import send_scanner_report


def main():

    print(
        "🤖 Smart EGX Bot started (Optimized & Filtered Mode)..."
    )

    try:

        # ==========================================================
        # Scan Full EGX Market & Get Top 5 Filtered Opportunities
        # ==========================================================

        opportunities = scan_market()

        print(
            f"📊 Scan completed successfully. "
            f"Found top {len(opportunities)} strong opportunities."
        )

        # ==========================================================
        # Send Telegram Report (Top 5 Only)
        # ==========================================================

        send_scanner_report(
            opportunities
        )

        print(
            "✅ Process completed and report sent successfully to Telegram."
        )

    except Exception as e:

        print(
            f"❌ Error while running bot: {e}"
        )


if __name__ == "__main__":
    main()
