import os
import sys
import traceback
from datetime import datetime

from config import (
    ADMIN_CHAT_ID,
    TIMEZONE,
    REPORT_TIMES,
    REPORT_TIME_TOLERANCE_MINUTES,
    TRADING_WEEKDAYS,
    EGX_HOLIDAYS,
    require_telegram,
)
from scanner import scan_market
from report import send_scanner_report, send_portfolio_report, safe_send_message
from portfolio import analyze_user_portfolio


# =====================================================================
# SCHEDULE
# =====================================================================

def is_trading_day(now=None):
    """الأحد..الخميس وليس إجازة رسمية (egx_holidays.txt)."""
    now = now or datetime.now(TIMEZONE)
    return now.weekday() in TRADING_WEEKDAYS and now.strftime("%Y-%m-%d") not in EGX_HOLIDAYS


def is_manual_trigger():
    """السماح بتشغيل التقرير يدويًا من GitHub Actions."""
    return os.getenv("GITHUB_EVENT_NAME", "workflow_dispatch") == "workflow_dispatch"


# =====================================================================
# MAIN
# =====================================================================

def main():

    print("🤖 Smart EGX Bot started...")

    if is_manual_trigger():
        print("🔵 Manual trigger detected.")

    elif not is_trading_day():
        print(f"⏭️ اليوم ليس يوم تداول (جمعة/سبت/إجازة) - تخطي. الوقت الآن بتوقيت القاهرة: {datetime.now(TIMEZONE):%Y-%m-%d %H:%M %A}")
        return

    try:
        require_telegram()

        # عند التشغيل: رسالة فورية تثبت إن التوكن والـ ID شغالين قبل السكان الطويل
        if not safe_send_message(
            ADMIN_CHAT_ID,
            "🤖 *EGX Bot:* بدأ تشغيل البوت — جاري فحص الأسهم وإرسال التقرير والتوصيات.",
        ):
            print("❌ تيليجرام رفض رسالة الاختبار: راجع TELEGRAM_TOKEN و ADMIN_CHAT_ID في config.py "
                  "(Unauthorized = توكن غلط | chat not found = ID غلط أو لم تضغط Start).")
            sys.exit(1)

        print("🔎 Starting EGX market scan...")
        opportunities, ctx = scan_market(return_context=True)

        print(f"📊 تم العثور على {len(opportunities)} فرصة.")
        scanner_ok = send_scanner_report(opportunities, ctx)

        print("💼 Preparing portfolio report...")
        portfolio_ok = send_portfolio_report(analyze_user_portfolio(ctx))

        if scanner_ok and portfolio_ok:
            print("✅ تم الانتهاء من إرسال جميع التقارير والتوصيات بنجاح.")
        else:
            print("❌ فشل إرسال بعض الرسائل لتيليجرام - راجع الأسطر أعلاه (غالباً ADMIN_CHAT_ID أو TELEGRAM_TOKEN).")
            sys.exit(1)

    except Exception:  # noqa: BLE001
        print("❌ Error while running bot:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
