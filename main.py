import telebot
from config import TELEGRAM_TOKEN
from scanner import run_market_scanner

bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    msg = (
        "💎 **مرحباً بك في نظام التداول الكمي الاحترافي (Elite EGX Bot)**\n\n"
        "البوت مبرمج بأعلى معايير إدارة المخاطر، مؤشرات العزم، كشف الاختراقات، وحساب حجم المراكز.\n\n"
        "🔹 أرسل كلمة **فرص** أو **بحث** أو الأمر `/scan` لبدء فحص السوق فوراً."
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text in ['/scan', 'فرص', 'بحث'])
def trigger_scanner(message):
    bot.reply_to(message, "🔍 جاري تشغيل محرك الفحص المتقدم وتحليل الأسهم المصرية...")
    try:
        run_market_scanner()
    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ أثناء تشغيل الفحص: {str(e)}")

if __name__ == "__main__":
    print("🤖 نظام التداول الاحترافي يعمل الآن وجاهز لاستقبال الأوامر على تليجرام...")
    bot.infinity_polling()
