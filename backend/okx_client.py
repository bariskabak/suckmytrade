import ccxt
import pandas as pd
from typing import List, Dict, Any, Optional
from backend import config

class OKXClient:
    def __init__(self):
        # API anahtarları varsa OKX bağlantısını kimlik doğrulamalı başlat
        exchange_params = {
            'enableRateLimit': True,
        }
        
        if config.OKX_API_KEY and config.OKX_SECRET_KEY and config.OKX_PASSPHRASE:
            exchange_params.update({
                'apiKey': config.OKX_API_KEY,
                'secret': config.OKX_SECRET_KEY,
                'password': config.OKX_PASSPHRASE,
            })
        
        self.exchange = ccxt.okx(exchange_params)
        
        # Sandbox (Demo Trading) ayarı
        if config.OKX_USE_SANDBOX:
            self.exchange.set_sandbox_mode(True)
            
    def fetch_candles(self, symbol: str, timeframe: str = '15m', limit: int = 100) -> pd.DataFrame:
        """
        Belirtilen çift ve zaman dilimi için mum verilerini çeker ve DataFrame olarak döner.
        """
        try:
            # OKX çift formatı ccxt'te genellikle SOL/USDT şeklindedir
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            # Milisaniye cinsinden zaman damgasını okunabilir tarihe çevir
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Mum verisi çekilirken hata oluştu ({symbol}): {e}")
            # Hata durumunda boş DataFrame dön
            return pd.DataFrame()

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Anlık fiyat ve değişim bilgilerini çeker.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "percentage": ticker.get("percentage"),
                "baseVolume": ticker.get("baseVolume"),
                "quoteVolume": ticker.get("quoteVolume")
            }
        except Exception as e:
            print(f"Ticker çekilirken hata oluştu ({symbol}): {e}")
            return {"symbol": symbol, "last": None, "percentage": None}

    def fetch_tickers(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Aynı anda birden fazla çiftin anlık verilerini çeker.
        """
        try:
            tickers = self.exchange.fetch_tickers(symbols)
            result = {}
            for sym in symbols:
                if sym in tickers:
                    t = tickers[sym]
                    result[sym] = {
                        "symbol": sym,
                        "last": t.get("last"),
                        "high": t.get("high"),
                        "low": t.get("low"),
                        "percentage": t.get("percentage"),
                        "baseVolume": t.get("baseVolume")
                    }
            return result
        except Exception as e:
            print(f"Toplu ticker çekilirken hata oluştu: {e}")
            # Hata durumunda tek tek çekmeyi dene
            result = {}
            for sym in symbols:
                result[sym] = self.fetch_ticker(sym)
            return result

    def get_balance(self) -> Optional[Dict[str, Any]]:
        """
        Hesap bakiyesini çeker (API anahtarları tanımlı ise).
        """
        if not self.exchange.apiKey:
            return None
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            print(f"Bakiye çekilirken hata oluştu: {e}")
            return None

    def create_market_order(self, symbol: str, side: str, amount: float) -> Optional[Dict[str, Any]]:
        """
        Piyasa fiyatından alım veya satım emri gönderir.
        """
        if not self.exchange.apiKey:
            print("API anahtarları tanımlanmadığı için işlem simüle edildi.")
            return {
                "id": "mock-order-id",
                "symbol": symbol,
                "side": side,
                "type": "market",
                "amount": amount,
                "status": "closed",
                "info": "Simulated/Mock Order"
            }
        try:
            return self.exchange.create_market_order(symbol, side, amount)
        except Exception as e:
            print(f"Emir gönderilirken hata oluştu ({side} {symbol}): {e}")
            return None
