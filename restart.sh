#!/bin/bash
# OKX Trader Asistanı - Tek Tuşla Sıfırdan Başlatma Betiği
# Kullanım: bash restart.sh

echo "🛑 Eski sunucu süreçleri durduruluyor..."
pkill -f "uvicorn" 2>/dev/null
pkill -f "python.*run.py" 2>/dev/null
sleep 2

echo "📦 Gerekli paketler yükleniyor..."
pip3 install fastapi uvicorn ccxt pandas numpy websockets 2>&1 | tail -5

echo ""
echo "🚀 Sunucu başlatılıyor..."
echo "   http://127.0.0.1:8000"
echo "   Durdurmak için Ctrl+C"
echo ""

cd "$(dirname "$0")"
python3 run.py
