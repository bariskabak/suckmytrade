import pandas as pd
from typing import Dict, Any, List
from backend.analyzer import MarketAnalyzer

class BacktestSimulator:
    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0, leverage: float = 1.0, 
                 maker_fee: float = 0.0002, taker_fee: float = 0.0005, maintenance_margin: float = 0.005,
                 risk_per_trade: float = 0.10, days_back: int = 30):
        self.df = df
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.maintenance_margin = maintenance_margin
        self.risk_per_trade = risk_per_trade
        self.days_back = days_back
        
        self.position = None  # None, 'LONG', 'SHORT'
        self.entry_price = 0.0
        self.position_size = 0.0
        self.margin_used = 0.0
        
        # Risk & Çıkış Stratejisi
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0
        self.partial_tp_price = 0.0     # %50 satılacak olan hedef (Scale-out)
        self.partial_tp_done = False    # Kısmi satış yapıldı mı?
        self.trailing_activation = 0.0 # Trailing stop'u tetikleyecek fiyat seviyesi
        self.trailing_distance = 0.0   # Fiyatı ne kadar mesafeden takip edecek
        
        self.trades = []
        self.debug_logs = []
        self.daily_equity = {}
        
    def run(self) -> Dict[str, Any]:
        """Backtesti çalıştırır"""
        if self.df is None or len(self.df) < 50:
            return {"error": "Yetersiz veri (Simülasyon için en az 50 mum gerekli)"}
            
        window_size = 50
        
        daily_start_balance = self.initial_balance
        last_traded_date = None
        trading_halted_today = False
        
        for i in range(window_size, len(self.df)):
            current_idx = self.df.index[i]
            row = self.df.iloc[i]
            current_price = row['close']
            high_price = row['high']
            low_price = row['low']
            
            current_date = current_idx.date() if hasattr(current_idx, 'date') else None
            
            # Gün değişimi kontrolü
            if current_date != last_traded_date:
                daily_start_balance = self.balance
                last_traded_date = current_date
                trading_halted_today = False
                
            # KURUMSAL KURAL 3: Günlük Şalter (Max Drawdown Koruması)
            # Eğer o gün kasanın %3'ünü kaybettiysek, makine fişi çeker! (Trading Halt)
            if self.balance < daily_start_balance * 0.97:
                if not trading_halted_today:
                    self.debug_logs.append(f"🛑 GÜNLÜK ŞALTER İNDİ: %3 Max Drawdown aşıldı! Tarih: {current_date}")
                    trading_halted_today = True
                    
            # 1. Likidasyon Kontrolü
            if self.position:
                if self.check_liquidation(current_price):
                    self.close_position(current_price, current_idx, reason="LIQUIDATION")
                    if self.balance <= 0:
                        break # Bakiye bitti
                        
                # DAY TRADING KORUMASI: Gecelik boşluk (Gap) riskine karşı 17:45'te kapat
                elif hasattr(current_idx, 'hour') and current_idx.hour == 17 and current_idx.minute >= 45:
                    self.close_position(current_price, current_idx, reason="END_OF_DAY")
                    continue
                        
            # 2. Stop-Loss & Take-Profit ve Trailing Stop Kontrolleri
            if self.position:
                # Güncel mumun ekstrem uçlarına göre stop/tp kontrolü
                if self.position == 'LONG':
                    # Akıllı Kâr Koruma Kalkanı (Maliyete Çek)
                    if high_price >= self.partial_tp_price and self.partial_tp_price > 0 and not self.partial_tp_done:
                        # Kârın belirli bir seviyesine ulaştık, pozisyonu kapatma ama stop'u maliyete çek.
                        # VİOP'ta komisyonu da kurtaracak şekilde ufak bir buffer bırakılır.
                        buffer = self.entry_price * 0.001
                        if self.stop_loss_price < self.entry_price + buffer:
                            self.stop_loss_price = self.entry_price + buffer
                        self.partial_tp_done = True
                            
                    # Trailing Stop Güncellemesi (Sadece kâra geçince ve geniş mesafeyle)
                    if high_price >= self.trailing_activation and self.trailing_activation > 0:
                        new_sl = high_price - self.trailing_distance
                        if new_sl > self.stop_loss_price:
                            self.stop_loss_price = new_sl
                            
                    # Kâr Al (Take Profit)
                    if high_price >= self.take_profit_price and self.take_profit_price > 0:
                        self.close_position(self.take_profit_price, current_idx, reason="TAKE_PROFIT")
                        continue
                    # Zarar Kes (Stop Loss)
                    elif low_price <= self.stop_loss_price and self.stop_loss_price > 0:
                        self.close_position(self.stop_loss_price, current_idx, reason="STOP_LOSS")
                        continue
                        
                elif self.position == 'SHORT':
                    # Akıllı Kâr Koruma Kalkanı (Maliyete Çek)
                    if low_price <= self.partial_tp_price and self.partial_tp_price > 0 and not self.partial_tp_done:
                        buffer = self.entry_price * 0.001
                        if self.stop_loss_price > self.entry_price - buffer or self.stop_loss_price == 0:
                            self.stop_loss_price = self.entry_price - buffer
                        self.partial_tp_done = True
                            
                    # Trailing Stop Güncellemesi
                    if low_price <= self.trailing_activation and self.trailing_activation > 0:
                        new_sl = low_price + self.trailing_distance
                        if new_sl < self.stop_loss_price or self.stop_loss_price == 0:
                            self.stop_loss_price = new_sl
                            
                    # Kâr Al
                    if low_price <= self.take_profit_price and self.take_profit_price > 0:
                        self.close_position(self.take_profit_price, current_idx, reason="TAKE_PROFIT")
                        continue
                    # Zarar Kes
                    elif high_price >= self.stop_loss_price and self.stop_loss_price > 0:
                        self.close_position(self.stop_loss_price, current_idx, reason="STOP_LOSS")
                        continue
                        
                # POZİSYON KORUMA: Pozisyon hala açıksa (Yukarıda kapanmadıysa),
                # sinyal aramaya girme. "Gelecek Görüyorsan Bekle" mantığının nihai garantisi.
                if self.position:
                    continue

            # Eğer bugün şalter indiyse (Drawdown), yeni pozisyon açma!
            if trading_halted_today:
                continue
                
            # KURUMSAL KURAL 4: Amatör Saati (Amateur Hour) Tuzağı
            # Sabah ilk 15 dakika (BIST için 09:55 - 10:15) piyasa yönü belirsizdir, spread açıktır.
            # O saatlerde algoritmik işlem yasaktır!
            is_amateur_hour = False
            if hasattr(current_idx, 'hour') and hasattr(current_idx, 'minute'):
                if current_idx.hour == 9 or (current_idx.hour == 10 and current_idx.minute <= 15):
                    is_amateur_hour = True
            
            if is_amateur_hour:
                continue

            # Alt küme (sub_df) ile analiz yap (Lookback window)
            sub_df = self.df.iloc[i - window_size : i + 1].copy()
            analysis = MarketAnalyzer.analyze(sub_df)
            signal = analysis.get('signal', 'NOTR')
            
            # ATR verisini al
            indicators = analysis.get('indicators', {})
            atr = indicators.get('volatility', {}).get('atr', 0)
            
            # Signal mode (TREND_FOLLOWING veya MEAN_REVERSION)
            signal_mode = analysis.get('signal_mode', 'MEAN_REVERSION')
            
            # Otonom Trade & Gelecek Görme (Golden Score)
            # Skor >= 5 (AL/SAT ve GUCLU_AL/GUCLU_SAT) sinyallerinde işlem açılır.
            # Zıt sinyal geldiğinde, eğer sinyal şiddeti (Skor) 9'dan küçükse pozisyonu KORU.
            score = analysis.get('score', 0.0)
            if score >= 4.0 or score <= -4.0:
                self.debug_logs.append(f"Idx {i}: Score={score}, Sig={signal}, Mode={signal_mode}, Details={analysis.get('details')}")
                
            if signal in ("GUCLU_AL", "AL"):
                if self.position == 'SHORT':
                    if score >= 9.0: 
                        self.close_position(current_price, current_idx, reason="STRONG_REVERSAL")
                    else:
                        pass # Zayıf dönüş sinyallerini yoksay, trendi ve hedefi koru
                        
                if self.position is None:
                    self.open_position('LONG', current_price, current_idx, atr, signal_mode=signal_mode)
            
            elif signal in ("GUCLU_SAT", "SAT"):
                if self.position == 'LONG':
                    if score <= -9.0:
                        self.close_position(current_price, current_idx, reason="STRONG_REVERSAL")
                    else:
                        pass # Trendi ve hedefi koru
                        
                if self.position is None:
                    self.open_position('SHORT', current_price, current_idx, atr, signal_mode=signal_mode)
                    
            # Günlük Döküm (Kapanış)
            try:
                date_str = str(row['datetime']).split(' ')[0]
                open_pnl = 0.0
                if self.position:
                    if self.position == 'LONG':
                        open_pnl = (current_price - self.entry_price) * self.position_size
                    else:
                        open_pnl = (self.entry_price - current_price) * self.position_size
                self.daily_equity[date_str] = {
                    "balance": round(self.balance, 2),
                    "open_pnl": round(open_pnl, 2),
                    "equity": round(self.balance + open_pnl, 2)
                }
            except:
                pass

        # Döngü bittiğinde açık pozisyon varsa son fiyattan kapat
        if self.position:
            last_price = self.df.iloc[-1]['close']
            last_idx = self.df.index[-1]
            self.close_position(last_price, last_idx, reason="END_OF_TEST")
            
        return self.generate_report()

    def open_position(self, side: str, price: float, timestamp: Any, atr: float = 0.0, signal_mode: str = 'MEAN_REVERSION'):
        # 1. STOP MESAFESİ (ATR Bazlı) - Signal Mode'a göre ayarlanır
        # TREND_FOLLOWING: Geniş SL/TP (trendi yakalamak için nefes alanı)
        # MEAN_REVERSION: Sıkı SL/TP (ortalamaya dönüşte vur-kaç)
        if atr and atr > 0:
            if signal_mode == 'TREND_FOLLOWING':
                stop_distance = atr * 3.0  # Trende nefes alanı bırak
                tp_distance = atr * 4.0    # Trend hedefi geniş tut
            else:
                stop_distance = atr * 2.0  # Bıçak tutmaya karşı sıkı stop
                tp_distance = atr * 2.5    # Çok hızlı kâr al (Vur-kaç)
        else:
            # Fallback: ATR hesaplanamazsa sabit %1.0
            stop_distance = price * 0.01
            tp_distance = price * 0.015

        # 2. POSITION SIZING (Kasa Riski Yönetimi)
        # R = Tüm kasanın %X'i (Örn: 100.000 TL * %3 = 3.000 TL maksimum göze alınan zarar)
        max_loss_amount = self.balance * self.risk_per_trade
        
        # Alınacak Adet/Lot (Position Size) = Maksimum Zarar / Birim Başına Düşüş (Stop Mesafesi)
        # Eğer stop olursak sadece "max_loss_amount" kadar kaybederiz.
        raw_position_size = max_loss_amount / stop_distance
        
        # Toplam Büyüklük (Notional Value) = Lot * Fiyat
        desired_notional = raw_position_size * price
        
        # DİNAMİK KALDIRAÇ YÖNETİMİ
        # Eğer istenilen büyüklüğü almak için kasamız + API'den gelen kaldıraç yetmiyorsa
        # Sistemi patlatmamak için kaldıracı sadece yetecek kadar dinamik artırırız (Max 50x korumalı).
        # NOT: used_leverage bu işlem için geçerlidir, self.leverage asla mutasyona uğramaz.
        used_leverage = self.leverage
        if desired_notional / self.leverage > self.balance:
            needed_leverage = desired_notional / self.balance
            if needed_leverage > 50.0:
                needed_leverage = 50.0
                desired_notional = self.balance * 50.0
            used_leverage = needed_leverage
            notional_value = desired_notional
            self.position_size = notional_value / price
            required_margin = notional_value / used_leverage
        else:
            notional_value = desired_notional
            self.position_size = raw_position_size
            required_margin = notional_value / used_leverage

        # Kesinti (Fee)
        fee = notional_value * self.taker_fee
        
        # Kasada yeterli nakit var mı kontrolü
        if self.balance - fee - required_margin <= 0 or self.position_size <= 0:
            return # Yetersiz bakiye
            
        # 3. İŞLEME GİRİŞ
        self.balance -= fee  # Komisyonu anında kes
        self.position = side
        self.entry_price = price
        self.margin_used = required_margin
        
        # 4. HEDEFLERİ YERLEŞTİR (SCALPING İÇİN DARALTILDI)
        self.partial_tp_done = False
        if side == 'LONG':
            self.stop_loss_price = price - stop_distance
            self.partial_tp_price = price + (atr * 1.5) if atr else price * 0.007 # Çok çabuk risk sıfırlama
            self.take_profit_price = price + tp_distance # Ana Hedef (Kısa)
            self.trailing_activation = price + (atr * 2.0) if atr else price * 0.01
            self.trailing_distance = atr * 1.0 if atr else stop_distance / 2
        else:
            self.stop_loss_price = price + stop_distance
            self.partial_tp_price = price - (atr * 1.5) if atr else price * 0.007
            self.take_profit_price = price - tp_distance
            self.trailing_activation = price - (atr * 2.0) if atr else price * 0.01
            self.trailing_distance = atr * 1.0 if atr else stop_distance / 2
        
        self.trades.append({
            "action": f"OPEN_{side}",
            "price": round(price, 6),
            "timestamp": str(timestamp),
            "fee": round(fee, 2),
            "balance_after": round(self.balance, 2),
            "sl": round(self.stop_loss_price, 6),
            "tp": round(self.take_profit_price, 6),
            "used_leverage": round(used_leverage, 2),
            "signal_mode": signal_mode
        })

    def close_position(self, price: float, timestamp: Any, reason: str = "", portion: float = 1.0):
        if not self.position or self.position_size <= 0:
            return
            
        closed_size = self.position_size * portion
            
        # PnL Hesaplama
        if self.position == 'LONG':
            pnl = (price - self.entry_price) * closed_size
        else:
            pnl = (self.entry_price - price) * closed_size
            
        notional_value = price * closed_size
        fee = notional_value * self.taker_fee
        
        net_pnl = pnl - fee
        self.balance += net_pnl
        
        # Kapatılan kısım kadar margin serbest kalır
        freed_margin = self.margin_used * portion
        self.margin_used -= freed_margin
        
        self.trades.append({
            "action": f"CLOSE_{self.position}_{reason}",
            "price": round(price, 6),
            "timestamp": str(timestamp),
            "pnl": round(net_pnl, 2),
            "fee": round(fee, 2),
            "reason": reason,
            "balance_after": round(self.balance, 2)
        })
        
        self.position_size -= closed_size
        
        # Tamamı kapandıysa veya pozisyon sıfıra indiyse State'i sıfırla
        if portion == 1.0 or self.position_size <= 0.000001:
            self.position = None
            self.entry_price = 0.0
            self.position_size = 0.0
            self.margin_used = 0.0
            self.stop_loss_price = 0.0
            self.take_profit_price = 0.0
            self.partial_tp_price = 0.0
            self.partial_tp_done = False
            self.trailing_activation = 0.0
            self.trailing_distance = 0.0

    def check_liquidation(self, current_price: float) -> bool:
        if not self.position:
            return False
            
        if self.position == 'LONG':
            pnl = (current_price - self.entry_price) * self.position_size
        else:
            pnl = (self.entry_price - current_price) * self.position_size
            
        margin_ratio = (self.margin_used + pnl) / (self.position_size * current_price) if current_price > 0 else 0
        
        if margin_ratio <= self.maintenance_margin:
            return True
            
        return False

    def generate_report(self) -> Dict[str, Any]:
        win_trades = [t for t in self.trades if "CLOSE" in t['action'] and t.get('pnl', 0) > 0]
        loss_trades = [t for t in self.trades if "CLOSE" in t['action'] and t.get('pnl', 0) <= 0]
        
        total_closed = len(win_trades) + len(loss_trades)
        win_rate = (len(win_trades) / total_closed * 100) if total_closed > 0 else 0.0
        
        net_profit = self.balance - self.initial_balance
        net_profit_pct = (net_profit / self.initial_balance) * 100
        
        daily_profit = net_profit / self.days_back if self.days_back > 0 else net_profit
        daily_profit_pct = net_profit_pct / self.days_back if self.days_back > 0 else net_profit_pct
        
        # Günlük PnL Hesaplama ve Max Drawdown
        daily_breakdown_list = []
        prev_equity = self.initial_balance
        peak_equity = self.initial_balance
        max_drawdown_pct = 0.0
        
        for date_str, eq_data in self.daily_equity.items():
            current_eq = eq_data['equity']
            if current_eq > peak_equity:
                peak_equity = current_eq
            
            dd_pct = ((peak_equity - current_eq) / peak_equity) * 100 if peak_equity > 0 else 0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
                
            daily_pnl = current_eq - prev_equity
            daily_breakdown_list.append({
                "date": date_str,
                "balance": eq_data['balance'],
                "open_pnl": eq_data['open_pnl'],
                "equity": current_eq,
                "daily_pnl": round(daily_pnl, 2)
            })
            prev_equity = current_eq

        # Profit Factor
        gross_profit = sum(t.get('pnl', 0) for t in win_trades)
        gross_loss = abs(sum(t.get('pnl', 0) for t in loss_trades))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)

        return {
            "initial_balance": self.initial_balance,
            "final_balance": round(self.balance, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round(net_profit_pct, 2),
            "daily_profit": round(daily_profit, 2),
            "daily_profit_pct": round(daily_profit_pct, 2),
            "total_trades": total_closed,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "leverage_used": self.leverage,
            "risk_per_trade_pct": self.risk_per_trade * 100,
            "trades": self.trades[-20:], # Sadece son 20 işlemi detaylı dön (Önyüz için)
            "daily_breakdown": daily_breakdown_list,
            "debug_logs": self.debug_logs[-10:] # Son 10 debug logu
        }
