import yfinance as yf
import pandas as pd
import time
from typing import List, Dict, Any, Optional

class BISTClient:
    def __init__(self):
        pass

    @staticmethod
    def _safe_float(val):
        if val is None:
            return None
        import math
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except:
            return None

        
    def fetch_candles(self, symbol: str, timeframe: str = '15m', limit: int = 100, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Belirtilen BIST hissesi için mum verilerini çeker ve DataFrame olarak döner.
        """
        interval = '15m'
        period = '60d' # yfinance 15m verisi için 60 güne kadar izin veriyor
        
        if timeframe == '1h':
            interval = '1h'
            period = '1mo'
        elif timeframe == '1d':
            interval = '1d'
            period = '6mo'
            
        try:
            symbol = symbol.upper()
            ticker = yf.Ticker(symbol)
            
            if start_date and end_date:
                import datetime
                # Eğer kullanıcı sadece tek bir gün seçerse (başlangıç ve bitiş aynıysa)
                # yfinance bitiş tarihini exclusive (hariç) tuttuğu için boş döner.
                # Bu yüzden bitiş tarihine 1 gün ekliyoruz.
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                end_dt += datetime.timedelta(days=1)
                adjusted_end_date = end_dt.strftime("%Y-%m-%d")
                
                df = ticker.history(start=start_date, end=adjusted_end_date, interval=interval)
            else:
                df = ticker.history(period=period, interval=interval)
                
            if df.empty:
                return pd.DataFrame()
            
            df = df.reset_index()
            # Kolon isimlerini eşleştir
            df = df.rename(columns={
                df.columns[0]: 'datetime',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Milisaniye cinsinden timestamp sütunu oluştur
            df['timestamp'] = df['datetime'].astype('int64') // 10**6
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'datetime']]
            return df.tail(limit).copy()
        except Exception as e:
            print(f"BIST mum verisi çekilirken hata oluştu ({symbol}): {e}")
            return pd.DataFrame()

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Belirli bir hissenin anlık fiyat bilgilerini çeker.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5d")
            df = df.dropna(subset=['Close'])
            if len(df) >= 2:
                last_close = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                pct_change = ((last_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                return {
                    "symbol": symbol,
                    "last": self._safe_float(last_close),
                    "high": self._safe_float(df['High'].iloc[-1]),
                    "low": self._safe_float(df['Low'].iloc[-1]),
                    "percentage": self._safe_float(pct_change),
                    "baseVolume": self._safe_float(df['Volume'].iloc[-1])
                }
        except Exception as e:
            print(f"Hisse ticker çekilirken hata oluştu ({symbol}): {e}")
        return {"symbol": symbol, "last": None, "percentage": None}

    def fetch_tickers(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Tüm aktif takip edilen hisselerin fiyatlarını toplu çeker.
        """
        result = {}
        try:
            if not symbols:
                return result
            # Toplu indirme işlemi hız kazandırır
            df = yf.download(symbols, period="5d", interval="1d", group_by="ticker", progress=False)
            for sym in symbols:
                try:
                    if len(symbols) == 1:
                        sym_df = df
                    else:
                        sym_df = df[sym]
                    
                    sym_df = sym_df.dropna(subset=['Close'])
                    if len(sym_df) >= 2:
                        last_close = sym_df['Close'].iloc[-1]
                        prev_close = sym_df['Close'].iloc[-2]
                        pct_change = ((last_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                        high = sym_df['High'].iloc[-1]
                        low = sym_df['Low'].iloc[-1]
                        volume = sym_df['Volume'].iloc[-1]
                        result[sym] = {
                            "symbol": sym,
                            "last": self._safe_float(last_close),
                            "high": self._safe_float(high),
                            "low": self._safe_float(low),
                            "percentage": self._safe_float(pct_change),
                            "baseVolume": self._safe_float(volume)
                        }
                    else:
                        result[sym] = {"symbol": sym, "last": None, "percentage": None}
                except Exception as e:
                    print(f"Toplu veri okuma hatası ({sym}): {e}")
                    result[sym] = {"symbol": sym, "last": None, "percentage": None}
        except Exception as e:
            print(f"Toplu BIST indirirken genel hata: {e}. Tek tek indiriliyor...")
            for sym in symbols:
                result[sym] = self.fetch_ticker(sym)
        return result

    def get_global_indices(self, indices: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """
        Küresel endekslerin (Nikkei, Hang Seng, S&P 500 futures) günlük durumlarını çeker.
        """
        result = {}
        for name, ticker_symbol in indices.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                df = ticker.history(period="5d")
                df = df.dropna(subset=['Close'])
                if len(df) >= 2:
                    last_val = df['Close'].iloc[-1]
                    prev_val = df['Close'].iloc[-2]
                    pct_change = ((last_val - prev_val) / prev_val) * 100 if prev_val != 0 else 0
                    result[name] = {
                        "ticker": ticker_symbol,
                        "last": self._safe_float(last_val),
                        "percentage": self._safe_float(pct_change)
                    }
                else:
                    result[name] = {"ticker": ticker_symbol, "last": None, "percentage": 0.0}
            except Exception as e:
                print(f"Global endeks çekme hatası ({name} - {ticker_symbol}): {e}")
                result[name] = {"ticker": ticker_symbol, "last": None, "percentage": 0.0}
        return result

    def get_market_news(self) -> List[Dict[str, Any]]:
        """
        Piyasa genel haberlerini ve ekonomi haberlerini RSS ve yfinance üzerinden çeker.
        """
        import yfinance as yf
        import feedparser
        news_list = []
        seen_titles = set()
        
        # 1. RSS Feed'den güncel ekonomi haberleri
        try:
            feed = feedparser.parse('https://www.trthaber.com/ekonomi_articles.rss')
            for entry in feed.entries[:5]:
                title = entry.title
                if title not in seen_titles:
                    seen_titles.add(title)
                    # Extract HH:MM if possible, else just use current time
                    time_str = time.strftime('%H:%M')
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        # Convert UTC to local conceptually, or just use string
                        import datetime
                        dt = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        # TR is UTC+3
                        dt = dt + datetime.timedelta(hours=3)
                        time_str = dt.strftime('%H:%M')
                    news_list.append({
                        "title": title,
                        "source": "TRT Ekonomi",
                        "link": entry.link,
                        "time": time_str
                    })
        except Exception as e:
            print(f"RSS haber çekme hatası: {e}")

        # 2. yfinance'dan global/yerel hisse haberleri
        news_tickers = ["THYAO.IS", "TUPRS.IS", "ES=F"]
        for sym in news_tickers:
            try:
                t = yf.Ticker(sym)
                ticker_news = t.news
                if ticker_news:
                    for item in ticker_news[:2]:
                        title = item.get('title')
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            pub_time = item.get('providerPublishTime', int(time.time()))
                            time_str = time.strftime('%H:%M', time.localtime(pub_time))
                            news_list.append({
                                "title": title,
                                "source": item.get('publisher', 'YF Feed'),
                                "link": item.get('link', '#'),
                                "time": time_str
                            })
            except Exception as e:
                print(f"Hisse haber çekme hatası ({sym}): {e}")
                
        # 3. Yeterli haber yoksa yedek senaryo
        if len(news_list) < 5:
            fallback_news = [
                {"title": "BIST 100 Endeksi küresel piyasalardaki temkinli duruşa paralel yatay seyre yöneldi", "source": "BISTASSIST Makro", "link": "#", "time": "09:30"},
                {"title": "Sanayi ve enerji sektörü hisselerinde kademeli alım ilgisi dikkat çekiyor", "source": "BISTASSIST Analiz", "link": "#", "time": "09:15"},
                {"title": "ABD S&P 500 vadeli kontratları Asya seansındaki satıcılı havayı takip ediyor", "source": "BISTASSIST Global", "link": "#", "time": "08:50"}
            ]
            for fn in fallback_news:
                if fn["title"] not in seen_titles:
                    news_list.append(fn)
                    seen_titles.add(fn["title"])
                    
        # Saatlere göre sırala
        return sorted(news_list, key=lambda x: x['time'], reverse=True)[:8]
