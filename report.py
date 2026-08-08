import telebot
from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_scanner_report(opportunities):
    try:
        if not opportunities:
            bot.send_message(
                ADMIN_CHAT_ID, 
                "⚠️ لا توجد أسهم تطابق معايير الاختراق والزخم القوي اليوم. السوق تحت المراقبة.",
                parse_mode='Markdown'
            )
            return

        response = "🏆 **التقارير الاحترافية المعتمدة (فرص عالية الاحتمالية):**\n\n"
        for item in opportunities:
            response += (
                f"📌 **سهم: {item['ticker']}** | التقييم الكلي: **{item['score']}/100** 🌟\n"
                f"📊 **نسبة النجاح المتوقعة:** ~{item['prob']}%\n"
                f"💵 **سعر الدخول (Entry):** {item['price']} ج.م\n"
                f"📦 **الكمية المقترحة للشراء:** {item['shares']} سهم\n"
                f"🛑 **وقف الخسارة (Stop Loss):** {item['stop_loss']} ج.م\n"
                f"🎯 **الهدف الأول (TP1):** {item['tp1']} ج.م\n"
                f"🎯 **الهدف الثاني (TP2):** {item['tp2']} ج.م\n"
                f"💡 **تفاصيل الفحص الفني:**\n"
            )
            for r in item['reasons']:
                response += f"   - {r}\n"
            response += f"-----------------------------------\n"
        
        bot.send_message(ADMIN_CHAT_ID, response, parse_mode='Markdown')
        print("✅ تم إرسال التقرير بنجاح إلى تليجرام!")

    except Exception as e:
        print(f"Error sending report: {e}")
