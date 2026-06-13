import os
import telebot
import urllib.request
import json

# Token'ı environment variable'dan al (.env içinden veya Render/Railway panelinden gelecek)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
PORT = os.environ.get("PORT", 8000)
API_BASE = f"http://127.0.0.1:{PORT}/api"

# Telebot objesini oluştur
bot = telebot.TeleBot(TOKEN) if TOKEN else None

def fetch_api(endpoint):
    try:
        req = urllib.request.Request(f"{API_BASE}/{endpoint}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"API Hatası ({endpoint}): {e}")
        return None

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
        "⚙️ /durum - Sistem sağlık durumu"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

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
        
        item = f"• *{sym.split('.')[0]}* - Fiyat: {price} (Skor: {score})"
        if "AL" in sig:
            al_list.append(item)
        elif "SAT" in sig:
            sat_list.append(item)
            
    text = "🎯 *GÜNCEL SİNYALLER*\n\n"
    if al_list:
        text += "🟩 *AL Sinyalleri:*\n" + "\n".join(al_list) + "\n\n"
    if sat_list:
        text += "🟥 *SAT Sinyalleri:*\n" + "\n".join(sat_list) + "\n\n"
        
    if not al_list and not sat_list:
        text += "Şu an için güçlü bir AL veya SAT sinyali bulunmuyor. Piyasa yatay veya hisseler orta bantta (Nötr)."
        
    bot.reply_to(message, text, parse_mode="Markdown")

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
    
    text = f"📰 *PİYASA RAPORU* (GSS: {gss})\n\n"
    text += f"*{title}*\n{desc}\n\n"
    
    recs = data.get("recommended_stocks", [])
    if recs:
        text += "⭐ *ÖNE ÇIKAN HİSRELER:*\n"
        for r in recs:
            text += f"• *{r.get('name', '')}*: {r.get('strategy', '')} (Hedef: {r.get('tp', '')})\n"
            
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['makro'])
def send_macro(message):
    bot.reply_to(message, "⏳ Makro veriler getiriliyor...")
    data = fetch_api("morning-report")
    if not data:
        bot.reply_to(message, "❌ Makro verilere ulaşılamadı.")
        return
        
    text = "🌍 *MAKRO EKONOMİK DURUM & PİYASA*\n\n"
    
    globals_data = data.get("global_markets", {})
    if globals_data:
        text += "🌐 *Küresel Endeksler:*\n"
        for name, info in globals_data.items():
            pct = info.get('percentage', 0.0)
            sign = "+" if pct > 0 else ""
            text += f"• {name}: {info.get('last')} (%{sign}{pct})\n"
        text += "\n"
            
    sectors = data.get("sector_analysis", [])
    if sectors:
        text += "📊 *Sektörel Isı Haritası:*\n"
        for s in sectors:
            text += f"• {s.get('name')}: {s.get('trend')} (Skor: {s.get('score')})\n"
        text += "\n"
            
    cal = data.get("economic_calendar", [])
    if cal:
        text += "🗓 *Bugünün Ekonomik Takvimi:*\n"
        for c in cal:
            text += f"• {c.get('time')} [{c.get('country')}] - {c.get('event')}\n"
            
    news = data.get("news", [])
    if news:
        text += "\n📰 *Son Haberler:*\n"
        for n in news[:3]:
            text += f"• {n.get('time')} - {n.get('title')} ({n.get('source')})\n"

    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['hisse'])
def send_stock_info(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Lütfen bir hisse kodu girin. Örnek: `/hisse THYAO`", parse_mode="Markdown")
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
    
    text = f"🎯 *{symbol} - DETAYLI ANALİZ*\n\n"
    text += f"*{outlook.get('title', '')}*\n"
    text += f"{outlook.get('description', '')}\n\n"
    
    text += f"📈 *Destek / Direnç:*\n"
    text += f"Destek: {range_est.get('support', '')}\n"
    text += f"Direnç: {range_est.get('resistance', '')}\n"
    text += f"Trend Beklentisi: {range_est.get('trend', '')}\n"
    
    bot.reply_to(message, text, parse_mode="Markdown")

def start():
    """Botu başlatan ana fonksiyon"""
    if not TOKEN:
        print("⚠️ TELEGRAM_TOKEN bulunamadı. Telegram botu başlatılmadı.")
        return
    
    print("🚀 Telegram botu mesajları dinlemeye başladı...")
    bot.infinity_polling()

if __name__ == "__main__":
    start()
