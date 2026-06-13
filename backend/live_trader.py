import time
from typing import Dict, Any, List
from datetime import datetime

class LiveTrader:
    def __init__(self, initial_balance: float = 100000.0, leverage: float = 10.0, risk_per_trade: float = 0.03):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.risk_per_trade = risk_per_trade
        
        self.is_active = False
        
        # State
        self.daily_start_balance = initial_balance
        self.trading_halted_today = False
        self.last_traded_date = None
        
        # Active positions per symbol
        # format: { 'THYAO.IS': { 'side': 'LONG', 'entry_price': 100.0, 'size': 50, ... } }
        self.positions = {}
        
        # Trade History
        self.trades = []
        self.logs = []
        
    def start(self):
        self.is_active = True
        self.log("Canlı Test Modu Başlatıldı.")
        
    def stop(self):
        self.is_active = False
        self.log("Canlı Test Modu Durduruldu.")
        
    def log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {message}")
        print(f"[LIVE TRADER] {message}")
        if len(self.logs) > 200:
            self.logs.pop(0)
            
    def get_status(self) -> Dict[str, Any]:
        open_pnl_total = 0.0
        active_positions = []
        
        for sym, pos in self.positions.items():
            active_positions.append({
                "symbol": sym,
                "side": pos["side"],
                "entry_price": pos["entry_price"],
                "current_price": pos["current_price"],
                "pnl": pos["pnl"],
                "pnl_percent": pos["pnl_percent"]
            })
            open_pnl_total += pos["pnl"]
            
        return {
            "is_active": self.is_active,
            "balance": round(self.balance, 2),
            "equity": round(self.balance + open_pnl_total, 2),
            "open_pnl": round(open_pnl_total, 2),
            "daily_drawdown_halt": self.trading_halted_today,
            "positions": active_positions,
            "recent_logs": self.logs
        }

    def process_tick(self, symbol: str, current_price: float, high: float, low: float, analysis: Dict[str, Any]):
        if not self.is_active:
            return
            
        current_date = datetime.now().date()
        
        if current_date != self.last_traded_date:
            self.daily_start_balance = self.balance
            self.last_traded_date = current_date
            self.trading_halted_today = False
            
        # Drawdown Check (Halted logic removed so user can run infinitely)
        if self.balance < self.daily_start_balance * 0.97:
            self.log(f"🛑 Uyarı: %3 Günlük Drawdown aşıldı! (Durdurma kaldırıldı, işlem devam ediyor)")

            
        # Update existing position
        if symbol in self.positions:
            self._update_position(symbol, current_price, high, low)
            # If position was closed in update, it's removed from dict. We don't open a new one instantly.
            return
            
        # Time Filter (Amateur Hour)
        now = datetime.now()
        if now.hour == 9 or (now.hour == 10 and now.minute <= 15):
            return # Skip amateur hour
            
        # Look for Entry
        signal = analysis.get('signal', 'NOTR')
        score = analysis.get('score', 0.0)
        atr = analysis.get('indicators', {}).get('volatility', {}).get('atr', 0)
        
        if signal in ["GUCLU_AL", "AL"]:
            self._open_position(symbol, 'LONG', current_price, atr)
        elif signal in ["GUCLU_SAT", "SAT"]:
            self._open_position(symbol, 'SHORT', current_price, atr)
            
    def _open_position(self, symbol: str, side: str, price: float, atr: float):
        if atr > 0:
            stop_dist = atr * 2.0
            tp_dist = atr * 2.5
        else:
            stop_dist = price * 0.01
            tp_dist = price * 0.015
            
        max_loss = self.balance * self.risk_per_trade
        raw_size = max_loss / stop_dist
        notional = raw_size * price
        
        # Leverage Check
        if notional / self.leverage > self.balance:
            needed_lev = notional / self.balance
            if needed_lev > 50.0:
                needed_lev = 50.0
                notional = self.balance * 50.0
            used_leverage = needed_lev
        else:
            used_leverage = self.leverage
            
        size = notional / price
        margin = notional / used_leverage
        fee = notional * 0.0002 # Maker fee
        
        # Bakiye kontrolü (Serbest Marjin)
        total_margin_used = sum(p["margin"] for p in self.positions.values())
        available_margin = self.balance - total_margin_used
        
        if margin + fee > available_margin:
            self.log(f"⚠️ Yetersiz Bakiye! {symbol} için {margin:.2f} TL marjin gerekli. Serbest Bakiye: {available_margin:.2f} TL.")
            return
        
        self.balance -= fee
        
        sl_price = price - stop_dist if side == 'LONG' else price + stop_dist
        tp_price = price + tp_dist if side == 'LONG' else price - tp_dist
        partial_tp = price + (atr * 1.5) if side == 'LONG' else price - (atr * 1.5)
        
        self.positions[symbol] = {
            "side": side,
            "entry_price": price,
            "current_price": price,
            "size": size,
            "margin": margin,
            "leverage": used_leverage,
            "sl": sl_price,
            "tp": tp_price,
            "partial_tp": partial_tp,
            "partial_done": False,
            "pnl": -fee,
            "pnl_percent": 0.0,
            "open_time": datetime.now()
        }
        
        self.log(f"🟢 YENİ POZİSYON: {symbol} {side} @ {round(price, 2)} (SL: {round(sl_price,2)}, TP: {round(tp_price,2)})")
        
    def _update_position(self, symbol: str, current_price: float, high: float, low: float):
        pos = self.positions[symbol]
        pos["current_price"] = current_price
        
        side = pos["side"]
        entry = pos["entry_price"]
        size = pos["size"]
        
        if side == 'LONG':
            pnl = (current_price - entry) * size
            pnl_pct = ((current_price - entry) / entry) * 100 * pos["leverage"]
            
            # Partial TP
            if high >= pos["partial_tp"] and not pos["partial_done"]:
                buffer = entry * 0.001
                if pos["sl"] < entry + buffer:
                    pos["sl"] = entry + buffer
                pos["partial_done"] = True
                self.log(f"🛡️ {symbol} Risk Sıfırlandı (Stop Maliyete Çekildi)")
                
            # TP Hit
            if high >= pos["tp"]:
                self._close_position(symbol, pos["tp"], "TAKE_PROFIT")
                return
                
            # SL Hit
            if low <= pos["sl"]:
                self._close_position(symbol, pos["sl"], "STOP_LOSS")
                return
                
        else: # SHORT
            pnl = (entry - current_price) * size
            pnl_pct = ((entry - current_price) / entry) * 100 * pos["leverage"]
            
            # Partial TP
            if low <= pos["partial_tp"] and not pos["partial_done"]:
                buffer = entry * 0.001
                if pos["sl"] > entry - buffer:
                    pos["sl"] = entry - buffer
                pos["partial_done"] = True
                self.log(f"🛡️ {symbol} Risk Sıfırlandı (Stop Maliyete Çekildi)")
                
            # TP Hit
            if low <= pos["tp"]:
                self._close_position(symbol, pos["tp"], "TAKE_PROFIT")
                return
                
            # SL Hit
            if high >= pos["sl"]:
                self._close_position(symbol, pos["sl"], "STOP_LOSS")
                return
                
        pos["pnl"] = pnl
        pos["pnl_percent"] = pnl_pct

    def _close_position(self, symbol: str, exit_price: float, reason: str):
        pos = self.positions.pop(symbol)
        side = pos["side"]
        entry = pos["entry_price"]
        size = pos["size"]
        
        if side == 'LONG':
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size
            
        fee = (exit_price * size) * 0.0004 # Taker fee
        net_pnl = pnl - fee
        
        self.balance += net_pnl
        
        icon = "💰" if net_pnl > 0 else "🩸"
        self.log(f"{icon} POZİSYON KAPANDI: {symbol} ({reason}) PnL: {round(net_pnl, 2)} TL")
        
        self.trades.append({
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "exit": exit_price,
            "pnl": net_pnl,
            "reason": reason,
            "time": datetime.now()
        })
