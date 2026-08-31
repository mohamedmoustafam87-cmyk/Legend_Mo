from scanner import scan_market
from report import send_scanner_report, bot
from config import ADMIN_CHAT_ID
from portfolio import analyze_user_portfolio


def send_portfolio_report():
    try:
        results = analyze_user_portfolio()
        if not results:
            return

        msg = "💼 *تقرير متابعة محفظتك الخاصة (Portfolio Advisor)*\n\n"
        
        total_portfolio_value = 0
        total_portfolio_pnl = 0

        for item in results:
            emoji_pnl = "🟢" if item["pnl_pct"] >= 0 else "🔴"
            total_portfolio_value += item["current_value"]
            total_portfolio_pnl += item["pnl_egp"]

            msg += (
                f"📌 *السهم:* `{item['ticker']}`\n"
                f"📦 *الكمية:* `{item['shares']:,}` | *التكلفة:* `{item['buy_price']:.2f}` ج.م\n"
                f"💵 *السعر الحالي:* `{item['price']:.2f}` ج.م\n"
                f"{emoji_pnl} *الربح/الخسارة:* `{item['pnl_egp']:+,.2f}` ج.م (`{item['pnl_pct']:+.2f}%`)\n"
                f"💡 *النصيحة:* *{item['advice']}*\n"
                f"📝 *السبب:* {item['reason']}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
            )

        total_emoji = "🟢" if total_portfolio_pnl >= 0 else "🔴"
        msg += (
            f"📊 *إجمالي قيمة المحفظة:* `{total_portfolio_value:,.2f}` ج.م\n"
            f"{total_emoji} *إجمالي الأرباح/الخسائر:* `{total_portfolio_pnl:+,.2f}` ج.م\n"
        )

        bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
        print("✅ تم إرسال تقرير المحفظة بنجاح.")

    except Exception as e:
        print(f"❌ Error sending portfolio report: {e}")


def main():

    print(
        "🤖 Smart EGX Bot started (Optimized & Portfolio Mode)..."
    )

    try:

        # ==========================================================
        # 1. Scan Full EGX Market & Get Top 5 Filtered Opportunities
        # ==========================================================

        opportunities = scan_market()

        print(
            f"📊 Scan completed successfully. "
            f"Found top {len(opportunities)} strong opportunities."
        )

        # ==========================================================
        # 2. Send Telegram Market Report (Top 5 Only)
        # ==========================================================

        send_scanner_report(
            opportunities
        )

        # ==========================================================
        # 3. Send User Portfolio Advisor Report
        # ==========================================================

        send_portfolio_report()

        print(
            "✅ All processes completed and reports sent successfully to Telegram."
        )

    except Exception as e:

        print(
            f"❌ Error while running bot: {e}"
        )


if __name__ == "__main__":
    main()
