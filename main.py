import os
from datetime import datetime

from config import (
    TIMEZONE,
    REPORT_TIMES,
    REPORT_TIME_TOLERANCE_MINUTES,
    TRADING_WEEKDAYS,
    EGX_HOLIDAYS,
    require_telegram,
)
from scanner import scan_market
from report import send_scanner_report, send_portfolio_report
from portfolio import analyze_user_portfolio


# =====================================================================
# SCHEDULE
# =====================================================================

def is_trading_day(now=None):
    """الأحد..الخميس وليس إجازة رسمية (egx_holidays.txt)."""
    now = now or datetime.now(TIMEZONE)
    return now.weekday() in TRADING_WEEKDAYS and now.strftime("%Y-%m-%d") not in EGX_HOLIDAYS


def is_scheduled_report_time(now=None):
    """التحقق من أن الوقت الحالي داخل نافذة أحد مواعيد التقارير."""
    now = now or datetime.now(TIMEZONE)
    now_minutes = now.hour * 60 + now.minute

    return any(
        abs(now_minutes - (h * 60 + m)) <= REPORT_TIME_TOLERANCE_MINUTES
        for h, m in REPORT_TIMES
    )


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
        print("⏭️ اليوم ليس يوم تداول (جمعة/سبت/إجازة) - تخطي.")
        return

    elif not is_scheduled_report_time():
        print("⏭️ خارج مواعيد الإرسال المحددة - تخطي.")
        return

    try:
        require_telegram()

        print("🔎 Starting EGX market scan...")
        opportunities, ctx = scan_market(return_context=True)

        print(f"📊 تم العثور على {len(opportunities)} فرصة.")
        send_scanner_report(opportunities, ctx)

        print("💼 Preparing portfolio report...")
        send_portfolio_report(analyze_user_portfolio(ctx))

        print("✅ تم الانتهاء من إرسال جميع التقارير بنجاح.")

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error while running bot: {e}")


if __name__ == "__main__":
    main()
