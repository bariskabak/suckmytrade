#!/usr/bin/env python3
"""Dependency checker and diagnostic script"""
import sys, os

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print()

deps = {
    'fastapi': None,
    'uvicorn': None,
    'ccxt': None,
    'pandas': None,
    'numpy': None,
    'websockets': None,
}

for name in deps:
    try:
        mod = __import__(name)
        ver = getattr(mod, '__version__', 'OK')
        deps[name] = ver
        print(f"  ✅ {name}: {ver}")
    except ImportError:
        print(f"  ❌ {name}: NOT INSTALLED")

print()

# Check port 8000
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('127.0.0.1', 8000))
if result == 0:
    print("🔵 Port 8000: OCCUPIED (sunucu zaten çalışıyor)")
else:
    print("⚪ Port 8000: FREE (sunucu çalışmıyor)")
s.close()

# Quick OKX connectivity test
try:
    import ccxt
    print("\n🔄 OKX bağlantı testi yapılıyor...")
    exchange = ccxt.okx({'enableRateLimit': True, 'timeout': 10000})
    ticker = exchange.fetch_ticker('BTC/USDT')
    print(f"  ✅ OKX BTC/USDT fiyat: ${ticker['last']}")
except Exception as e:
    print(f"  ❌ OKX bağlantı hatası: {e}")

print("\n--- Tanılama tamamlandı ---")
