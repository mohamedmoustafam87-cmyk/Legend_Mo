import telebot

from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID


bot = telebot.TeleBot(TELEGRAM_TOKEN)


def send_scanner_report(opportunities):

    try:

        # ==========================================================
        # No Opportunities
        # ==========================================================

        if not opportunities:

            bot.send_message(
                ADMIN_CHAT_ID,
                (
                    "📊 *تقرير السوق المصري EGX*\n\n"
                    "⚠️ لا توجد أسهم حققت الحد الأدنى من التقييم حالياً.\n\n"
                    "🔎 السوق تحت المراقبة."
                ),
                parse_mode="Markdown"
            )

            return


        messages = []

        current_message = (
            "🏆 *تقرير التحليل الذكي للسوق المصري EGX*\n\n"
            "📈 *التركيز: اتجاه شهر وشهرين + أفضل نقطة دخول*\n\n"
        )


        # ==========================================================
        # Process Opportunities
        # ==========================================================

        for item in opportunities:

            ticker = item.get(
                "ticker",
                item.get("symbol", "N/A")
            )

            score = int(
                item.get("score", 0)
            )

            price = float(
                item.get("price", 0)
            )

            # ------------------------------------------------------
            # Trend
            # ------------------------------------------------------

            trend_status = item.get(
                "trend_status",
                "غير متوفر"
            )

            return_1m = float(
                item.get("return_1m", 0)
            )

            return_2m = float(
                item.get("return_2m", 0)
            )

            ma200_slope = float(
                item.get("ma200_slope", 0)
            )

            ema50_slope = float(
                item.get("ema50_slope", 0)
            )


            # ------------------------------------------------------
            # Entry
            # ------------------------------------------------------

            entry_status = item.get(
                "entry_status",
                "غير متوفر"
            )

            ideal_entry = float(
                item.get("ideal_entry", price)
            )

            entry_high = float(
                item.get("entry_high", price)
            )

            distance_from_ema = float(
                item.get("distance_from_ema", 0)
            )


            # ------------------------------------------------------
            # Risk Management
            # ------------------------------------------------------

            shares = int(
                item.get("shares", 0)
            )

            stop_loss = float(
                item.get("stop_loss", 0)
            )

            tp1 = float(
                item.get("tp1", 0)
            )

            tp2 = float(
                item.get("tp2", 0)
            )

            position_value = float(
                item.get("position_value", 0)
            )

            actual_risk = float(
                item.get("actual_risk", 0)
            )

            rr1 = float(
                item.get("rr1", 0)
            )

            rr2 = float(
                item.get("rr2", 0)
            )


            # ------------------------------------------------------
            # Technical Data
            # ------------------------------------------------------

            volume_ratio = float(
                item.get("volume_ratio", 0)
            )

            support = float(
                item.get("support", 0)
            )

            resistance = float(
                item.get("resistance", 0)
            )


            # ------------------------------------------------------
            # Recommendation
            # ------------------------------------------------------

            recommendation = item.get(
                "rec",
                "🟡 WATCH"
            )


            # ======================================================
            # Stock Message
            # ======================================================

            stock_message = (
                f"📌 *السهم:* `{ticker}`\n"
                f"⭐ *Score:* `{score}/100`\n"
                f"🎯 *الحالة:* {recommendation}\n\n"

                f"📈 *الاتجاه:*\n"
                f"• شهر: `{return_1m:+.1f}%`\n"
                f"• شهرين: `{return_2m:+.1f}%`\n"
                f"• الحالة: {trend_status}\n\n"

                f"💵 *السعر الحالي:* `{price:.2f}` ج.م\n"

                f"🎯 *منطقة الدخول:* "
                f"`{ideal_entry:.2f} - {entry_high:.2f}` ج.م\n"

                f"📊 *حالة الدخول:* {entry_status}\n"

                f"📏 *البعد عن EMA20:* "
                f"`{distance_from_ema:+.1f}%`\n\n"

                f"📊 *اتجاه المؤشرات:*\n"
                f"• MA200 Slope: `{ma200_slope:+.2f}%`\n"
                f"• EMA50 Slope: `{ema50_slope:+.2f}%`\n"
                f"• Volume: `{volume_ratio:.2f}x`\n\n"

                f"🛑 *Stop Loss:* `{stop_loss:.2f}` ج.م\n"

                f"📦 *الكمية المقترحة:* "
                f"`{shares:,}` سهم\n"

                f"💰 *قيمة الصفقة:* "
                f"`{position_value:,.2f}` ج.م\n"

                f"⚠️ *المخاطرة الفعلية:* "
                f"`{actual_risk:,.2f}` ج.م\n\n"

                f"🎯 *TP1:* `{tp1:.2f}` ج.م\n"
                f"📈 *R/R:* `1:{rr1:.2f}`\n\n"

                f"🎯 *TP2:* `{tp2:.2f}` ج.م\n"
                f"📈 *R/R:* `1:{rr2:.2f}`\n\n"

                f"📍 *الدعم:* `{support:.2f}`\n"
                f"🚧 *المقاومة:* `{resistance:.2f}`\n\n"

                f"💡 *أسباب التقييم:*\n"
            )


            # ======================================================
            # Reasons
            # ======================================================

            reasons = item.get(
                "reasons",
                []
            )

            if reasons:

                for reason in reasons:

                    stock_message += (
                        f"• {reason}\n"
                    )

            else:

                stock_message += (
                    "• لا توجد تفاصيل إضافية.\n"
                )


            stock_message += (
                "\n━━━━━━━━━━━━━━━━━━\n\n"
            )


            # ======================================================
            # Telegram Message Limit
            # ======================================================

            if len(
                current_message + stock_message
            ) > 3800:

                messages.append(
                    current_message
                )

                current_message = (
                    "🏆 *تكملة تقرير السوق المصري EGX*\n\n"
                    + stock_message
                )

            else:

                current_message += (
                    stock_message
                )


        # ==========================================================
        # Add Final Message
        # ==========================================================

        if current_message.strip():

            messages.append(
                current_message
            )


        # ==========================================================
        # Send Messages
        # ==========================================================

        for message in messages:

            bot.send_message(
                ADMIN_CHAT_ID,
                message,
                parse_mode="Markdown"
            )


        print(
            "✅ تم إرسال التقرير الجديد بنجاح إلى Telegram."
        )


    except Exception as e:

        print(
            f"❌ Error sending report: {e}"
            )
