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
        
        # BUG FIX: avg_loss == 0 olduğunda RSI = 100 olmalı (sürekli yükseliş)
        # Eski hatalı kod: rs = np.where(avg_loss == 0, 0, ...) → RSI = 0 döndürüyordu
        rs = np.where(avg_loss == 0, 100.0, avg_gain / avg_loss)
        rsi = np.where(avg_loss == 0, 100.0, 100 - (100 / (1 + rs)))
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
        
        # BUG FIX: Index hizalaması düzeltildi - orijinal index korunuyor
        positive_flow = pd.Series(
            np.where(typical_price > typical_price.shift(1), raw_money_flow, 0),
            index=df.index
        )
        negative_flow = pd.Series(
            np.where(typical_price < typical_price.shift(1), raw_money_flow, 0),
            index=df.index
        )
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
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

    @staticmethod
    def detect_rsi_divergence(df: pd.DataFrame, lookback: int = 5) -> Tuple[bool, bool]:
        """
        RSI Diverjans Tespiti
        Returns: (bullish_divergence, bearish_divergence)
        - Bullish: Fiyat yeni dip yapar ama RSI daha yüksek dip yapar → yukarı dönüş sinyali
        - Bearish: Fiyat yeni tepe yapar ama RSI daha düşük tepe yapar → aşağı dönüş sinyali
        """
        if len(df) < lookback + 2:
            return False, False
            
        close = df['close'].values
        rsi = df['RSI'].values
        
        recent_close = close[-lookback:]
        recent_rsi = rsi[-lookback:]
        older_close = close[-(lookback*2):-lookback]
        older_rsi = rsi[-(lookback*2):-lookback]
        
        if len(older_close) < lookback:
            return False, False
        
        # Bullish Divergence: Fiyat yeni dip, RSI yükselen dip
        bullish = False
        if min(recent_close) < min(older_close) and min(recent_rsi) > min(older_rsi):
            bullish = True
            
        # Bearish Divergence: Fiyat yeni tepe, RSI düşen tepe
        bearish = False
        if max(recent_close) > max(older_close) and max(recent_rsi) < max(older_rsi):
            bearish = True
            
        return bullish, bearish

    @classmethod
    def calculate_golden_score(cls, df: pd.DataFrame) -> Tuple[float, str, List[str], float, str]:
        """
        Otonom Trader için Özel Sentez: Golden Trend Puanı v2
        Squeeze Momentum, Hacim Filtresi, RSI Diverjans ve EMA 200 ile güçlendirildi.
        
        Returns: (score, signal, details, confidence_pct, signal_mode)
        - signal_mode: "MEAN_REVERSION" veya "TREND_FOLLOWING" — SL/TP stratejisini belirler
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0.0
        details = []
        confirmations = 0  # Aynı yönde onay veren gösterge sayısı
        total_checks = 0   # Toplam kontrol edilen gösterge sayısı
        signal_mode = "MEAN_REVERSION"  # Varsayılan strateji
        
        adx_val = cls._safe_float(latest.get('ADX', 0))
        st_dir = cls._safe_float(latest.get('ST_dir', 0))
        macd_hist_cur = cls._safe_float(latest.get('MACD_hist', 0))
        macd_hist_prev = cls._safe_float(prev.get('MACD_hist', 0))
        close = cls._safe_float(latest['close'])
        ema_9 = cls._safe_float(latest.get('EMA_9', 0))
        ema_21 = cls._safe_float(latest.get('EMA_21', 0))
        ema_200 = cls._safe_float(latest.get('EMA_200', 0))
        
        sqz_on = latest.get('Squeeze_On', False)
        sqz_mom_cur = cls._safe_float(latest.get('Squeeze_Mom', 0))
        sqz_mom_prev = cls._safe_float(prev.get('Squeeze_Mom', 0))
        
        rsi_val = cls._safe_float(latest.get('RSI', 50))
        mfi_val = cls._safe_float(latest.get('MFI', 50))
        vwap_val = cls._safe_float(latest.get('VWAP', close))
        bb_lower = cls._safe_float(latest.get('BB_lower', close))
        bb_upper = cls._safe_float(latest.get('BB_upper', close))
        
        # Hacim analizi
        vol_current = cls._safe_float(latest.get('volume', 0))
        vol_sma = cls._safe_float(latest.get('Vol_SMA', 1))
        vol_ratio = vol_current / vol_sma if vol_sma > 0 else 1.0
        
        # Diverjans tespiti
        bullish_div, bearish_div = cls.detect_rsi_divergence(df)
        
        # ═══════════════════════════════════════════════
        # EMA 200 ANA TREND FİLTRESİ
        # ═══════════════════════════════════════════════
        above_ema200 = close > ema_200 if ema_200 > 0 else True
        below_ema200 = close < ema_200 if ema_200 > 0 else True
        
        if ema_200 > 0:
            ema200_dist_pct = ((close - ema_200) / ema_200) * 100
        else:
            ema200_dist_pct = 0
        
        # ═══════════════════════════════════════════════
        # VWAP FİLTRESİ
        # ═══════════════════════════════════════════════
        is_discounted = close < vwap_val
        is_premium = close > vwap_val

        # ═══════════════════════════════════════════════
        # BÖLÜM 1: MEAN REVERSION (ORTALAMAYA DÖNÜŞ)
        # Yatay piyasada diplerden alıp, tepelerden satmak
        # ═══════════════════════════════════════════════
        
        # AL SİNYALİ (LONG) - Aşırı Satım (Dipten Toplama)
        if close <= bb_lower * 1.005 and rsi_val < 38:
            total_checks += 4
            
            # MFI ve VWAP onayı
            if mfi_val < 45:
                confirmations += 1
            if is_discounted:
                confirmations += 1
            # MACD dönüş onayı    
            if macd_hist_cur > macd_hist_prev:
                confirmations += 1
                details.append("MACD Dönüş Onayı ✓")
            # RSI Diverjans bonusu
            if bullish_div:
                confirmations += 1
                score += 2.0
                details.append("📊 RSI Bullish Diverjans ✓")
                
            if confirmations >= 2:
                score += 8.0
                details.append(f"🔥 Kurumsal Dip (RSI: {round(rsi_val,1)}, MFI: {round(mfi_val,1)}, Hacim: x{round(vol_ratio,1)})")
                signal_mode = "MEAN_REVERSION"
            else:
                details.append(f"⚠️ Dip sinyali ama yetersiz onay ({confirmations}/4)")
                
        # SAT SİNYALİ (SHORT) - Aşırı Alım (Tepeden Satış)
        elif close >= bb_upper * 0.995 and rsi_val > 62:
            total_checks += 4
            
            if mfi_val > 55:
                confirmations += 1
            if is_premium:
                confirmations += 1
            if macd_hist_cur < macd_hist_prev:
                confirmations += 1
                details.append("MACD Dönüş Onayı ✓")
            if bearish_div:
                confirmations += 1
                score -= 2.0
                details.append("📊 RSI Bearish Diverjans ✓")
                
            if confirmations >= 2:
                score -= 8.0
                details.append(f"🧊 Kurumsal Tepe (RSI: {round(rsi_val,1)}, MFI: {round(mfi_val,1)}, Hacim: x{round(vol_ratio,1)})")
                signal_mode = "MEAN_REVERSION"
            else:
                details.append(f"⚠️ Tepe sinyali ama yetersiz onay ({confirmations}/4)")
        else:
            details.append("Fiyat Orta Bantta (Bekleme Zonu)")

        # ═══════════════════════════════════════════════
        # BÖLÜM 2: ADX BAĞLAMA GÖRMELİ FİLTRE
        # Güçlü trendde Mean Reversion'a karşı işlem tehlikeli
        # ═══════════════════════════════════════════════
        if adx_val > 30 and score >= 8.0 and st_dir == -1:
            score -= 5.0
            details.append("⚠️ Güçlü Düşüş Trendi - Dip Alımı Riskli (Bıçak Tutma)")
        elif adx_val > 30 and score <= -8.0 and st_dir == 1:
            score += 5.0
            details.append("⚠️ Güçlü Yükseliş Trendi - Tepe Satışı Riskli")

        # ═══════════════════════════════════════════════
        # BÖLÜM 3: TREND TAKİBİ (Sıkılaştırılmış)
        # Sadece GERÇEK güçlü trendlerde sinyal üret
        # Koşullar: ADX > 28 + EMA Golden/Death Cross + Supertrend onayı
        # ═══════════════════════════════════════════════
        if score == 0:  # Sadece Mean Reversion sinyal vermemişse trend takibine bak
            total_checks += 5
            
            # TREND AL: ADX güçlü + ST pozitif + EMA Golden Cross + EMA 200 üstü
            trend_al_conditions = (
                adx_val > 28 and 
                st_dir == 1 and 
                ema_9 > ema_21 and   # Golden Cross
                close > ema_9 and
                rsi_val < 72
            )
            
            # TREND SAT: ADX güçlü + ST negatif + EMA Death Cross + EMA 200 altı
            trend_sat_conditions = (
                adx_val > 28 and 
                st_dir == -1 and 
                ema_9 < ema_21 and   # Death Cross
                close < ema_9 and
                rsi_val > 28
            )
            
            if trend_al_conditions:
                trend_confirmations = 0
                
                if above_ema200:
                    trend_confirmations += 1
                if macd_hist_cur > 0:
                    trend_confirmations += 1
                if macd_hist_cur > macd_hist_prev:  # MACD ivme artıyor
                    trend_confirmations += 1
                if mfi_val > 40:  # Para girişi var
                    trend_confirmations += 1
                if vol_ratio > 0.8:  # Hacim çok düşük değil
                    trend_confirmations += 1
                    
                confirmations = trend_confirmations
                    
                if trend_confirmations >= 3:
                    score += 5.0
                    signal_mode = "TREND_FOLLOWING"
                    details.append(f"🚀 Trend Takibi (AL): ADX {round(adx_val,1)}, EMA Cross ✓, ST↑ ({trend_confirmations}/5 onay)")
                    
                    # EMA 200 üstünde ek bonus
                    if above_ema200 and ema200_dist_pct > 2:
                        score += 1.5
                        details.append(f"📈 EMA 200 üstü (+{round(ema200_dist_pct,1)}%) - Trend güçlü")
                        
            elif trend_sat_conditions:
                trend_confirmations = 0
                
                if below_ema200:
                    trend_confirmations += 1
                if macd_hist_cur < 0:
                    trend_confirmations += 1
                if macd_hist_cur < macd_hist_prev:
                    trend_confirmations += 1
                if mfi_val < 60:
                    trend_confirmations += 1
                if vol_ratio > 0.8:
                    trend_confirmations += 1
                    
                confirmations = trend_confirmations
                    
                if trend_confirmations >= 3:
                    score -= 5.0
                    signal_mode = "TREND_FOLLOWING"
                    details.append(f"📉 Trend Takibi (SAT): ADX {round(adx_val,1)}, EMA Cross ✓, ST↓ ({trend_confirmations}/5 onay)")
                    
                    if below_ema200 and ema200_dist_pct < -2:
                        score -= 1.5
                        details.append(f"📉 EMA 200 altı ({round(ema200_dist_pct,1)}%) - Düşüş güçlü")

        # ═══════════════════════════════════════════════
        # BÖLÜM 4: SQUEEZE MOMENTUM (Volatilite Patlaması)
        # Sıkışma açılırken momentum yönü sinyali güçlendirir
        # ═══════════════════════════════════════════════
        prev_sqz_on = prev.get('Squeeze_On', False)
        
        # Squeeze sıkışması açılıyor (ON → OFF geçişi = patlama anı)
        if prev_sqz_on and not sqz_on:
            if sqz_mom_cur > 0 and sqz_mom_cur > sqz_mom_prev:
                score += 2.0
                details.append("💥 Squeeze Patlaması: Yukarı Momentum")
            elif sqz_mom_cur < 0 and sqz_mom_cur < sqz_mom_prev:
                score -= 2.0
                details.append("💥 Squeeze Patlaması: Aşağı Momentum")
                
        # Squeeze hala sıkışık → yakında patlama olacak (bilgilendirme)
        elif sqz_on:
            if sqz_mom_cur > sqz_mom_prev:
                details.append("🔸 Squeeze Sıkışık - Yukarı Momentum Birikiyor")
            elif sqz_mom_cur < sqz_mom_prev:
                details.append("🔸 Squeeze Sıkışık - Aşağı Momentum Birikiyor")
            else:
                details.append("🔸 Squeeze Sıkışık - Patlama Yakın")

        # ═══════════════════════════════════════════════
        # BÖLÜM 5: HACİM FİLTRESİ
        # Düşük hacimde sinyal gücünü düşür, yüksek hacimde güçlendir
        # ═══════════════════════════════════════════════
        if abs(score) >= 5.0:
            if vol_ratio < 0.5:
                # Çok düşük hacim — sahte kırılım riski
                old_score = score
                score *= 0.6  # Sinyali %40 zayıflat
                details.append(f"⚠️ Düşük Hacim Uyarısı (x{round(vol_ratio,1)}) - Sinyal zayıflatıldı")
            elif vol_ratio > 2.0:
                # Çok yüksek hacim — kurumsal hareket onayı
                score *= 1.15  # Sinyali %15 güçlendir
                details.append(f"✅ Yüksek Hacim Onayı (x{round(vol_ratio,1)})")
            elif vol_ratio > 1.3:
                details.append(f"✅ Orta-Yüksek Hacim (x{round(vol_ratio,1)})")

        # ═══════════════════════════════════════════════
        # BÖLÜM 6: EMA 200 KORUMA KALKANI
        # Ana trende karşı işleme ceza
        # ═══════════════════════════════════════════════
        if ema_200 > 0:
            if score > 0 and below_ema200 and signal_mode == "TREND_FOLLOWING":
                score *= 0.6
                details.append("⚠️ EMA 200 altında AL - Sinyal zayıflatıldı")
            elif score < 0 and above_ema200 and signal_mode == "TREND_FOLLOWING":
                score *= 0.6
                details.append("⚠️ EMA 200 üstünde SAT - Sinyal zayıflatıldı")

        # ═══════════════════════════════════════════════
        # SİNYAL YORUMU & GÜVENİLİRLİK
        # ═══════════════════════════════════════════════
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
            
        # Güvenilirlik yüzdesi hesaplama
        if total_checks > 0:
            confidence_pct = round((confirmations / total_checks) * 100, 0)
        else:
            confidence_pct = 0.0
            
        # Minimum güvenilirlik
        if signal != "NOTR":
            confidence_pct = max(confidence_pct, 40.0)  # En az %40

        return score, signal, details, confidence_pct, signal_mode

    @classmethod
    def calculate_gap_potential(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Kapanış-Açılış (Karanlık Oda / Gap) Stratejisi için potansiyel hesaplar.
        0-100 arası bir skor döner.
        """
        if len(df) < 20:
            return {"score": 0, "details": []}
            
        latest = df.iloc[-1]
        
        close_p = cls._safe_float(latest['close'])
        high_p = cls._safe_float(latest['high'])
        low_p = cls._safe_float(latest['low'])
        open_p = cls._safe_float(latest['open'])
        vol = cls._safe_float(latest['volume'])
        
        # Eğer henüz hacim SMA hesaplanmamışsa
        if 'Vol_SMA' not in df.columns:
            df['Vol_SMA'] = cls.calculate_volume_sma(df, 20)
        vol_sma = cls._safe_float(latest.get('Vol_SMA', 1.0))
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        
        score = 0
        details = []
        
        # 1. Kapanışın günün en yükseğine yakınlığı (Max 40 Puan)
        day_range = high_p - low_p
        if day_range > 0:
            close_to_high_ratio = (close_p - low_p) / day_range
            # %90'ın üzerindeyse tam puan
            if close_to_high_ratio >= 0.90:
                score += 40
                details.append(f"Zirveye Yakın Kapanış (Zirveye uzaklık: %{round((high_p-close_p)/high_p*100, 2)})")
            elif close_to_high_ratio >= 0.75:
                score += 20
                details.append(f"Güçlü Kapanış")
        
        # 2. Hacim İvmesi (Max 25 Puan)
        if vol_ratio >= 2.0:
            score += 25
            details.append(f"Çok Yüksek Hacim (x{round(vol_ratio, 1)})")
        elif vol_ratio >= 1.3:
            score += 15
            details.append(f"Artan Hacim İvmesi")
            
        # 3. Trend Gücü (Max 20 Puan)
        rsi = cls._safe_float(latest.get('RSI', 50))
        if rsi >= 60 and rsi <= 80:  # Güçlü ama aşırı alınmamış
            score += 20
            details.append("RSI İvmesi Pozitif")
        elif rsi > 80:
            score += 10
            details.append("RSI Aşırı Alımda (Riskli)")
            
        # 4. Tavan/Marj Kontrolü (BIST 100/30 limitleri %10)
        # Günlük yüzde değişim
        pct_change = ((close_p - open_p) / open_p) * 100 if open_p > 0 else 0
        if pct_change >= 8.5 and pct_change < 10.0:
            score += 15
            details.append(f"Tavana Çok Yakın (%{round(pct_change, 1)})")
        elif pct_change >= 4.0:
            score += 5
            
        # Güçlü düşüş/kırmızı mum ise skoru sıfırla
        if close_p < open_p:
            score = 0
            
        return {
            "score": min(100, score),
            "details": details,
            "close_ratio": round(close_to_high_ratio, 2) if day_range > 0 else 0,
            "vol_ratio": round(vol_ratio, 2),
            "pct_change": round(pct_change, 2)
        }

    @classmethod
    def analyze(cls, df: pd.DataFrame, global_sentiment_score: float = 0.0) -> Dict[str, Any]:
        """
        Otonom Trader Faz 6: Golden Trend Sentezi v2
        EMA 200, Squeeze Momentum, Hacim Filtresi, RSI Diverjans ve Güvenilirlik ile güçlendirildi.
        """
        if df.empty or len(df) < 50:
            return {
                "signal": "Yetersiz Veri",
                "score": 0,
                "confidence": 0,
                "signal_mode": "NONE",
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
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['MACD_line'], df['MACD_signal'], df['MACD_hist'] = cls.calculate_macd(
            df, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
        )
        
        # Harika Trader İndikatörü
        df['Squeeze_On'], df['Squeeze_Mom'] = cls.calculate_squeeze_momentum(df)
        
        # Hacim SMA (artık gerçekten kullanılıyor)
        df['Vol_SMA'] = cls.calculate_volume_sma(df, 20)
        
        # Golden Score v2 Hesaplama
        score, signal, details, confidence, signal_mode = cls.calculate_golden_score(df)
        
        # Küresel Duyarlılık Katkısı (Geliştirilmiş)
        if global_sentiment_score != 0.0:
            # GSS artık sadece GUCLU sinyallerde değil, tüm sinyallerde etkili
            if score > 0 and global_sentiment_score > 0:
                gss_bonus = min(global_sentiment_score * 0.3, 1.5)
                score += gss_bonus
            elif score < 0 and global_sentiment_score < 0:
                gss_bonus = min(abs(global_sentiment_score) * 0.3, 1.5)
                score -= gss_bonus
            # Ters yönlü GSS → uyarı
            elif score > 0 and global_sentiment_score < -2.0:
                details.append(f"⚠️ Küresel Sentiment Negatif (GSS: {round(global_sentiment_score,1)}) - Dikkat")
            elif score < 0 and global_sentiment_score > 2.0:
                details.append(f"⚠️ Küresel Sentiment Pozitif (GSS: {round(global_sentiment_score,1)}) - Dikkat")

        latest = df.iloc[-1]
        
        return {
            "signal": signal,
            "score": round(cls._safe_float(score), 2),
            "confidence": confidence,
            "signal_mode": signal_mode,
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
                    "trend": round(cls._safe_float(latest.get('EMA_200', 0.0)), 6)
                },
                "volatility": {
                    "atr": round(cls._safe_float(latest.get('ATR', 0.0)), 6)
                },
                "volume": {
                    "current": round(cls._safe_float(vol_current), 0) if 'vol_current' in dir() else 0,
                    "sma": round(cls._safe_float(latest.get('Vol_SMA', 0.0)), 0),
                    "ratio": round(cls._safe_float(latest.get('volume', 0) / max(latest.get('Vol_SMA', 1), 1)), 2)
                },
                "squeeze": {
                    "on": bool(latest.get('Squeeze_On', False)),
                    "momentum": round(cls._safe_float(latest.get('Squeeze_Mom', 0.0)), 6)
                }
            }
        }
