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


# =====================================================================
# SCHEDULE
# =====================================================================

def is_scheduled_report_time():
    """
    التحقق من أن الوقت الحالي داخل نافذة أحد مواعيد التقارير.
    """

    now = datetime.now(TIMEZONE)

    now_minutes = (
        now.hour * 60
        + now.minute
    )

    for target_hour, target_minute in REPORT_TIMES:

        target_minutes = (
            target_hour * 60
            + target_minute
        )

        if (
            abs(now_minutes - target_minutes)
            <= REPORT_TIME_TOLERANCE_MINUTES
        ):
            return True

    return False


# =====================================================================
# TRIGGER
# =====================================================================

def is_manual_trigger():
    """
    السماح بتشغيل التقرير يدويًا من GitHub Actions.
    """

    event_name = os.getenv(
        "GITHUB_EVENT_NAME",
        "workflow_dispatch"
    )

    return event_name == "workflow_dispatch"


# =====================================================================
# PORTFOLIO REPORT
# =====================================================================

def send_portfolio_report():

    try:

        results = analyze_user_portfolio()

        if not results:

            print(
                "⚠️ لا توجد بيانات متاحة للمحفظة."
            )

            return

        msg = (
            "💼 *تقرير متابعة محفظتك الخاصة*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
        )

        total_portfolio_value = 0.0
        total_portfolio_pnl = 0.0

        for item in results:

            ticker = item.get(
                "ticker",
                "N/A"
            )

            shares = item.get(
                "shares",
                0
            )

            buy_price = item.get(
                "buy_price",
                0
            )

            # ---------------------------------------------------------
            # CURRENT PRICE
            # ---------------------------------------------------------

            current_price = item.get(
                "current_price",
                item.get(
                    "price",
                    0
                )
            )

            current_price = float(
                current_price or 0
            )

            # ---------------------------------------------------------
            # P/L
            # ---------------------------------------------------------

            pnl_egp = float(
                item.get(
                    "pnl_egp",
                    0
                ) or 0
            )

            pnl_pct = float(
                item.get(
                    "pnl_pct",
                    0
                ) or 0
            )

            current_value = float(
                item.get(
                    "current_value",
                    0
                ) or 0
            )

            total_portfolio_value += (
                current_value
            )

            total_portfolio_pnl += (
                pnl_egp
            )

            # ---------------------------------------------------------
            # PRICE SOURCE
            # ---------------------------------------------------------

            price_source = item.get(
                "price_source",
                item.get(
                    "data_source",
                    "غير محدد"
                )
            )

            is_realtime = item.get(
                "is_realtime",
                False
            )

            if is_realtime:

                price_status = (
                    "🟢 السعر الحالي من Mubasher"
                )

            else:

                price_status = (
                    "🟡 آخر إغلاق Yahoo"
                )

            # ---------------------------------------------------------
            # P/L EMOJI
            # ---------------------------------------------------------

            emoji_pnl = (
                "🟢"
                if pnl_pct >= 0
                else "🔴"
            )

            # ---------------------------------------------------------
            # STRATEGY
            # ---------------------------------------------------------

            advice = item.get(
                "advice",
                item.get(
                    "rec",
                    "غير متوفر"
                )
            )

            reason = item.get(
                "reason",
                ""
            )

            # ---------------------------------------------------------
            # TECHNICAL DATA
            # ---------------------------------------------------------

            score = item.get(
                "score"
            )

            support = item.get(
                "support"
            )

            resistance = item.get(
                "resistance"
            )

            stop_loss = item.get(
                "stop_loss"
            )

            tp1 = item.get(
                "tp1"
            )

            tp2 = item.get(
                "tp2"
            )

            # ---------------------------------------------------------
            # STOCK MESSAGE
            # ---------------------------------------------------------

            msg += (
                f"📌 *السهم:* `{ticker}`\n"

                f"📦 *الكمية:* "
                f"`{int(shares):,}` سهم\n"

                f"💰 *سعر الشراء:* "
                f"`{float(buy_price):.2f}` ج.م\n"

                f"💵 *السعر الحالي:* "
                f"`{current_price:.2f}` ج.م\n"

                f"📡 *مصدر السعر:* "
                f"`{price_source}`\n"

                f"{price_status}\n"

                f"{emoji_pnl} *الربح/الخسارة:* "
                f"`{pnl_egp:+,.2f}` ج.م "
                f"(`{pnl_pct:+.2f}%`)\n\n"

                f"⭐ *Score:* "
                f"`{score if score is not None else '—'}/100`\n"

                f"💡 *النصيحة:* "
                f"*{advice}*\n"

                f"📝 *السبب:* "
                f"{reason}\n\n"

                f"📍 *الدعم:* "
                f"`{support if support is not None else '—'}`\n"

                f"🚧 *المقاومة:* "
                f"`{resistance if resistance is not None else '—'}`\n"

                f"🛑 *وقف الخسارة:* "
                f"`{stop_loss if stop_loss is not None else '—'}`\n"

                f"🎯 *TP1:* "
                f"`{tp1 if tp1 is not None else '—'}`\n"

                f"🎯 *TP2:* "
                f"`{tp2 if tp2 is not None else '—'}`\n"

                f"━━━━━━━━━━━━━━━━━━\n\n"
            )

        # =============================================================
        # TOTAL PORTFOLIO
        # =============================================================

        total_emoji = (
            "🟢"
            if total_portfolio_pnl >= 0
            else "🔴"
        )

        msg += (
            "📊 *ملخص المحفظة*\n"
            "━━━━━━━━━━━━━━━━━━\n"

            f"💰 *إجمالي قيمة المحفظة:* "
            f"`{total_portfolio_value:,.2f}` ج.م\n"

            f"{total_emoji} *إجمالي الأرباح/الخسائر:* "
            f"`{total_portfolio_pnl:+,.2f}` ج.م\n"
        )

        # =============================================================
        # SEND
        # =============================================================

        bot.send_message(
            ADMIN_CHAT_ID,
            msg,
            parse_mode="Markdown"
        )

        print(
            "✅ Portfolio report sent successfully."
        )

    except Exception as e:

        print(
            f"❌ Error sending portfolio report: {e}"
        )


# =====================================================================
# MAIN
# =====================================================================

def main():

    print(
        "🤖 Smart EGX Bot started..."
    )

    # -------------------------------------------------------------
    # MANUAL TRIGGER
    # -------------------------------------------------------------

    if is_manual_trigger():

        print(
            "🔵 Manual GitHub Actions trigger detected."
        )

    # -------------------------------------------------------------
    # SCHEDULED TRIGGER
    # -------------------------------------------------------------

    elif not is_scheduled_report_time():

        print(
            "⏭️ خارج مواعيد الإرسال المحددة - تخطي."
        )

        return

    # -------------------------------------------------------------
    # MARKET SCAN
    # -------------------------------------------------------------

    try:

        print(
            "🔎 Starting EGX market scan..."
        )

        opportunities = scan_market()

        if opportunities:

            print(
                f"📊 تم العثور على "
                f"{len(opportunities)} فرصة."
            )

            send_scanner_report(
                opportunities
            )

        else:

            print(
                "ℹ️ لا توجد فرص مطابقة لشروط الاستراتيجية."
            )

        # ---------------------------------------------------------
        # PORTFOLIO
        # ---------------------------------------------------------

        print(
            "💼 Preparing portfolio report..."
        )

        send_portfolio_report()

        print(
            "✅ تم الانتهاء من إرسال جميع التقارير بنجاح."
        )

    except Exception as e:

        print(
            f"❌ Error while running bot: {e}"
        )


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    main()
