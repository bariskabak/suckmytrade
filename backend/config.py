import os

# Tüm desteklenen BIST 100 hisseleri (Yahoo Finance Ticker formatında)
DEFAULT_PAIRS = [
    "THYAO.IS", "TUPRS.IS", "EREGL.IS", "ASELS.IS", "BIMAS.IS",
    "KCHOL.IS", "SAHOL.IS", "GARAN.IS", "AKBNK.IS", "YKBNK.IS",
    "SISE.IS", "PGSUS.IS", "SASA.IS", "HEKTS.IS", "TOASO.IS",
    "FROTO.IS", "PETKM.IS", "KOZAL.IS", "EKGYO.IS", "ODAS.IS",
    "ISCTR.IS", "HALKB.IS", "VAKBN.IS", "ALARK.IS", "SOKM.IS",
    "MGROS.IS", "KOZAA.IS", "ENKAI.IS", "DOHOL.IS", "TTKOM.IS",
    "TCELL.IS", "GUBRF.IS", "TKFEN.IS", "VESBE.IS", "OTKAR.IS",
    "EGEEN.IS", "CIMSA.IS", "AKSEN.IS", "BRSAN.IS", "TSKB.IS",
    "OYAKC.IS", "MAVI.IS", "MIATK.IS", "REEDR.IS", "KONTR.IS",
    "YEOTK.IS", "SMRTG.IS", "ASTOR.IS", "ALFAS.IS", "CWENE.IS",
    "SDTTR.IS", "TABGD.IS", "KBORU.IS", "EUPWR.IS", "GESAN.IS",
    "KLSER.IS", "BRYAT.IS", "ALBRK.IS", "SKBNK.IS", "ISMEN.IS",
    "ZOREN.IS", "IZMDC.IS", "TATEN.IS", "ENERY.IS"
]

# Başlangıçta aktif olarak takip edilecek varsayılan hisseler (VİOP Odaklı)
DEFAULT_ACTIVE_PAIRS = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", 
    "BRSAN.IS", "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", 
    "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS", 
    "KOZAA.IS", "KOZAL.IS", "MGROS.IS", "OYAKC.IS", "PETKM.IS", 
    "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", 
    "THYAO.IS", "TOASO.IS", "TUPRS.IS", "YKBNK.IS"
]

# Küresel Piyasa Göstergeleri (Korelasyon analizi için)
GLOBAL_INDICES = {
    "VIOP_30": "XU030.IS",     # BIST 30 (VIOP Dayanağı)
    "NIKKEI": "^N225",        # Japonya Nikkei 225
    "HANGSENG": "^HSI",       # Hong Kong Hang Seng
    "SHANGHAI": "000001.SS",  # Çin Shanghai Composite
    "SP500_FUT": "ES=F",       # ABD S&P 500 Vadeli
    "NASDAQ_FUT": "NQ=F"       # ABD Nasdaq Vadeli
}

# Analiz Parametreleri
DEFAULT_TIMEFRAME = "1d"  # 15m, 1h, 1d
ANALYSIS_INTERVAL = 20  # BIST seansında veri çekme sıklığı (saniye)

# Teknik Gösterge Varsayılan Ayarları
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
