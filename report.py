import telebot

from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID


bot = telebot.TeleBot(TELEGRAM_TOKEN)


def send_scanner_report(opportunities):

    try:

        if not opportunities:

            bot.send_message(
                ADMIN_CHAT_ID,
                (
                    "⚠️ *لا توجد فرص تداول مطابقة للشروط حالياً.*\n\n"
                    "📊 السوق تحت المراقبة."
                ),
                parse_mode="Markdown"
            )

            return

        messages = []

        current_message = (
            "🏆 *أفضل فرص التداول في السوق المصري EGX*\n\n"
        )

        for item in opportunities:

            ticker = item.get(
                "ticker",
                item.get("symbol", "N/A")
            )

            score = item.get("score", 0)

            price = float(
                item.get("price", 0)
            )

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

            reasons = item.get(
                "reasons",
                []
            )

            risk = price - stop_loss
            reward_1 = tp1 - price
            reward_2 = tp2 - price

            if risk > 0:
                rr1 = reward_1 / risk
                rr2 = reward_2 / risk
            else:
                rr1 = 0
                rr2 = 0

            position_value = price * shares

            if score >= 90:
                recommendation = "🔥 شراء قوي جداً"
            elif score >= 85:
                recommendation = "🟢 فرصة شراء قوية"
            elif score >= 75:
                recommendation = "🟡 فرصة شراء جيدة"
            else:
                recommendation = "👀 مراقبة"

            stock_message = (
                f"📌 *السهم:* `{ticker}`\n"
                f"⭐ *Score:* `{score}/100`\n"
                f"🎯 *التوصية:* {recommendation}\n\n"
                f"💵 *سعر الدخول:* `{price:.2f}` ج.م\n"
                f"📦 *الكمية المقترحة:* `{shares:,}` سهم\n"
                f"💰 *قيمة الصفقة:* `{position_value:,.2f}` ج.م\n\n"
                f"🛑 *Stop Loss:* `{stop_loss:.2f}` ج.م\n"
                f"⚠️ *المخاطرة للسهم:* `{risk:.2f}` ج.م\n\n"
                f"🎯 *TP1:* `{tp1:.2f}` ج.م\n"
                f"📈 *Risk/Reward:* `1:{rr1:.2f}`\n\n"
                f"🎯 *TP2:* `{tp2:.2f}` ج.م\n"
                f"📈 *Risk/Reward:* `1:{rr2:.2f}`\n\n"
                f"💡 *أسباب الاختيار:*\n"
            )

            if reasons:
                for reason in reasons:
                    stock_message += f"• {reason}\n"
            else:
                stock_message += "• لا توجد تفاصيل إضافية.\n"

            stock_message += (
                "\n━━━━━━━━━━━━━━━━━━\n\n"
            )

            if len(
                current_message + stock_message
            ) > 3800:

                messages.append(
                    current_message
                )

                current_message = stock_message

            else:
                current_message += stock_message

        if current_message.strip():
            messages.append(
                current_message
            )

        for message in messages:
            bot.send_message(
                ADMIN_CHAT_ID,
                message,
                parse_mode="Markdown"
            )

        print(
            "✅ تم إرسال تقرير الفرص بنجاح إلى Telegram."
        )

    except Exception as e:
        print(
            f"❌ Error sending report: {e}"
        )
