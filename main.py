import telebot
from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from scanner import scan_market

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_daily_report():
    try:
        opportunities = scan_market()
        
        if not opportunities:
            bot.send_message(ADMIN_CHAT_ID, "📊 *تقرير السوق المصري اليومي:*\n\nلا توجد فرص مطابقة للشروط حالياً.", parse_mode="Markdown")
            return
            
        response = "🚨 *تقرير الفرص الآلي - السوق المصري (EGX):*\n\n"
        for opp in opportunities:
            response += f"🔹 سهم: `{opp['symbol']}`\n"
            response += f"💰 السعر: `{opp['price']:.2f}`\n"
            response += f"⭐ التقييم: `{opp['score']}`\n"
            response += f"📌 الأسباب:\n"
            for reason in opp['reasons']:
                response += f"   - {reason}\n"
            response += "-------------------\n"
            
        bot.send_message(ADMIN_CHAT_ID, response, parse_mode="Markdown")
        print("Report sent successfully!")
    except Exception as e:
        print(f"Error sending report: {e}")

if __name__ == "__main__":
    send_daily_report()
