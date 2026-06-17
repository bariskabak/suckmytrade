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

SECTOR_MAP = {
    # Bankacılık
    "AKBNK.IS": "Bankacılık", "GARAN.IS": "Bankacılık", "ISCTR.IS": "Bankacılık", 
    "YKBNK.IS": "Bankacılık", "HALKB.IS": "Bankacılık", "VAKBN.IS": "Bankacılık",
    "TSKB.IS": "Bankacılık", "ALBRK.IS": "Bankacılık", "SKBNK.IS": "Bankacılık",
    "ISMEN.IS": "Bankacılık/Finans",
    
    # Holding
    "KCHOL.IS": "Holding", "SAHOL.IS": "Holding", "ENKAI.IS": "Holding", 
    "DOHOL.IS": "Holding", "TKFEN.IS": "Holding", "ALARK.IS": "Holding",
    
    # Havacılık / Ulaştırma
    "THYAO.IS": "Havacılık", "PGSUS.IS": "Havacılık",
    
    # Otomotiv
    "FROTO.IS": "Otomotiv", "TOASO.IS": "Otomotiv", "OTKAR.IS": "Otomotiv", "EGEEN.IS": "Otomotiv",
    
    # Enerji / Petrol
    "TUPRS.IS": "Petrol/Kimya", "PETKM.IS": "Petrol/Kimya", "ASTOR.IS": "Enerji", 
    "ALFAS.IS": "Enerji", "CWENE.IS": "Enerji", "EUPWR.IS": "Enerji", "GESAN.IS": "Enerji", 
    "SMRTG.IS": "Enerji", "YEOTK.IS": "Enerji", "ZOREN.IS": "Enerji", "TATEN.IS": "Enerji", 
    "ENERY.IS": "Enerji", "AKSEN.IS": "Enerji", "ODAS.IS": "Enerji",
    
    # Perakende / Ticaret
    "BIMAS.IS": "Perakende", "MGROS.IS": "Perakende", "SOKM.IS": "Perakende", "MAVI.IS": "Perakende",
    
    # Teknoloji / Savunma / Yazılım
    "ASELS.IS": "Savunma", "MIATK.IS": "Teknoloji", "REEDR.IS": "Teknoloji", "KONTR.IS": "Teknoloji", "SDTTR.IS": "Teknoloji",
    
    # Telekom
    "TTKOM.IS": "Telekomünikasyon", "TCELL.IS": "Telekomünikasyon",
    
    # Demir-Çelik / Sanayi
    "EREGL.IS": "Demir Çelik", "KRDMD.IS": "Demir Çelik", "BRSAN.IS": "Demir Çelik", 
    "CIMSA.IS": "Çimento", "OYAKC.IS": "Çimento", "KLSER.IS": "Seramik", "KBORU.IS": "Sanayi",
    "BRYAT.IS": "Sanayi", "IZMDC.IS": "Demir Çelik",
    
    # Madencilik / Altın
    "KOZAL.IS": "Madencilik", "KOZAA.IS": "Madencilik",
    
    # Gıda / Tarım
    "HEKTS.IS": "Tarım", "GUBRF.IS": "Tarım", "TABGD.IS": "Gıda",
    
    # Kimya
    "SASA.IS": "Kimya", "SISE.IS": "Cam/Kimya",
    
    # GYO / İnşaat
    "EKGYO.IS": "Gayrimenkul",
    
    # Dayanıklı Tüketim
    "VESBE.IS": "Dayanıklı Tüketim"
}

# Başlangıçta aktif olarak takip edilecek varsayılan hisseler (VİOP Odaklı)
DEFAULT_ACTIVE_PAIRS = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", 
    "BRSAN.IS", "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", 
    "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS", 
    "MGROS.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS", "SAHOL.IS", 
    "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS", 
    "TUPRS.IS", "YKBNK.IS"
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
