import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List
from backend import config

class MarketAnalyzer:
    @staticmethod
    def _safe_float(val, default=0.0):
        if val is None: return default
        import math
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except:
            return default

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Relative Strength Index (RSI) Hesaplama"""
        close = df['close']
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Exponential Moving Average base calculations for RSI
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        
        # Sıfıra bölünme hatasını engelle
        rs = np.where(avg_loss == 0, 0, avg_gain / avg_loss)
        rsi = 100 - (100 / (1 + rs))
        return pd.Series(rsi, index=df.index)

    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Moving Average Convergence Divergence (MACD) Hesaplama"""
        close = df['close']
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bantları Hesaplama"""
        close = df['close']
        basis = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper_band = basis + (std * num_std)
        lower_band = basis - (std * num_std)
        
        return upper_band, basis, lower_band

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """Hacim Ağırlıklı Ortalama Fiyat (VWAP) - Günlük Sıfırlanmalı veya Periyotluk"""
        # index'in datetime olduğunu varsayıyoruz. Günlük gruplama yapıp kümülatif hesaplayalım.
        # Eğer datetime yoksa düz kümülatif hesaplarız.
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        volume = df['volume']
        
        if pd.api.types.is_datetime64_any_dtype(df.index):
            dates = df.index.date
            cum_vol = volume.groupby(dates).cumsum()
            cum_vol_price = (typical_price * volume).groupby(dates).cumsum()
        else:
            cum_vol = volume.cumsum()
            cum_vol_price = (typical_price * volume).cumsum()
            
        vwap = cum_vol_price / cum_vol.replace(0, 1)
        return pd.Series(vwap, index=df.index)

    @staticmethod
    def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Money Flow Index (MFI) Hesaplama (Hacim ağırlıklı RSI)"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = typical_price * df['volume']
        
        positive_flow = np.where(typical_price > typical_price.shift(1), raw_money_flow, 0)
        negative_flow = np.where(typical_price < typical_price.shift(1), raw_money_flow, 0)
        
        positive_mf = pd.Series(positive_flow).rolling(window=period).sum()
        negative_mf = pd.Series(negative_flow).rolling(window=period).sum()
        
        # Sıfıra bölünme hatasını önle
        mfi_ratio = positive_mf / negative_mf.replace(0, 0.001)
        mfi = 100 - (100 / (1 + mfi_ratio))
        return pd.Series(mfi.values, index=df.index)

    @staticmethod
    def calculate_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Hacim Basit Hareketli Ortalaması"""
        return df['volume'].rolling(window=period).mean()

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range (ATR) Hesaplama (Volatilite)"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return pd.Series(atr, index=df.index)


    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average Directional Index (ADX) - Trend Gücü Hesaplama"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm = np.where((plus_dm > 0) & (plus_dm > -minus_dm), plus_dm, 0.0)
        minus_dm = np.where((minus_dm < 0) & (-minus_dm > plus_dm), -minus_dm, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        tr_smooth = tr.rolling(window=period).sum()
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=period).sum() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=period).sum() / tr_smooth)

        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1))
        adx = dx.rolling(window=period).mean()
        return pd.Series(adx, index=df.index)

    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """Supertrend Algoritması"""
        hl2 = (df['high'] + df['low']) / 2
        atr = MarketAnalyzer.calculate_atr(df, period)
        
        final_upperband = hl2 + (multiplier * atr)
        final_lowerband = hl2 - (multiplier * atr)
        
        st = np.zeros(len(df))
        d = np.ones(len(df))
        
        close = df['close'].values
        fub = final_upperband.to_numpy(copy=True)
        flb = final_lowerband.to_numpy(copy=True)
        
        for i in range(1, len(df)):
            if close[i] > fub[i-1]:
                d[i] = 1
            elif close[i] < flb[i-1]:
                d[i] = -1
            else:
                d[i] = d[i-1]
                
            if d[i] == 1:
                if flb[i] < flb[i-1]:
                    flb[i] = flb[i-1]
                st[i] = flb[i]
            else:
                if fub[i] > fub[i-1]:
                    fub[i] = fub[i-1]
                st[i] = fub[i]
                
        return pd.Series(st, index=df.index), pd.Series(d, index=df.index)

    @staticmethod
    def calculate_squeeze_momentum(df: pd.DataFrame, period: int = 20, mult: float = 2.0, kc_mult: float = 1.5) -> Tuple[pd.Series, pd.Series]:
        """Squeeze Momentum Indicator (TTM Squeeze uyarlaması) - Harika Trader İndikatörü"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Bollinger Bands
        m_avg = close.rolling(window=period).mean()
        m_std = close.rolling(window=period).std()
        bb_upper = m_avg + (mult * m_std)
        bb_lower = m_avg - (mult * m_std)
        
        # Keltner Channels
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        kc_upper = m_avg + (kc_mult * atr)
        kc_lower = m_avg - (kc_mult * atr)
        
        # Squeeze On Condition: Bollinger Bands Keltner'in içine girerse
        squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
        
        # Momentum (Fiyatın orta bantlardan uzaklaşma ivmesi)
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        avg = (highest_high + lowest_low) / 2.0
        
        delta = close - ((avg + m_avg) / 2.0)
        # Momentum'u pürüzsüzleştir
        momentum = delta.rolling(window=period).mean()
        
        return pd.Series(squeeze_on, index=df.index), pd.Series(momentum, index=df.index)

    @classmethod
    def calculate_golden_score(cls, df: pd.DataFrame) -> Tuple[float, str, List[str]]:
        """
        Otonom Trader için Özel Sentez: Golden Trend Puanı
        10 Üzerinden puanlama yapar. (Squeeze Momentum ile Güçlendirildi)
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0.0
        details = []
        
        adx_val = latest.get('ADX', 0)
        st_dir = latest.get('ST_dir', 0)
        macd_hist_cur = latest.get('MACD_hist', 0)
        macd_hist_prev = prev.get('MACD_hist', 0)
        close = latest['close']
        ema_9 = latest.get('EMA_9', 0)
        ema_21 = latest.get('EMA_21', 0)
        
        sqz_on = latest.get('Squeeze_On', False)
        sqz_mom_cur = latest.get('Squeeze_Mom', 0)
        sqz_mom_prev = prev.get('Squeeze_Mom', 0)
        
        # MEAN REVERSION (ORTALAMAYA DÖNÜŞ) KAZANMA MAKİNESİ
        # Amacımız yatay piyasada diplerden alıp, tepelerden satmak. (Scalping)
        
        rsi_val = latest.get('RSI', 50)
        mfi_val = latest.get('MFI', 50)
        vwap_val = latest.get('VWAP', close)
        bb_lower = latest.get('BB_lower', close)
        bb_upper = latest.get('BB_upper', close)
        
        # Trend yönünü sadece bir filtre olarak tutuyoruz, hard constraint yapmıyoruz.
        if close > ema_9:
            trend_direction = 1
        elif close < ema_9:
            trend_direction = -1
        else:
            trend_direction = 0

        # KURUMSAL KURAL 1: VWAP FİLTRESİ
        # Akıllı para VWAP'ın altında satıcı, üstünde alıcıdır.
        # Mean Reversion için: Fiyat VWAP'ın çok altındayken (İskonto) alınır, üstündeyken (Primli) satılır.
        is_discounted = close < vwap_val
        is_premium = close > vwap_val

        # AL SİNYALİ (LONG) - Aşırı Satım (Dipten Toplama)
        if close <= bb_lower * 1.002 and rsi_val < 35:
            # KURUMSAL KURAL 2: MFI Uyumsuzluğu / Hacim Onayı
            if mfi_val < 40 and is_discounted:
                score += 8.0
                details.append(f"🔥 Kurumsal Dip (VWAP Altı, RSI: {round(rsi_val,1)}, MFI: {round(mfi_val,1)})")
                if macd_hist_cur > macd_hist_prev:
                    score += 2.0
                    details.append("MACD Dönüş Onayı")
            else:
                details.append("Hacim Onaysız veya VWAP Üstü Dip - Pas Geçildi")
                
        # SAT SİNYALİ (SHORT) - Aşırı Alım (Tepeden Satış)
        elif close >= bb_upper * 0.998 and rsi_val > 65:
            if mfi_val > 60 and is_premium:
                score -= 8.0
                details.append(f"🧊 Kurumsal Tepe (VWAP Üstü, RSI: {round(rsi_val,1)}, MFI: {round(mfi_val,1)})")
                if macd_hist_cur < macd_hist_prev:
                    score -= 2.0
                    details.append("MACD Dönüş Onayı")
            else:
                details.append("Hacim Onaysız veya VWAP Altı Tepe - Pas Geçildi")
        else:
            details.append("Fiyat Orta Bantta (Bekleme Zonu)")

        # ADX Filtresi: Yatay piyasada Mean Reversion muhteşem çalışır. (ADX < 25)
        # Eğer ADX çok yüksekse (güçlü trend), terse işlem açmak tehlikelidir!
        if adx_val > 30 and score >= 8.0 and st_dir == -1:
            score -= 5.0 # Çok güçlü düşüş trendinde dipten almaya çalışma (Bıçak tutma)
            details.append("Güçlü Düşüş Trendi - Alım İptal")
        elif adx_val > 30 and score <= -8.0 and st_dir == 1:
            score += 5.0 # Çok güçlü yükseliş trendinde şortlama
            details.append("Güçlü Yükseliş Trendi - Satış İptal")

        # TREND FOLLOWING (TREND TAKİBİ) EKLENTİSİ
        # Piyasa sabahtan beri sürekli yükseliyorsa, Mean Reversion sinyal veremez. 
        # Bu yüzden güçlü trend (ADX > 20) varsa ve fiyatta moment varsa trend yönünde gir.
        if adx_val > 20 and st_dir == 1 and close > ema_9:
            if rsi_val < 75: # Henüz çok aşırı alıma gitmemişse
                score += 5.0
                details.append(f"🚀 Trend Takibi (AL): ST Pozitif, ADX: {round(adx_val,1)}")
        elif adx_val > 20 and st_dir == -1 and close < ema_9:
            if rsi_val > 25:
                score -= 5.0
                details.append(f"📉 Trend Takibi (SAT): ST Negatif, ADX: {round(adx_val,1)}")

        # Sinyal Yorumu
        if score >= 8.0:
            signal = "GUCLU_AL"
        elif score >= 5.0:
            signal = "AL"
        elif score <= -8.0:
            signal = "GUCLU_SAT"
        elif score <= -5.0:
            signal = "SAT"
        else:
            signal = "NOTR"

        return score, signal, details

    @classmethod
    def analyze(cls, df: pd.DataFrame, global_sentiment_score: float = 0.0) -> Dict[str, Any]:
        """
        Otonom Trader Faz 5: Golden Trend Sentezi
        """
        if df.empty or len(df) < 50:
            return {
                "signal": "Yetersiz Veri",
                "score": 0,
                "indicators": {}
            }
            
        # Göstergelerin Hesaplanması
        df['ATR'] = cls.calculate_atr(df)
        df['ADX'] = cls.calculate_adx(df, 14)
        df['ST_line'], df['ST_dir'] = cls.calculate_supertrend(df, 10, 3.0)
        df['RSI'] = cls.calculate_rsi(df, 14)
        df['MFI'] = cls.calculate_mfi(df, 14)
        df['VWAP'] = cls.calculate_vwap(df)
        df['BB_upper'], df['BB_mid'], df['BB_lower'] = cls.calculate_bollinger_bands(df, 20, 2.0)
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['MACD_line'], df['MACD_signal'], df['MACD_hist'] = cls.calculate_macd(
            df, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
        )
        
        # Harika Trader İndikatörü
        df['Squeeze_On'], df['Squeeze_Mom'] = cls.calculate_squeeze_momentum(df)
        
        # Golden Score Hesaplama
        score, signal, details = cls.calculate_golden_score(df)
        
        # Küresel Duyarlılık Opsiyonel Katkı
        if global_sentiment_score != 0.0:
            if signal == "GUCLU_AL" and global_sentiment_score > 0:
                score += global_sentiment_score
            elif signal == "GUCLU_SAT" and global_sentiment_score < 0:
                score -= global_sentiment_score

        latest = df.iloc[-1]
        
        return {
            "signal": signal,
            "score": round(cls._safe_float(score), 2),
            "details": details,
            "price": round(cls._safe_float(latest.get('close', 0.0)), 6),
            "indicators": {
                "rsi": round(cls._safe_float(latest.get('RSI', 0.0)), 2),
                "adx": round(cls._safe_float(latest.get('ADX', 0.0)), 2),
                "supertrend": {
                    "value": round(cls._safe_float(latest.get('ST_line', 0.0)), 6),
                    "direction": int(cls._safe_float(latest.get('ST_dir', 0.0)))
                },
                "macd": {
                    "line": round(cls._safe_float(latest.get('MACD_line', 0.0)), 6),
                    "signal": round(cls._safe_float(latest.get('MACD_signal', 0.0)), 6),
                    "hist": round(cls._safe_float(latest.get('MACD_hist', 0.0)), 6)
                },
                "bollinger": {
                    "upper": round(cls._safe_float(latest.get('BB_upper', 0.0)), 6),
                    "lower": round(cls._safe_float(latest.get('BB_lower', 0.0)), 6)
                },
                "ema": {
                    "fast": round(cls._safe_float(latest.get('EMA_9', 0.0)), 6),
                    "slow": round(cls._safe_float(latest.get('EMA_21', 0.0)), 6),
                    "trend": round(cls._safe_float(latest.get('EMA_trend', 0.0)), 6)
                },
                "volatility": {
                    "atr": round(cls._safe_float(latest.get('ATR', 0.0)), 6)
                }
            }
        }
