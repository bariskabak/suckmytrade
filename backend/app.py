import asyncio
import os
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.bist_client import BISTClient
from backend.analyzer import MarketAnalyzer
from backend.simulator import BacktestSimulator
from backend.live_trader import LiveTrader
from backend import config
import math

# Telegram bildirim fonksiyonu
def send_telegram_notification(text):
    try:
        from backend.telegram_bot import send_notification
        send_notification(text)
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")

def safe_float(val, default=0.0):
    if val is None: return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except:
        return default

app = FastAPI(title="BIST & Global Algorithmic Trader Assistant API")

# CORS Desteği
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Durum (State)
active_pairs = list(config.DEFAULT_ACTIVE_PAIRS)
current_timeframe = config.DEFAULT_TIMEFRAME
signals_history: List[Dict[str, Any]] = []
last_analysis_results: Dict[str, Dict[str, Any]] = {}
bist_status = "connecting"  # "connecting", "connected", "error"
session_status = "Bilinmiyor"  # "Açık", "Kapalı"
global_indices_data: Dict[str, Any] = {}
gss_value = 0.0  # Küresel Duyarlılık Skoru (-5.0 ile +5.0 arası)

cached_news: List[Dict[str, Any]] = []
last_news_update: float = 0.0

bist_client = BISTClient()

# Pydantic Modelleri
class ConfigUpdate(BaseModel):
    pairs: List[str]
    timeframe: str

class SimulateRequest(BaseModel):
    symbol: str
    timeframe: str = "15m"
    days_back: int = 30
    initial_balance: float = 10000.0
    leverage: float = 5.0
    risk_per_trade: float = 0.03
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()

def get_trt_time() -> datetime:
    """Türkiye yerel saatini (TRT - UTC+3) döner"""
    utc_now = datetime.now(timezone.utc)
    trt_tz = timezone(timedelta(hours=3))
    return utc_now.astimezone(trt_tz)

def check_bist_session() -> str:
    """BIST seans saatlerini kontrol eder (Hafta içi 10:00 - 18:00 TRT)"""
    trt_now = get_trt_time()
    # Hafta sonu kontrolü (Cumartesi = 5, Pazar = 6)
    if trt_now.weekday() >= 5:
        return "Kapalı"
    
    current_time = trt_now.time()
    start_time = datetime.strptime("10:00:00", "%H:%M:%S").time()
    end_time = datetime.strptime("18:00:00", "%H:%M:%S").time()
    
    if start_time <= current_time <= end_time:
        return "Açık"
    return "Kapalı"

def calculate_gss(indices_data: Dict[str, Dict[str, Any]]) -> float:
    """
    Küresel endeks değişimlerine göre Küresel Duyarlılık Skorunu (GSS) hesaplar.
    Nikkei, Hang Seng ve S&P 500 Vadeli endekslerinin günlük değişimlerini ağırlıklandırır.
    Dönen değer -5.0 ile +5.0 arasındadır.
    """
    try:
        weights = {
            "NIKKEI": 0.30,
            "HANGSENG": 0.30,
            "SP500_FUT": 0.40
        }
        weighted_sum = 0.0
        total_weight = 0.0
        
        for name, weight in weights.items():
            idx_info = indices_data.get(name)
            if idx_info and idx_info.get("percentage") is not None:
                weighted_sum += idx_info["percentage"] * weight
                total_weight += weight
                
        if total_weight == 0:
            return 0.0
            
        avg_pct = weighted_sum / total_weight
        # 1.5% veya üzerini tam skora (+5) veya (-5) eşitleyelim
        gss = avg_pct * 3.33
        return max(-5.0, min(5.0, gss))
    except Exception as e:
        return 0.0

live_trader = LiveTrader(initial_balance=100000.0, leverage=10.0, risk_per_trade=0.03)

# Background Task: BIST Takip ve Analiz Döngüsü (Non-blocking)
async def market_analysis_loop():
    global bist_status, session_status, global_indices_data, gss_value
    print("✅ Market analiz döngüsü başlatıldı...")
    
    await asyncio.sleep(2)
    
    while True:
        try:
            # 1. Seans Durumu Kontrolü
            session_status = check_bist_session()
            
            # 2. Küresel Piyasaları Güncelle
            global_indices_data = await asyncio.to_thread(bist_client.get_global_indices, config.GLOBAL_INDICES)
            gss_value = calculate_gss(global_indices_data)
            
            print(f"🔄 Analiz döngüsü çalışıyor... BIST Seansı: {session_status} | GSS: {round(gss_value, 2)}")
            
            # 3. BIST Hisselerini Güncelle
            tickers = await asyncio.to_thread(bist_client.fetch_tickers, active_pairs)
            valid_tickers = {k: v for k, v in tickers.items() if v.get("last") is not None}
            
            if not valid_tickers:
                bist_status = "error"
                print("❌ BIST verileri alınamadı")
            else:
                bist_status = "connected"
                print(f"✅ BIST verileri alındı — {len(valid_tickers)} hisse güncellendi")
                
            for symbol in active_pairs:
                try:
                    # Mum verilerini çek
                    df = await asyncio.to_thread(bist_client.fetch_candles, symbol, current_timeframe, 100)
                    if df.empty:
                        print(f"  ⚠️  {symbol}: Mum verisi boş döndü")
                        continue
                    
                    # Küresel skor ile harmanlanmış teknik analiz yap
                    analysis = MarketAnalyzer.analyze(df, gss_value)
                    
                    # Ticker verisini ekle
                    ticker_info = tickers.get(symbol, {"last": None, "percentage": None})
                    analysis["ticker"] = ticker_info
                    
                    # CANLI İŞLEM MOTORU (Paper Trading)
                    if live_trader.is_active:
                        current_price = analysis["price"]
                        high_price = float(df['high'].iloc[-1])
                        low_price = float(df['low'].iloc[-1])
                        live_trader.process_tick(symbol, current_price, high_price, low_price, analysis)
                    
                    # Sinyal değiştiyse geçmişe kaydet
                    prev_result = last_analysis_results.get(symbol)
                    if not prev_result or prev_result.get("signal") != analysis["signal"]:
                        signal_event = {
                            "timestamp": int(time.time()),
                            "symbol": symbol,
                            "price": analysis["price"],
                            "signal": analysis["signal"],
                            "score": analysis["score"],
                            "confidence": analysis.get("confidence", 0),
                            "signal_mode": analysis.get("signal_mode", "MEAN_REVERSION"),
                            "details": analysis["details"],
                            "timeframe": current_timeframe
                        }
                        signals_history.insert(0, signal_event)
                        if len(signals_history) > 100:
                            signals_history.pop()
                        
                        await manager.broadcast({
                            "type": "new_signal",
                            "data": signal_event
                        })
                        print(f"  📡 {symbol}: Akıllı Sinyal = {analysis['signal']} (Skor: {analysis['score']}, Güven: %{analysis.get('confidence', 0)})")
                        
                        # Güçlü sinyallerde otomatik Telegram bildirimi
                        if analysis["signal"] in ["GUCLU_AL", "GUCLU_SAT"]:
                            emoji = "🟢" if "AL" in analysis["signal"] else "🔴"
                            notif_text = (
                                f"{emoji} GÜÇLÜ SİNYAL: {symbol.split('.')[0]}\n"
                                f"Sinyal: {analysis['signal']}\n"
                                f"Fiyat: {analysis['price']}\n"
                                f"Skor: {analysis['score']} | Güven: %{analysis.get('confidence', 0)}\n"
                                f"Strateji: {analysis.get('signal_mode', '')}\n"
                                f"Detay: {', '.join(analysis.get('details', [])[:2])}"
                            )
                            send_telegram_notification(notif_text)
                    
                    last_analysis_results[symbol] = analysis
                    
                except Exception as sym_err:
                    print(f"  ❌ {symbol} analiz hatası: {sym_err}")

            # Tüm verileri arayüze yayınla
            await manager.broadcast({
                "type": "market_update",
                "data": {
                    "results": last_analysis_results,
                    "timeframe": current_timeframe,
                    "pairs": active_pairs,
                    "bist_status": bist_status,
                    "session_status": session_status,
                    "global_indices": global_indices_data,
                    "gss": round(gss_value, 2),
                    "live_trading": live_trader.get_status()
                }
            })

        except Exception as e:
            print(f"❌ Analiz döngüsünde genel hata: {e}")
            traceback.print_exc()
            bist_status = "error"
            await manager.broadcast({
                "type": "market_update",
                "data": {
                    "results": last_analysis_results,
                    "timeframe": current_timeframe,
                    "pairs": active_pairs,
                    "bist_status": bist_status,
                    "session_status": session_status,
                    "global_indices": global_indices_data,
                    "gss": round(gss_value, 2)
                }
            })
            
            
        await asyncio.sleep(config.ANALYSIS_INTERVAL)

async def live_ticker_loop():
    """Canlı ticaret motorundaki pozisyonların anlık fiyatlarını ve PnL durumunu her 3 saniyede bir günceller."""
    while True:
        await asyncio.sleep(3)
        try:
            if live_trader.is_active and len(live_trader.positions) > 0:
                tickers = await asyncio.to_thread(bist_client.fetch_tickers, list(live_trader.positions.keys()))
                for sym, data in tickers.items():
                    if data.get("last") and sym in live_trader.positions:
                        pos = live_trader.positions[sym]
                        current_price = data["last"]
                        pos["current_price"] = current_price
                        
                        if pos["side"] == 'LONG':
                            pnl = (current_price - pos["entry_price"]) * pos["size"]
                            pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
                        else:
                            pnl = (pos["entry_price"] - current_price) * pos["size"]
                            pnl_pct = ((pos["entry_price"] - current_price) / pos["entry_price"]) * 100 * pos["leverage"]
                            
                        # Keep fee in mind when showing open pnl
                        fee = (pos["entry_price"] * pos["size"]) * 0.0002
                        pos["pnl"] = pnl - fee
                        pos["pnl_percent"] = pnl_pct
                
                await manager.broadcast({
                    "type": "live_trading_update",
                    "data": live_trader.get_status()
                })
        except Exception as e:
            pass

async def gap_hunter_loop():
    """Saat 17:50'de Kapanış-Açılış (Gap) Stratejisi analizi yapar ve Telegram bildirimi gönderir."""
    last_run_date = None
    while True:
        await asyncio.sleep(60)
        try:
            trt_now = get_trt_time()
            current_date = trt_now.date()
            
            # Sadece hafta içi
            if trt_now.weekday() >= 5:
                continue
                
            # Saat 17:50 ile 17:55 arası kontrol et
            if trt_now.hour == 17 and trt_now.minute == 50:
                if last_run_date != current_date:
                    print("🔍 Kapanış-Açılış (Gap) Stratejisi: Sistem Taraması Başladı...")
                    last_run_date = current_date
                    
                    gap_candidates = []
                    # Sadece BIST30/100 gibi güçlü ve hacimli hisseleri tarıyoruz (active_pairs)
                    for symbol in active_pairs:
                        try:
                            # 1 günlük mum verisi al (Son 20 günü alıyoruz ki SMA hacim hesaplansın)
                            df = await asyncio.to_thread(bist_client.fetch_candles, symbol, limit=30, timeframe="1d")
                            if df.empty or len(df) < 20:
                                continue
                                
                            gap_data = MarketAnalyzer.calculate_gap_potential(df)
                            if gap_data["score"] >= 80:
                                gap_candidates.append({
                                    "symbol": symbol.replace(".IS", ""),
                                    "score": gap_data["score"],
                                    "details": gap_data["details"],
                                    "close_ratio": gap_data["close_ratio"]
                                })
                        except Exception as e:
                            pass
                            
                    # Eğer iyi adaylar varsa telegramdan gönder
                    if gap_candidates:
                        # Skora göre sırala
                        gap_candidates.sort(key=lambda x: x["score"], reverse=True)
                        
                        text = "🔔 KAPANIŞ / GAP STRATEJİSİ FIRSATLARI 🔔\n\n"
                        text += "Ertesi gün açılışta tavan veya gap-up yapma potansiyeli yüksek hisseler:\n\n"
                        
                        for c in gap_candidates[:5]:
                            text += f"🚀 *{c['symbol']}* (Skor: {c['score']})\n"
                            text += f"• {', '.join(c['details'][:2])}\n\n"
                            
                        text += "💡 Not: 18:00 kapanışına kadar kademeli alım yapılabilir."
                        send_telegram_notification(text)
        except Exception as e:
            print(f"Gap Hunter hatası: {e}")

@app.on_event("startup")
async def startup_event():
    print("🚀 FastAPI sunucusu başlatıldı.")
    asyncio.create_task(market_analysis_loop())
    asyncio.create_task(live_ticker_loop())
    asyncio.create_task(gap_hunter_loop())

# REST API Uç Noktaları

@app.get("/api/gap-hunter")
async def get_gap_hunter_results():
    """İstenilen anda o günkü Gap potansiyellerini hesaplar ve UI'a döner."""
    gap_candidates = []
    
    # Paralel çekim yapılabilir ama basitlik için sıralı (BIST verisini zorlamamak adına)
    for symbol in active_pairs:
        try:
            df = await asyncio.to_thread(bist_client.fetch_candles, symbol, limit=30, timeframe="1d")
            if df.empty or len(df) < 20:
                continue
                
            gap_data = MarketAnalyzer.calculate_gap_potential(df)
            
            # Tüm hesaplananları ekleyelim (UI'da en iyileri göstermek için)
            gap_candidates.append({
                "symbol": symbol.replace(".IS", ""),
                "score": gap_data["score"],
                "details": gap_data["details"],
                "close_ratio": gap_data["close_ratio"],
                "vol_ratio": gap_data["vol_ratio"],
                "pct_change": gap_data["pct_change"]
            })
        except Exception:
            pass
            
    # Skora göre sırala ve en yüksek 10 tanesini UI'a gönder
    gap_candidates.sort(key=lambda x: x["score"], reverse=True)
    return {"status": "success", "candidates": gap_candidates[:12]}

# REST API Uç Noktaları

@app.get("/api/health")
def health_check():
    """Sunucu sağlık kontrolü."""
    return {
        "status": "ok",
        "bist_status": bist_status,
        "session_status": session_status,
        "active_pairs": len(active_pairs),
        "gss": round(gss_value, 2),
        "signals_count": len(signals_history)
    }

@app.get("/api/config")
def get_config():
    """Mevcut konfigürasyonu döner."""
    return {
        "pairs": active_pairs,
        "timeframe": current_timeframe,
        "all_supported_pairs": config.DEFAULT_PAIRS
    }

@app.post("/api/config")
def update_config(cfg: ConfigUpdate):
    """Takip edilen hisseleri ve zaman dilimini günceller."""
    global active_pairs, current_timeframe, last_analysis_results
    
    clean_pairs = [p for p in cfg.pairs if p in config.DEFAULT_PAIRS]
    if not clean_pairs:
        raise HTTPException(status_code=400, detail="En az bir geçerli hisse senedi seçilmelidir.")
        
    active_pairs = clean_pairs
    current_timeframe = cfg.timeframe
    last_analysis_results.clear()
    
    return {"status": "success", "pairs": active_pairs, "timeframe": current_timeframe}

def make_recommendation_item(sym: str, res: dict) -> dict:
    price = res.get("price") or 100.0
    entry_min = round(price * 0.992, 2)
    entry_max = round(price * 1.002, 2)
    tp = round(price * 1.045, 2)
    sl = round(price * 0.975, 2)
    
    sig = res.get("signal", "NOTR")
    score = res.get("score", 0.0)
    
    # Strategy determination
    if score >= 3.5:
        strategy = "Güçlü Kademeli Alım (Agresif)"
        risk = "Düşük/Orta Risk - Güçlü Trend Takibi"
    elif 1.5 <= score < 3.5:
        strategy = "Kademeli Alım / Parçalı Giriş"
        risk = "Düşük Risk - Dengeli Giriş"
    elif -1.5 < score <= 0:
        strategy = "Defansif Kademeli Biriktirme"
        risk = "Orta Risk - Destek Dönüşü Beklentisi"
    else:
        strategy = "Korumalı Kademeli Alım"
        risk = "Yüksek Risk - Tepki Alımı Denemesi"

    # Indicators support description
    indicators_support = []
    inds = res.get("indicators", {})
    if inds:
        rsi_val = inds.get("rsi")
        if rsi_val:
            indicators_support.append(f"RSI ({rsi_val})")
        ema = inds.get("ema", {})
        if ema:
            fast = ema.get("fast")
            slow = ema.get("slow")
            if fast and slow:
                if fast > slow:
                    indicators_support.append("EMA Altın Kesişim")
                else:
                    indicators_support.append("EMA Negatif Eğilim")
        macd = inds.get("macd", {})
        if macd:
            hist = macd.get("hist")
            if hist and hist > 0:
                indicators_support.append("MACD Boğa Bölgesi")
    
    if not indicators_support:
        indicators_support = ["Teknik Gösterge Desteği", "EMA 200 Seviyesi"]

    # Step details
    step1_price = round(price * 1.00, 2)
    step2_price = round(price * 0.992, 2)
    step3_price = round(price * 0.985, 2)
    
    steps = [
        f"1. Kademe (%30 Giriş): {step1_price} TL seviyesinden açılışla",
        f"2. Kademe (%40 Takviye): {step2_price} TL ara destek seviyesine geri çekilmede",
        f"3. Kademe (%30 Koruma): {step3_price} TL ana destek seviyesinden son ekleme"
    ]

    if "AL" in sig:
        rationale = "Güçlü teknik göstergeler, RSI aşırı satım desteği ve EMA trend yönü ile yukarı kırılım beklentisi."
    elif "SAT" in sig:
        rationale = "Düzeltme sonrası destek seviyelerinden tepki alımı ve kısa vadeli toparlanma potansiyeli."
    else:
        rationale = "EMA 200 seviyesi üzerinde konsolidasyon ve hacimli kırılım öncesi kademeli biriktirme."

    return {
        "symbol": sym,
        "name": sym.split('.')[0],
        "price": price,
        "entry_range": f"{entry_min} - {entry_max} TL",
        "tp": f"{tp} TL",
        "tp_pct": "+4.5%",
        "sl": f"{sl} TL",
        "sl_pct": "-2.5%",
        "strategy": strategy,
        "indicators_support": indicators_support,
        "timeframe_horizon": "1-3 Seans / Kısa Vade",
        "steps": steps,
        "rationale": rationale,
        "risk": risk
    }

@app.get("/api/signals")
def get_signals():
    """Sinyal geçmişini döner."""
    return signals_history

@app.get("/api/results")
def get_results():
    """En son analiz sonuçlarını döner."""
    return last_analysis_results

@app.get("/api/morning-report")
async def get_morning_report(symbol: str = None):
    """Sabah seans öncesi gün içi analiz, öneri ve haber raporu."""
    global cached_news, last_news_update
    if symbol and symbol in last_analysis_results:
        res = last_analysis_results[symbol]
        sig = res.get("signal", "NOTR")
        score = res.get("score", 0.0)
        details = res.get("details", [])
        
        # Hisse için Pivot Noktalarını (Support / Resistance) hesapla
        try:
            df = await asyncio.to_thread(bist_client.fetch_candles, symbol, current_timeframe, 50)
            if not df.empty and len(df) >= 20:
                recent_df = df.tail(20)
                high = float(recent_df['high'].max())
                low = float(recent_df['low'].min())
                close = float(recent_df['close'].iloc[-1])
                pp = (high + low + close) / 3.0
                s1 = 2.0 * pp - high
                s2 = pp - (high - low)
                r1 = 2.0 * pp - low
                r2 = pp + (high - low)
                
                support_str = f"{round(s1, 2)} / {round(s2, 2)}"
                resistance_str = f"{round(r1, 2)} / {round(r2, 2)}"
            else:
                price = res.get("price") or 100.0
                support_str = f"{round(price * 0.98, 2)} / {round(price * 0.96, 2)}"
                resistance_str = f"{round(price * 1.02, 2)} / {round(price * 1.04, 2)}"
        except Exception as e:
            print(f"Pivot noktası hesaplama hatası ({symbol}): {e}")
            price = res.get("price") or 100.0
            support_str = f"{round(price * 0.98, 2)} / {round(price * 0.96, 2)}"
            resistance_str = f"{round(price * 1.02, 2)} / {round(price * 1.04, 2)}"

        # Hisse özelinde beklenti metni üret
        if "AL" in sig or "BUY" in sig:
            outlook_title = f"{symbol.split('.')[0]} Algoritmik Alım (Dip Avcısı) Sinyali"
            outlook_class = "gss-positive"
            details_str = f" ({', '.join(details)})" if details else ""
            outlook_desc = (
                f"🚨 QUANT ALERT: {symbol.split('.')[0]} hissesi, Bollinger Alt Bandı dışına taşarak aşırı satım (Oversold) bölgesine girdi (Skor: {score}){details_str}. "
                "Mean Reversion algoritmamız bu seviyeyi irrasyonel bir panik satışı olarak değerlendirmektedir. "
                "Buradan yaşanacak ilk yukarı sekmelerde agresif kâr alımı (Scalping) planlanmaktadır. Alım yönlü pozisyonlar için ideal fırsat bölgesidir."
            )
            trend_str = "Kısa Vadeli Sıçrama (Bouncing)"
        elif "SAT" in sig or "SELL" in sig:
            outlook_title = f"{symbol.split('.')[0]} Algoritmik Kâr Alma (Tepe) Sinyali"
            outlook_class = "gss-negative"
            details_str = f" ({', '.join(details)})" if details else ""
            outlook_desc = (
                f"🚨 QUANT ALERT: {symbol.split('.')[0]} hissesi, aşırı alım bölgesi olan Bollinger Üst Bandını zorluyor (Skor: {score}){details_str}. "
                "Piyasadaki mevcut FOMO (coşku) dalgası, algoritmamız tarafından kâr realizasyonu (SHORT) fırsatı olarak görülmektedir. "
                "Fiyatın ortalamasına (SMA 20) doğru hızlı bir geri çekilme ihtimali yüksektir. Dirençte satıcı olmak rasyoneldir."
            )
            trend_str = "Ortalamaya Düşüş (Pullback)"
        else:
            outlook_title = f"{symbol.split('.')[0]} Nötr / Testere Bandı"
            outlook_class = "gss-neutral"
            details_str = f" ({', '.join(details)})" if details else ""
            outlook_desc = (
                f"⚖️ {symbol.split('.')[0]} hissesi şu an Bollinger bantlarının merkezinde (Adil Değer) fiyatlanıyor (Skor: {score}){details_str}. "
                "Algoritma, fiyatın uç bantlardan birine değmesini beklemektedir. "
                "Bu seviyeden rastgele işlem açmak kasa riskini artırır. Sabırla bandın dışına bir 'volatilite patlaması' beklenmelidir."
            )
            trend_str = "Yatay Bant (Range Bound)"
            
        # Öneri hisseler (seçili hisse olsa da genel sabah listesi kalır)
        recommended_stocks = []
        candidates = []
        for s, r in last_analysis_results.items():
            if "AL" in r.get("signal", ""):
                candidates.append((s, r))
        fallback_candidates = ["THYAO.IS", "TUPRS.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS"]
        for s in fallback_candidates:
            if len(candidates) >= 3:
                break
            if s in last_analysis_results and s not in [c[0] for c in candidates]:
                candidates.append((s, last_analysis_results[s]))
            elif s not in [c[0] for c in candidates]:
                candidates.append((s, {"price": 100.0, "signal": "NOTR", "score": 0.0}))

        for s, r in candidates[:3]:
            recommended_stocks.append(make_recommendation_item(s, r))
            
        now = time.time()
        if now - last_news_update > 300 or not cached_news: # 5 minutes cache
            try:
                # 5 saniye timeout ile haberleri çekmeyi dene, kilitlenmeyi önle
                cached_news = await asyncio.wait_for(
                    asyncio.to_thread(bist_client.get_market_news),
                    timeout=5.0
                )
                last_news_update = now
            except Exception as e:
                print(f"Haberler alınamadı veya zaman aşımı: {e}")
                if not cached_news:
                    cached_news = [{"title": "Haber akışı şu anda alınamıyor.", "source": "Sistem", "link": "#", "time": ""}]
        
        return {
            "outlook": {
                "title": outlook_title,
                "class": outlook_class,
                "description": outlook_desc,
                "gss": round(score, 2)
            },
            "range_estimate": {
                "support": support_str,
                "resistance": resistance_str,
                "trend": trend_str
            },
            "global_markets": global_indices_data,
            "recommended_stocks": recommended_stocks,
            "news": cached_news
        }

    # 1. Genel Açılış beklentisi belirleme (BIST 100 geneli)
    if gss_value > 1.5:
        outlook_title = "Güçlü Pozitif Açılış"
        outlook_class = "gss-positive"
        outlook_desc = (
            f"Küresel piyasa duyarlılık skoru ({round(gss_value, 2)}) oldukça güçlü seyrediyor. "
            "Uzak Doğu borsalarının alıcılı kapanışının ardından güne alıcılı ve yukarı yönlü bir boşlukla (gap) başlanması bekleniyor. "
            "Küçük bütçeli alımlar için güçlü trend takip eden hisselerde kademeli alım stratejisi uygulanabilir."
        )
    elif gss_value > 0.5:
        outlook_title = "Pozitif Açılış"
        outlook_class = "gss-positive"
        outlook_desc = (
            f"Küresel duyarlılık skoru ({round(gss_value, 2)}) pozitif bölgede. "
            "BIST 100 endeksinin güne hafif alıcılı başlaması bekleniyor. Açılışın ardından hisse bazlı hareketlilik "
            "ön plana çıkacaktır. Bankacılık ve ulaştırma sektörlerindeki destek seviyeleri alım fırsatı sunabilir."
        )
    elif gss_value < -1.5:
        outlook_title = "Sert Satıcılı Açılış"
        outlook_class = "gss-negative"
        outlook_desc = (
            f"Küresel piyasalarda ciddi bir riskten kaçış havası var (GSS: {round(gss_value, 2)}). "
            "Güne satıcılı bir başlangıç yapılması ve destek seviyelerinin test edilmesi bekleniyor. "
            "Sabah saatlerinde aceleci alımlardan kaçınarak piyasanın taban oluşturmasını beklemek ve nakit oranını korumak mantıklı olacaktır."
        )
    elif gss_value < -0.5:
        outlook_title = "Negatif Açılış"
        outlook_class = "gss-negative"
        outlook_desc = (
            f"Küresel duyarlılık skoru ({round(gss_value, 2)}) negatif bölgede seyrediyor. "
            "Endeksin güne hafif satıcılı başlaması beklenmektedir. Gün içi toparlanma eğilimleri için global vadeli "
            "kontratlar ve döviz kurları yakından takip edilmelidir. Kademeli alım için alt destekler beklenmelidir."
        )
    else:
        outlook_title = "Yatay / Kararsız Açılış"
        outlook_class = "gss-neutral"
        outlook_desc = (
            f"Küresel endeksler yatay bir bantta hareket ediyor (GSS: {round(gss_value, 2)}). "
            "BIST 100 endeksinin güne yatay ve sakin bir başlangıç yapması beklenmektedir. "
            "Endeksteki sıkışma seans içi kırılımlara göre yön bulacaktır. Seçici ve hisse bazlı hareketler tercih edilmelidir."
        )

    # 2. Algoritmik Hisse Tarayıcı (En Yüksek Skorlular)
    recommended_stocks = []
    candidates = []
    
    for sym, res in last_analysis_results.items():
        sig = res.get("signal", "")
        if "AL" in sig or "BUY" in sig:
            candidates.append((sym, res))
            
    # Skora göre büyükten küçüğe sırala (En güçlü sinyaller)
    candidates.sort(key=lambda x: x[1].get("score", 0), reverse=True)
            
    fallback_candidates = ["THYAO.IS", "TUPRS.IS", "ASELS.IS", "EREGL.IS", "BIMAS.IS"]
    for sym in fallback_candidates:
        if len(candidates) >= 3:
            break
        if sym in last_analysis_results and sym not in [c[0] for c in candidates]:
            candidates.append((sym, last_analysis_results[sym]))
        elif sym not in [c[0] for c in candidates]:
            candidates.append((sym, {"price": 100.0, "signal": "NOTR", "score": 0.0}))

    for sym, res in candidates[:3]:
        recommended_stocks.append(make_recommendation_item(sym, res))

    # 3. Haberler
    now = time.time()
    if now - last_news_update > 300 or not cached_news:
        try:
            cached_news = await asyncio.wait_for(
                asyncio.to_thread(bist_client.get_market_news),
                timeout=5.0
            )
            last_news_update = now
        except Exception as e:
            print(f"Genel haberler alınamadı veya zaman aşımı: {e}")
            if not cached_news:
                cached_news = [{"title": "Haber akışı şu anda alınamıyor.", "source": "Sistem", "link": "#", "time": ""}]

    # 4. Sektörel Isı Haritası
    sectors = {
        "Bankacılık": ["AKBNK.IS", "GARAN.IS", "ISCTR.IS", "YKBNK.IS"],
        "Sanayi & Enerji": ["TUPRS.IS", "EREGL.IS", "FROTO.IS", "TOASO.IS", "PETKM.IS", "SASA.IS", "ASTOR.IS"],
        "Hizmet & Ulaştırma": ["THYAO.IS", "PGSUS.IS", "TCELL.IS", "MGROS.IS", "BIMAS.IS"],
        "Holding": ["KCHOL.IS", "SAHOL.IS", "ALARK.IS"]
    }
    
    sector_analysis = []
    for s_name, s_stocks in sectors.items():
        total_score = 0
        count = 0
        for stock in s_stocks:
            if stock in last_analysis_results:
                total_score += last_analysis_results[stock].get("score", 0)
                count += 1
        avg_score = (total_score / count) if count > 0 else 0
        
        trend = "Yatay"
        color = "neutral"
        if avg_score > 1.0:
            trend = "Güçlü Alış"
            color = "positive"
        elif avg_score > 0.3:
            trend = "Pozitif"
            color = "positive"
        elif avg_score < -1.0:
            trend = "Güçlü Satış"
            color = "negative"
        elif avg_score < -0.3:
            trend = "Negatif"
            color = "negative"
            
        sector_analysis.append({
            "name": s_name,
            "score": round(avg_score, 2),
            "trend": trend,
            "color": color
        })

    # Dinamik Destek/Direnç hesaplama (BIST 30 / XU030 verisiyle)
    def _calculate_dynamic_sr(level_type):
        try:
            xu030_data = global_indices_data.get("VIOP_30", {})
            xu030_last = xu030_data.get("last")
            if xu030_last and xu030_last > 0:
                if level_type == "support":
                    s1 = round(xu030_last * 0.985, 0)
                    s2 = round(xu030_last * 0.975, 0)
                    return f"{int(s1)} / {int(s2)}"
                else:
                    r1 = round(xu030_last * 1.015, 0)
                    r2 = round(xu030_last * 1.025, 0)
                    return f"{int(r1)} / {int(r2)}"
        except:
            pass
        return "Hesaplanamadı"

    # 5. Ekonomik Takvim (Mock / Curated for today)
    import datetime
    economic_calendar = [
        {"time": "10:00", "country": "TR", "event": "TCMB Finansal İstikrar Raporu", "importance": "high"},
        {"time": "12:00", "country": "EU", "event": "Euro Bölgesi TÜFE (Enflasyon)", "importance": "high"},
        {"time": "15:30", "country": "US", "event": "Tarım Dışı İstihdam (NFP)", "importance": "high"},
        {"time": "17:00", "country": "US", "event": "Michigan Tüketici Güveni", "importance": "medium"}
    ]

    return {
        "outlook": {
            "title": outlook_title,
            "class": outlook_class,
            "description": outlook_desc,
            "gss": round(gss_value, 2)
        },
        "range_estimate": {
            "support": _calculate_dynamic_sr("support"),
            "resistance": _calculate_dynamic_sr("resistance"),
            "trend": "Yatay-Pozitif" if gss_value >= 0 else "Yatay-Negatif"
        },
        "global_markets": global_indices_data,
        "recommended_stocks": recommended_stocks,
        "news": cached_news,
        "sector_analysis": sector_analysis,
        "economic_calendar": economic_calendar
    }

@app.get("/api/candles/{symbol:path}")
async def get_candles(symbol: str):
    """Belirli bir hissenin mum verilerini döner."""
    df = await asyncio.to_thread(bist_client.fetch_candles, symbol, current_timeframe, 100)
    if df.empty:
        raise HTTPException(status_code=404, detail="Mum verileri alınamadı.")
        
    candles_list = []
    for _, row in df.iterrows():
        # yfinance timestamp datetime nesnesidir veya integer'dır.
        # bist_client.fetch_candles milisaniye döndüğü için saniyeye çeviriyoruz.
        candles_list.append({
            "time": int(row['timestamp'] / 1000),
            "open": safe_float(row['open']),
            "high": safe_float(row['high']),
            "low": safe_float(row['low']),
            "close": safe_float(row['close']),
            "volume": safe_float(row['volume'])
        })
    return candles_list

@app.post("/api/trade")
def mock_trade(symbol: str, side: str, amount: float):
    """Sanal BIST işlemi gerçekleştirir."""
    # İşlemi simüle et
    return {
        "status": "success",
        "order": {
            "id": f"bist-mock-{int(time.time())}",
            "symbol": symbol,
            "side": side,
            "type": "market",
            "amount": amount,
            "status": "closed",
            "info": "BIST Sanal/Simüle İşlem"
        }
    }

@app.post("/api/simulate")
async def run_simulation(req: SimulateRequest):
    """
    Belirli bir sembol için geçmiş verileri çekerek kaldıraçlı backtest simülasyonu çalıştırır.
    Böylece stratejinin (Volume & Sinyaller) ne kadar başarılı olduğunu görebiliriz.
    """
    # 1 günde 15m'lik yaklaşık 32-40 mum olur.
    limit = min(req.days_back * 40, 1000) # En fazla 1000 mum (BIST sınırları gereği veya API sınırı)
    
    if req.start_date and req.timeframe == '15m':
        import datetime
        start_dt = datetime.datetime.strptime(req.start_date, "%Y-%m-%d")
        if (datetime.datetime.now() - start_dt).days > 59:
            raise HTTPException(status_code=400, detail="Yahoo Finance kısıtlaması nedeniyle 15 dakikalık (15m) veriler sadece son 60 gün için çekilebilir. Lütfen daha yakın bir tarih aralığı seçin veya '1d' (Günlük) periyodu kullanın.")
    
    df = await asyncio.to_thread(bist_client.fetch_candles, req.symbol, req.timeframe, limit, req.start_date, req.end_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="Simülasyon için yeterli veri alınamadı.")
        
    sim = BacktestSimulator(
        df=df,
        initial_balance=req.initial_balance,
        leverage=req.leverage,
        maker_fee=0.0002,  # Binde 2
        taker_fee=0.0004,  # Binde 4
        risk_per_trade=req.risk_per_trade,
        days_back=req.days_back
    )
    
    result = sim.run()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return {
        "status": "success",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "days_back": req.days_back,
        "simulation_result": result
    }

@app.get("/api/live-trading/status")
def get_live_trading_status():
    """Canlı kağıt üstünde işlem (Paper Trading) motorunun anlık durumunu döndürür."""
    return live_trader.get_status()

class LiveToggleRequest(BaseModel):
    active: bool

@app.post("/api/live-trading/toggle")
def toggle_live_trading(req: LiveToggleRequest):
    """Canlı kağıt üstünde işlem (Paper Trading) motorunu başlatır veya durdurur."""
    if req.active:
        live_trader.start()
    else:
        live_trader.stop()
    return {"status": "success", "is_active": live_trader.is_active}

# WebSocket Uç Noktası
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"🔌 WebSocket bağlantısı açıldı ({len(manager.active_connections)} aktif)")
    try:
        # İlk bağlantıda mevcut durumu gönder
        await websocket.send_json({
            "type": "welcome",
            "data": {
                "results": last_analysis_results,
                "history": signals_history,
                "timeframe": current_timeframe,
                "pairs": active_pairs,
                "bist_status": bist_status,
                "session_status": session_status,
                "global_indices": global_indices_data,
                "gss": round(gss_value, 2)
            }
        })
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"🔌 WebSocket bağlantısı kapandı ({len(manager.active_connections)} aktif)")
    except Exception as e:
        print(f"WebSocket hatası: {e}")
        manager.disconnect(websocket)

# Statik Dosyaların Sunulması
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def get_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))
