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


# ==========================================================
# Check If Now Is a Scheduled Report Time (Cairo Local Time)
# ==========================================================

def is_scheduled_report_time():
    """
    بيتحقق إن التوقيت الحالي بتوقيت القاهرة قريب من أحد
    المواعيد المحددة في REPORT_TIMES، بهامش REPORT_TIME_TOLERANCE_MINUTES.
    بيتعامل تلقائيًا مع التوقيت الصيفي لأن TIMEZONE = Africa/Cairo.
    """

    now = datetime.now(TIMEZONE)
    now_minutes = (now.hour * 60) + now.minute

    for target_hour, target_minute in REPORT_TIMES:
        target_minutes = (target_hour * 60) + target_minute

        if abs(now_minutes - target_minutes) <= REPORT_TIME_TOLERANCE_MINUTES:
            print(
                f"⏰ الوقت الحالي ({now.strftime('%H:%M')}) "
                f"يطابق الموعد المحدد ({target_hour:02d}:{target_minute:02d}) - جاري التنفيذ"
            )
            return True

    return False


# ==========================================================
# Check If This Run Was Triggered Manually
# ==========================================================

def is_manual_trigger():
    """
    GitHub Actions بيحط اسم الحدث في GITHUB_EVENT_NAME.
    لو التشغيل يدوي (زرار Run workflow) قيمتها 'workflow_dispatch'.
    لو مش موجودة (تشغيل محلي على جهازك مثلاً) بنعتبره يدوي برضه.
    """

    event_name = os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    return event_name == "workflow_dispatch"


def send_portfolio_report():
    try:
        results = analyze_user_portfolio()
        if not results:
            print("⚠️ لا توجد بيانات لتقرير المحفظة.")
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

    # ==========================================================
    # 0. Skip Only If Automatic (Scheduled) Run AND Not a
    #    Scheduled Report Time. Manual runs always execute.
    # ==========================================================

    if not is_manual_trigger() and not is_scheduled_report_time():
        print(
            "⏭️ تشغيل تلقائي خارج مواعيد الإرسال المحددة - تخطي الـ scan والإرسال."
        )
        return

    if is_manual_trigger():
        print(
            "▶️ تشغيل يدوي (workflow_dispatch) - جاري التنفيذ بغض النظر عن التوقيت."
        )

    try:

        # ==========================================================
        # 1. Scan Full EGX Market & Get Top 5 Filtered Opportunities
        # ==========================================================

        print("🔍 جاري بدء مسح السوق والفحص الفني للأسهم...")
        opportunities = scan_market()

        print(
            f"📊 Scan completed successfully. "
            f"Found top {len(opportunities)} strong opportunities."
        )

        # ==========================================================
        # 2. Send Telegram Market Report (Top 5 Only)
        # ==========================================================

        if opportunities and len(opportunities) > 0:
            print("📤 جاري إرسال تقرير السوق إلى تيليجرام...")
            send_scanner_report(opportunities)
            print("✅ تم إرسال تقرير السوق بنجاح.")
        else:
            print("⚠️ لم يتم العثور على فرص مطابقة للشروط الفنية اليوم، لذلك لن يتم إرسال رسالة السوق.")

        # ==========================================================
        # 3. Send User Portfolio Advisor Report
        # ==========================================================

        print("💼 جاري فحص المحفظة وإرسال تقريرها...")
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
