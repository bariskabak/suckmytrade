import os
import telebot
import urllib.request
import json
import time as time_module

# Token'ı environment variable'dan al (.env içinden veya Render/Railway panelinden gelecek)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
PORT = os.environ.get("PORT", 8000)
API_BASE = f"http://127.0.0.1:{PORT}/api"

# Kayıtlı kullanıcılar dosyası
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "registered_users.json")

# Telebot objesini oluştur
# NOT: Bot objesi her zaman oluşturulmalı ki dekoratörler (@bot.message_handler) hata vermesin.
# Token boşsa polling'de hata verir ama start() fonksiyonu zaten kontrol ediyor.
bot = telebot.TeleBot(TOKEN if TOKEN else "123456789:placeholder_token_will_not_poll")

def fetch_api(endpoint):
    try:
        req = urllib.request.Request(f"{API_BASE}/{endpoint}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"API Hatası ({endpoint}): {e}")
        return None

# ═══════════════════════════════════════════════
# KULLANICI KAYIT SİSTEMİ
# ═══════════════════════════════════════════════

def load_registered_users():
    """Kayıtlı kullanıcı chat_id'lerini dosyadan yükler"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Kullanıcı dosyası okuma hatası: {e}")
    return []

def save_registered_users(users):
    """Kayıtlı kullanıcı chat_id'lerini dosyaya yazar"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
    except Exception as e:
        print(f"Kullanıcı dosyası yazma hatası: {e}")

def send_notification(text):
    """Tüm kayıtlı kullanıcılara bildirim gönderir"""
    if not bot or not TOKEN:
        return
    users = load_registered_users()
    for chat_id in users:
        try:
            bot.send_message(chat_id, text)
        except Exception as e:
            print(f"Bildirim gönderme hatası (chat_id: {chat_id}): {e}")

# ═══════════════════════════════════════════════
# KOMUTLAR
# ═══════════════════════════════════════════════

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "👋 *Trade Asistanına Hoş Geldiniz!*\n\n"
        "Sistem arka planda BIST hisselerini analiz etmeye devam ediyor. "
        "Aşağıdaki komutları kullanarak anlık verilere ulaşabilirsiniz:\n\n"
        "📊 /rapor - Güncel piyasa özeti ve sabah raporu\n"
        "🎯 /sinyaller - Güçlü AL/SAT sinyali veren hisseler\n"
        "🌍 /makro - Makro ekonomik durum ve küresel endeksler\n"
        "🔍 /hisse [KOD] - Seçtiğiniz hissenin detaylı analizi (Örn: /hisse THYAO)\n"
        "⚙️ /durum - Sistem sağlık durumu\n"
        "🔔 /kayit - Otomatik sinyal bildirimi için kaydol\n"
        "🔕 /kayitiptal - Bildirim kaydını iptal et"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['kayit'])
def register_user(message):
    chat_id = message.chat.id
    users = load_registered_users()
    if chat_id not in users:
        users.append(chat_id)
        save_registered_users(users)
        bot.reply_to(message, "✅ Bildirim kaydınız oluşturuldu! Artık güçlü sinyaller otomatik olarak size gönderilecek.")
    else:
        bot.reply_to(message, "ℹ️ Zaten kayıtlısınız. Güçlü sinyaller otomatik olarak size gönderilmeye devam edecek.")

@bot.message_handler(commands=['kayitiptal'])
def unregister_user(message):
    chat_id = message.chat.id
    users = load_registered_users()
    if chat_id in users:
        users.remove(chat_id)
        save_registered_users(users)
        bot.reply_to(message, "🔕 Bildirim kaydınız iptal edildi. Artık otomatik sinyal bildirimi almayacaksınız.")
    else:
        bot.reply_to(message, "ℹ️ Zaten kayıtlı değilsiniz.")

@bot.message_handler(commands=['durum'])
def send_status(message):
    data = fetch_api("health")
    if not data:
        bot.reply_to(message, "❌ Sistem durumuna ulaşılamadı. Sunucu arka planda hala başlıyor olabilir.")
        return
        
    text = (
        f"⚙️ *Sistem Durumu:*\n"
        f"Durum: `{data.get('status', 'Bilinmiyor')}`\n"
        f"BIST Bağlantısı: `{data.get('bist_status', 'Bilinmiyor')}`\n"
        f"Seans Durumu: `{data.get('session_status', 'Bilinmiyor')}`\n"
        f"Takip Edilen Hisse Sayısı: `{data.get('active_pairs', 0)}`\n"
        f"Küresel Duyarlılık Skoru (GSS): `{data.get('gss', 0.0)}`"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['sinyaller'])
def send_signals(message):
    data = fetch_api("results")
    if not data:
        bot.reply_to(message, "❌ Sinyallere ulaşılamadı. Analiz döngüsü tamamlanmamış olabilir.")
        return
        
    al_list = []
    sat_list = []
    
    for sym, res in data.items():
        sig = res.get("signal", "NOTR")
        score = res.get("score", 0.0)
        price = res.get("price", 0.0)
        confidence = res.get("confidence", 0)
        
        name = sym.split('.')[0]
        conf_str = f" | Güven: %{int(confidence)}" if confidence > 0 else ""
        item = f"• {name} - Fiyat: {price} (Skor: {score}{conf_str})"
        if "AL" in sig:
            al_list.append(item)
        elif "SAT" in sig:
            sat_list.append(item)
            
    text = "🎯 GÜNCEL SİNYALLER\n\n"
    if al_list:
        text += "🟩 AL Sinyalleri:\n" + "\n".join(al_list) + "\n\n"
    if sat_list:
        text += "🟥 SAT Sinyalleri:\n" + "\n".join(sat_list) + "\n\n"
        
    if not al_list and not sat_list:
        text += "Şu an için güçlü bir AL veya SAT sinyali bulunmuyor. Piyasa yatay veya hisseler orta bantta (Nötr)."
        
    bot.reply_to(message, text)

@bot.message_handler(commands=['rapor'])
def send_report(message):
    bot.reply_to(message, "⏳ Rapor hazırlanıyor, bu birkaç saniye sürebilir...")
    data = fetch_api("morning-report")
    if not data:
        bot.reply_to(message, "❌ Rapora ulaşılamadı.")
        return
        
    outlook = data.get("outlook", {})
    title = outlook.get("title", "Rapor")
    desc = outlook.get("description", "")
    gss = outlook.get("gss", 0.0)
    
    text = f"📰 PİYASA RAPORU (GSS: {gss})\n\n"
    text += f"➤ {title}\n{desc}\n\n"
    
    recs = data.get("recommended_stocks", [])
    if recs:
        text += "⭐ ÖNE ÇIKAN HİSSELER:\n"
        for r in recs:
            text += f"• {r.get('name', '')}: {r.get('strategy', '')} (Hedef: {r.get('tp', '')})\n"
            
    bot.reply_to(message, text)

@bot.message_handler(commands=['makro'])
def send_macro(message):
    bot.reply_to(message, "⏳ Makro veriler getiriliyor...")
    data = fetch_api("morning-report")
    if not data:
        bot.reply_to(message, "❌ Makro verilere ulaşılamadı.")
        return
        
    text = "🌍 MAKRO EKONOMİK DURUM & PİYASA\n\n"
    
    globals_data = data.get("global_markets", {})
    if globals_data:
        text += "🌐 Küresel Endeksler:\n"
        for name, info in globals_data.items():
            pct = info.get('percentage', 0.0)
            sign = "+" if pct > 0 else ""
            text += f"• {name}: {info.get('last')} (%{sign}{pct})\n"
        text += "\n"
            
    sectors = data.get("sector_analysis", [])
    if sectors:
        text += "📊 Sektörel Isı Haritası:\n"
        for s in sectors:
            text += f"• {s.get('name')}: {s.get('trend')} (Skor: {s.get('score')})\n"
        text += "\n"
            
    cal = data.get("economic_calendar", [])
    if cal:
        text += "🗓 Bugünün Ekonomik Takvimi:\n"
        for c in cal:
            text += f"• {c.get('time')} [{c.get('country')}] - {c.get('event')}\n"
            
    news = data.get("news", [])
    if news:
        text += "\n📰 Son Haberler:\n"
        for n in news[:3]:
            text += f"• {n.get('time')} - {n.get('title')} ({n.get('source')})\n"

    bot.reply_to(message, text)

@bot.message_handler(commands=['hisse'])
def send_stock_info(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Lütfen bir hisse kodu girin. Örnek: /hisse THYAO")
        return
        
    symbol = parts[1].upper()
    if not symbol.endswith(".IS"):
        symbol += ".IS"
        
    bot.reply_to(message, f"⏳ {symbol} için analiz getiriliyor...")
    data = fetch_api(f"morning-report?symbol={symbol}")
    if not data or "outlook" not in data:
        bot.reply_to(message, "❌ Hisse bulunamadı veya analiz henüz tamamlanmadı.")
        return
        
    outlook = data.get("outlook", {})
    range_est = data.get("range_estimate", {})
    
    text = f"🎯 {symbol} - DETAYLI ANALİZ\n\n"
    text += f"➤ {outlook.get('title', '')}\n"
    text += f"{outlook.get('description', '')}\n\n"
    
    text += f"📈 Destek / Direnç:\n"
    text += f"Destek: {range_est.get('support', '')}\n"
    text += f"Direnç: {range_est.get('resistance', '')}\n"
    text += f"Trend Beklentisi: {range_est.get('trend', '')}\n"
    
    bot.reply_to(message, text)

def start():
    """Botu başlatan ana fonksiyon"""
    if not TOKEN:
        print("⚠️ TELEGRAM_TOKEN bulunamadı. Telegram botu başlatılmadı.")
        return
    
    print("🚀 Telegram botu mesajları dinlemeye başladı...")
    bot.infinity_polling()

if __name__ == "__main__":
    start()
