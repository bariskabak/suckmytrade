import os
import sys
import subprocess
import signal
import socket

def install_requirements():
    print("📦 Gerekli Python kütüphaneleri kontrol ediliyor...")
    missing = []
    deps = {
        'fastapi': 'fastapi>=0.100.0',
        'uvicorn': 'uvicorn>=0.22.0',
        'yfinance': 'yfinance>=0.2.38',
        'pandas': 'pandas>=2.0.0',
        'numpy': 'numpy>=1.24.0',
        'websockets': 'websockets>=11.0',
        'telebot': 'pyTelegramBotAPI>=4.12.0',
        'dotenv': 'python-dotenv>=1.0.0',
    }
    for name, pkg in deps.items():
        try:
            if name == 'yfinance':
                __import__('yfinance')
            else:
                __import__(name)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"❌ Eksik paketler bulundu: {', '.join(missing)}")
        print("⬇️  Yükleniyor...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT
            )
            print("✅ Tüm paketler yüklendi.")
        except Exception as e:
            print(f"🔴 Kurulum hatası: {e}")
            sys.exit(1)
    else:
        print("✅ Tüm bağımlılıklar zaten yüklü.")

def kill_port(port=8000):
    """Port üzerinde çalışan tüm işlemleri sonlandır"""
    print(f"🔄 Port {port} kontrol ediliyor...")
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split('\n')
        pids = [p.strip() for p in pids if p.strip()]
        if pids:
            print(f"⚠️  Port {port} meşgul. PID'ler sonlandırılıyor: {', '.join(pids)}")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            import time
            time.sleep(1)
            print(f"✅ Port {port} serbest bırakıldı.")
        else:
            print(f"✅ Port {port} zaten boş.")
    except Exception as e:
        print(f"⚠️  Port kontrolü yapılamadı: {e}")

def check_bist_connection():
    """BIST veri bağlantısını test et (Yahoo Finance)"""
    print("🌐 BIST veri bağlantısı test ediliyor (Yahoo Finance)...")
    try:
        import yfinance as yf
        ticker = yf.Ticker('THYAO.IS')
        info = ticker.history(period="1d")
        if not info.empty:
            last_price = info['Close'].iloc[-1]
            print(f"✅ BIST Bağlantısı Başarılı! THYAO.IS: {last_price} TL")
            return True
        else:
            raise Exception("Hisse verisi boş döndü")
    except Exception as e:
        print(f"⚠️  BIST bağlantı uyarısı: {e}")
        print("   Sunucu yine de başlatılacak, veriler gelince arayüz güncellenecek.")
        return False

def main():
    # Proje kök dizininde olduğumuzdan emin olalım
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    
    # .env dosyasını yükle (Lokal testler için)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    
    port = int(os.environ.get("PORT", 8000))
    
    # Port temizle
    kill_port(port)
    
    # BIST bağlantı kontrolü
    check_bist_connection()
    
    print("\n" + "=" * 55)
    print("  🚀 BIST VE KÜRESEL PİYASA TRADER ASISTANI BAŞLATILIYOR")
    print("=" * 55)
    print(f"  📊 Web Arayüzü: http://127.0.0.1:{port}")
    print(f"  📊 Alternatif:  http://localhost:{port}")
    print("  🛑 Kapatmak için: Ctrl + C")
    print("=" * 55 + "\n")
    
    # Telegram botunu ayrı thread'de başlat
    def run_telegram_bot():
        try:
            from backend.telegram_bot import start as bot_start
            print("✅ Telegram Bot Thread Başlatılıyor...")
            bot_start()
        except Exception as e:
            print(f"❌ Telegram bot başlatılamadı: {e}")

    import threading
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # Uvicorn ile FastAPI sunucusunu başlat
    # host="0.0.0.0" hem IPv4 hem IPv6 dinler
    try:
        import uvicorn
        uvicorn.run(
            "backend.app:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Sistem kapatıldı.")
    except Exception as e:
        print(f"🔴 Sunucu başlatılırken hata oluştu: {e}")

if __name__ == "__main__":
    main()
