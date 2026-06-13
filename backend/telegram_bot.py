import os
import telebot

# Token'ı environment variable'dan al (.env içinden veya Render panelinden gelecek)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# Telebot objesini oluştur (Eğer token boşsa hata vermemesi için kontrol edebiliriz ama telebot boş stringe de izin verir, sadece polling'de hata fırlatır)
bot = telebot.TeleBot(TOKEN) if TOKEN else None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 Merhaba! Trade botunuza hoş geldiniz. Sistem çalışıyor!")

def start():
    """Botu başlatan ana fonksiyon"""
    if not TOKEN:
        print("⚠️ TELEGRAM_TOKEN bulunamadı. Telegram botu başlatılmadı.")
        return
    
    print("🚀 Telegram botu mesajları dinlemeye başladı...")
    # sonsuz döngüde çalışıp mesajları dinler
    bot.infinity_polling()

if __name__ == "__main__":
    start()
