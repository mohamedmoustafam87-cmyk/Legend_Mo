import os
from datetime import datetime

from scanner import scan_market
from report import send_scanner_report, bot
from config import (
    ADMIN_CHAT_ID,
    TIMEZONE,
    REPORT_TIMES,
    REPORT_TIME_TOLERANCE_MINUTES
)
from portfolio import analyze_user_portfolio


def is_scheduled_report_time():
    now = datetime.now(TIMEZONE)
    now_minutes = (now.hour * 60) + now.minute

    for target_hour, target_minute in REPORT_TIMES:
        target_minutes = (target_hour * 60) + target_minute

        if abs(now_minutes - target_minutes) <= REPORT_TIME_TOLERANCE_MINUTES:
            return True

    return False


def is_manual_trigger():
    event_name = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    return event_name == "workflow_dispatch"


def send_portfolio_report():
    try:
        results = analyze_user_portfolio()

        if not results:
            print("⚠️ لا توجد بيانات للمحفظة.")
            return

        msg = "💼 *تقرير متابعة محفظتك الخاصة (Portfolio Advisor)*\n\n"

        total_portfolio_value = 0
        total_portfolio_pnl = 0

        for item in results:

            current_price = item.get(
                "current_price",
                item.get("price")
            )

            price_source = item.get(
                "price_source",
                "Unknown"
            )

            is_realtime = item.get(
                "is_realtime",
                False
            )

            price_status = (
                "🟢 حالي"
                if is_realtime
                else "🟡 آخر إغلاق Yahoo"
            )

            emoji_pnl = (
                "🟢"
                if item["pnl_pct"] >= 0
                else "🔴"
            )

            total_portfolio_value += item["current_value"]
            total_portfolio_pnl += item["pnl_egp"]

            msg += (
                f"📌 *السهم:* `{item['ticker']}`\n"
                f"📦 *الكمية:* `{item['shares']:,}`\n"
                f"💰 *سعر الشراء:* `{item['buy_price']:.2f}` ج.م\n"
                f"💵 *السعر الحالي:* `{current_price:.2f}` ج.م\n"
                f"📡 *المصدر:* `{price_source}` {price_status}\n"
                f"{emoji_pnl} *الربح/الخسارة:* "
                f"`{item['pnl_egp']:+,.2f}` ج.م "
                f"(`{item['pnl_pct']:+.2f}%`)\n"
                f"💡 *النصيحة:* *{item['advice']}*\n"
                f"📝 *السبب:* {item['reason']}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
            )

        total_emoji = (
            "🟢"
            if total_portfolio_pnl >= 0
            else "🔴"
        )

        msg += (
            f"📊 *إجمالي قيمة المحفظة:* "
            f"`{total_portfolio_value:,.2f}` ج.م\n"
            f"{total_emoji} *إجمالي الأرباح/الخسائر:* "
            f"`{total_portfolio_pnl:+,.2f}` ج.م\n"
        )

        bot.send_message(
            ADMIN_CHAT_ID,
            msg,
            parse_mode="Markdown"
        )

        print("✅ Portfolio report sent.")

    except Exception as e:
        print(
            f"❌ Error sending portfolio report: {e}"
        )


def main():

    print("🤖 Smart EGX Bot started...")

    # Manual GitHub Actions execution
    if is_manual_trigger():
        print("🔵 Manual trigger detected.")

    # Scheduled execution
    elif not is_scheduled_report_time():
        print(
            "⏭️ خارج مواعيد الإرسال المحددة - تخطي."
        )
        return

    try:

        print("🔎 Starting market scan...")

        opportunities = scan_market()

        if opportunities:
            print(
                f"📊 Found {len(opportunities)} opportunities."
            )

            send_scanner_report(
                opportunities
            )

        else:
            print(
                "ℹ️ لا توجد فرص مطابقة للشروط."
            )

        print("💼 Preparing portfolio report...")

        send_portfolio_report()

        print(
            "✅ تم الانتهاء من إرسال التقارير بنجاح."
        )

    except Exception as e:

        print(
            f"❌ Error while running bot: {e}"
        )


if __name__ == "__main__":
    main()
