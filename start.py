#!/usr/bin/env python3
"""
BIST Trader Asistanı - Otomatik Başlatıcı
Çalıştırma: python3 start.py
"""
import subprocess, sys, os, signal, time

print("=" * 55)
print("  BIST VE KÜRESEL PİYASA TRADER ASISTANI - BAŞLATICI")
print("=" * 55)

# 1. Eski sunucuları durdur
print("\n🛑 Eski sunucu süreçleri kontrol ediliyor...")
try:
    r = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
    pids = [p.strip() for p in r.stdout.strip().split('\n') if p.strip()]
    if pids:
        print(f"   Eski PID'ler bulundu: {', '.join(pids)}")
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except:
                pass
        time.sleep(2)
        print("   ✅ Eski süreçler sonlandırıldı.")
    else:
        print("   ✅ Port 8000 zaten boş.")
except:
    print("   ⚠️  Port kontrolü atlandı.")

# 2. Bağımlılıkları kur
print("\n📦 Bağımlılıklar kontrol ediliyor...")
deps_to_install = []
for pkg_name, pip_name in [
    ('fastapi', 'fastapi'),
    ('uvicorn', 'uvicorn[standard]'),
    ('yfinance', 'yfinance'),
    ('pandas', 'pandas'),
    ('numpy', 'numpy'),
    ('websockets', 'websockets'),
]:
    try:
        if pkg_name == 'yfinance':
            __import__('yfinance')
        else:
            __import__(pkg_name)
        print(f"   ✅ {pkg_name}")
    except ImportError:
        print(f"   ❌ {pkg_name} — YÜKLENİYOR...")
        deps_to_install.append(pip_name)

if deps_to_install:
    print(f"\n⬇️  Eksik paketler yükleniyor: {', '.join(deps_to_install)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + deps_to_install)
    print("✅ Kurulum tamamlandı.\n")

# 3. BIST bağlantı testi
print("🌐 BIST veri bağlantısı test ediliyor (Yahoo Finance)...")
try:
    import yfinance as yf
    ticker = yf.Ticker('THYAO.IS')
    info = ticker.history(period="1d")
    if not info.empty:
        last_price = info['Close'].iloc[-1]
        print(f"   ✅ BIST Bağlantısı Başarılı! THYAO.IS = {last_price} TL")
    else:
        raise Exception("Boş veri döndü.")
except Exception as e:
    print(f"   ⚠️  BIST testi başarısız: {e}")
    print("   Sunucu yine de başlatılacak.\n")

# 4. Sunucuyu başlat
print("\n" + "=" * 55)
print("  🚀 SUNUCU BAŞLATILIYOR")
print("  📊 http://127.0.0.1:8000")
print("  🛑 Ctrl + C ile kapatın")
print("=" * 55 + "\n")

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
uvicorn.run(
    "backend.app:app",
    host="0.0.0.0",
    port=8000,
    reload=False,
    log_level="info"
)
