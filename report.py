import telebot

from config import (
    TELEGRAM_TOKEN,
    ADMIN_CHAT_ID
)


bot = telebot.TeleBot(
    TELEGRAM_TOKEN
)


def safe_send_message(chat_id, text):
    try:
        bot.send_message(chat_id, text, parse_mode="Markdown")
        return True
    except Exception:
        try:
            plain_text = (
                text
                .replace("*", "")
                .replace("`", "")
                .replace("_", "")
            )
            bot.send_message(chat_id, plain_text)
            return True
        except Exception:
            return False


def send_scanner_report(opportunities):
    try:
        if not opportunities:
            safe_send_message(
                ADMIN_CHAT_ID,
                (
                    "📊 *تقرير السوق المصري EGX*\n\n"
                    "⚠️ لا توجد أسهم حققت الحد الأدنى "
                    "من شروط الاستراتيجية حالياً.\n\n"
                    "🔎 السوق تحت المراقبة."
                )
            )
            return

        opportunities = sorted(opportunities, key=lambda x: x.get("score", 0), reverse=True)[:5]
        messages = []

        current_message = (
            "🏆 *تقرير التحليل الذكي للسوق المصري EGX (أقوى 5 فرص)*\n\n"
            "📈 *الاستراتيجية: التوقعات المستقبلية (شهر + شهرين)*\n"
            "🎯 *الهدف: اختيار السهم + توقيت الدخول + إدارة الخروج*\n\n"
        )

        for item in opportunities:
            try:
                ticker = item.get("ticker", "N/A")
                score = int(item.get("score", 0))
                price = float(item.get("price", 0))
                data_source = item.get("data_source", "غير محدد")

                trend_status = item.get("trend_status", "غير متوفر")
                forecast_1m_score = int(item.get("forecast_1m_score", 0))
                forecast_2m_score = int(item.get("forecast_2m_score", 0))
                forecast_1m_status = item.get("forecast_1m_status", "غير متوفر")
                forecast_2m_status = item.get("forecast_2m_status", "غير متوفر")

                ma200_slope = float(item.get("ma200_slope", 0))
                ema50_slope = float(item.get("ema50_slope", 0))

                entry_status = item.get("entry_status", "غير متوفر")
                ideal_entry = float(item.get("ideal_entry", price))
                entry_high = float(item.get("entry_high", price))
                distance_from_ema = float(item.get("distance_from_ema", 0))

                shares = int(item.get("shares", 0))
                stop_loss = float(item.get("stop_loss", 0))
                stop_loss_pct = float(item.get("stop_loss_pct", 0))
                tp1 = float(item.get("tp1", 0))
                days_tp1_text = item.get("days_tp1_text", "غير متوفر")
                tp2 = float(item.get("tp2", 0))
                days_tp2_text = item.get("days_tp2_text", "غير متوفر")
                position_value = float(item.get("position_value", 0))
                actual_risk = float(item.get("actual_risk", 0))
                risk_per_share = float(item.get("risk_per_share", 0))
                rr1 = float(item.get("rr1", 0))
                rr2 = float(item.get("rr2", 0))

                volume_ratio = float(item.get("volume_ratio", 0))
                support = float(item.get("support", 0))
                resistance = float(item.get("resistance", 0))
                atr = float(item.get("atr", 0))
                exit_strategy = item.get("exit_strategy", "🟢 الوضع آمن")

                recommendation = item.get("rec", "🟡 WATCH")

                if entry_status.startswith("🟢"):
                    entry_message = "🟢 *الدخول مناسب حالياً*"
                elif entry_status.startswith("🟡"):
                    entry_message = "🟡 *انتظر نقطة دخول أفضل*"
                else:
                    entry_message = "🔴 *لا يوجد دخول حالياً*"

                if score >= 90:
                    score_message = "🔥 تقييم استثنائي"
                elif score >= 80:
                    score_message = "🟢 تقييم قوي جداً"
                elif score >= 65:
                    score_message = "🟡 تقييم جيد ومناسب"
                else:
                    score_message = "⚪ تقييم متحفظ"

                stock_message = (
                    f"📌 *السهم:* `{ticker}`\n"
                    f"⭐ *Score:* `{score}/100`\n"
                    f"📊 *تقييم النظام:* {score_message}\n"
                    f"🎯 *التوصية:* {recommendation}\n\n"

                    f"📈 *التوقعات المستقبلية:*\n"
                    f"• الشهر القادم: `{forecast_1m_score}/100` ({forecast_1m_status})\n"
                    f"• الشهرين القادمين: `{forecast_2m_score}/100` ({forecast_2m_status})\n"
                    f"• الحالة العامة: {trend_status}\n\n"

                    f"💵 *السعر الحالي:* `{price:.2f}` ج.م\n"
                    f"🔄 *مصدر السعر:* {data_source}\n\n"

                    f"🎯 *منطقة الدخول المقترحة:*\n"
                    f"`{ideal_entry:.2f} - {entry_high:.2f}` ج.م\n"
                    f"📊 {entry_message}\n"
                    f"📏 *البعد عن EMA20:* `{distance_from_ema:+.1f}%`\n\n"

                    f"📊 *المؤشرات الرئيسية:*\n"
                    f"• MA200 Slope: `{ma200_slope:+.2f}%`\n"
                    f"• EMA50 Slope: `{ema50_slope:+.2f}%`\n"
                    f"• Volume: `{volume_ratio:.2f}x` | ATR: `{atr:.2f}`\n\n"

                    f"🛑 *Stop Loss:* `{stop_loss:.2f}` ج.م (`{stop_loss_pct:.2f}%`)\n"
                    f"⚠️ *المخاطرة للسهم:* `{risk_per_share:.2f}` ج.م\n\n"

                    f"📦 *الكمية المقترحة:* `{shares:,}` سهم\n"
                    f"💰 *قيمة الصفقة:* `{position_value:,.2f}` ج.م\n"
                    f"⚠️ *المخاطرة الفعلية:* `{actual_risk:,.2f}` ج.م\n\n"

                    f"🎯 *الهدف الأول TP1:* `{tp1:.2f}` ج.م (Risk/Reward: `1:{rr1:.2f}`)\n"
                    f"🎯 *الهدف الثاني TP2:* `{tp2:.2f}` ج.م (Risk/Reward: `1:{rr2:.2f}`)\n\n"

                    f"📍 *الدعم:* `{support:.2f}` ج.م | 🚧 *المقاومة:* `{resistance:.2f}` ج.م\n"
                    f"🚪 *خطة وإشارات الخروج:* \n{exit_strategy}\n\n"

                    f"💡 *أسباب التقييم:*\n"
                )

                reasons = item.get("reasons", [])
                if reasons:
                    for reason in reasons:
                        stock_message += f"• {reason}\n"
                else:
                    stock_message += "• لا توجد تفاصيل إضافية.\n"

                stock_message += "\n━━━━━━━━━━━━━━━━━━\n\n"

                if len(current_message + stock_message) > 3800:
                    messages.append(current_message)
                    current_message = "🏆 *تكملة تقرير السوق المصري EGX*\n\n" + stock_message
                else:
                    current_message += stock_message

            except Exception:
                continue

        if current_message.strip():
            messages.append(current_message)

        for message in messages:
            safe_send_message(ADMIN_CHAT_ID, message)

    except Exception as e:
        print(f"❌ Error sending report: {e}")
