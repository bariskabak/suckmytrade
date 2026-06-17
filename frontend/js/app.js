// Global Application State
const state = {
    activeSymbol: "THYAO.IS",
    timeframe: "15m",
    pairs: [],
    allSupportedPairs: [],
    lastResults: {},
    signalsHistory: [],
    
    // Paper Trading State
    paperBalance: 100000.00,
    positions: {} // Symbol -> { entryPrice, amount }
};

let ws = null;
let chart = null;
const API_BASE = window.location.protocol === "file:" ? "http://localhost:8000" : "";

// Audio Chime Generator using Web Audio API
function playSignalChime(isBuy) {
    const soundEnabled = document.getElementById('sound-toggle').checked;
    if (!soundEnabled) return;
    
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        
        osc.connect(gain);
        gain.connect(ctx.destination);
        
        if (isBuy) {
            // Rising chime for BUY
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
            osc.frequency.exponentialRampToValueAtTime(783.99, ctx.currentTime + 0.12); // G5
            osc.frequency.exponentialRampToValueAtTime(1046.50, ctx.currentTime + 0.24); // C6
            
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
            
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.4);
        } else {
            // Falling chime for SELL
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(392.00, ctx.currentTime); // G4
            osc.frequency.exponentialRampToValueAtTime(311.13, ctx.currentTime + 0.12); // Eb4
            osc.frequency.exponentialRampToValueAtTime(261.63, ctx.currentTime + 0.24); // C4
            
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
            
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.4);
        }
    } catch (e) {
        console.warn("Audio Context init failed (browser interaction required first):", e);
    }
}

// Format Price Function (adaptive decimals)
function formatPrice(val) {
    if (val === undefined || val === null) return '-';
    const num = parseFloat(val);
    if (num > 1000) return num.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (num > 1) return num.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    return num.toFixed(4);
}

// Format Percent Function
function formatPercent(val) {
    if (val === undefined || val === null) return '-';
    const num = parseFloat(val);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
}

// Update BIST Connection Status Badge
function updateBISTStatus(status) {
    const badge = document.getElementById('bist-status-badge');
    if (!badge) return;
    
    if (status === 'connected') {
        badge.className = 'connection-badge status-online';
        badge.innerHTML = '<span class="dot"></span> BIST: BAĞLI';
    } else if (status === 'connecting') {
        badge.className = 'connection-badge status-offline';
        badge.innerHTML = '<span class="dot"></span> BIST: BAĞLANIYOR...';
    } else {
        badge.className = 'connection-badge status-offline';
        badge.innerHTML = '<span class="dot"></span> BIST: BAĞLANTI YOK';
    }
}

// Chart Initializer and Loader
async function loadChartData(symbol) {
    if (typeof LightweightCharts === 'undefined') {
        console.warn("Grafik kütüphanesi (LightweightCharts) yüklü değil.");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/candles/${symbol}`);
        if (!res.ok) throw new Error("Mum verisi yüklenemedi.");
        const candles = await res.json();
        
        if (chart) {
            chart.setData(candles);
        }
    } catch (e) {
        console.error(e);
    }
}

// Change Active Coin Display and Load Chart
function selectActiveCoin(symbol) {
    state.activeSymbol = symbol;
    
    // Update active state in sidebar UI
    document.querySelectorAll('.coin-item').forEach(item => {
        if (item.getAttribute('data-sym') === symbol) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update Header
    document.getElementById('active-coin-name').innerText = symbol;
    
    const coinData = state.lastResults[symbol];
    if (coinData) {
        updateActiveCoinStats(coinData);
    }
    
    // Load new chart
    loadChartData(symbol);
    
    // Update Paper Trading buttons text
    const cleanSym = symbol.split('.')[0];
    document.getElementById('btn-mock-buy').innerHTML = `<i class="fa-solid fa-circle-arrow-up"></i> Sanal AL (${cleanSym})`;
    document.getElementById('btn-mock-sell').innerHTML = `<i class="fa-solid fa-circle-arrow-down"></i> Sanal SAT (${cleanSym})`;
    
    // Pozisyon bilgisini güncelle
    try { updatePositionPanel(); } catch(e) {}
    // Sabah analizini hisseye özel güncelle
    try { loadMorningReport(symbol); } catch(e) {}
}

// Update UI Stats for Selected Active Coin
function updateActiveCoinStats(data) {
    const priceEl = document.getElementById('active-coin-price');
    const changeEl = document.getElementById('active-coin-change');
    const signalBadge = document.getElementById('signal-badge');
    const scoreBadge = document.getElementById('signal-score-badge');
    const rsiVal = document.getElementById('rsi-value');
    const rsiProgress = document.getElementById('rsi-progress');
    const macdVal = document.getElementById('macd-value');
    const bbVal = document.getElementById('bb-value');
    const emaVal = document.getElementById('ema-value');

    // Prices and change
    const priceFormatted = formatPrice(data.price);
    priceEl.innerText = `${priceFormatted} TL`;
    
    const pct = data.ticker ? data.ticker.percentage : null;
    changeEl.innerText = formatPercent(pct);
    changeEl.className = 'change-badge ' + (pct >= 0 ? 'change-up' : 'change-down');
    if (pct !== null && pct >= 0) {
        changeEl.style.backgroundColor = 'rgba(0, 255, 136, 0.15)';
        changeEl.style.color = 'var(--color-buy)';
    } else if (pct !== null) {
        changeEl.style.backgroundColor = 'rgba(255, 74, 90, 0.15)';
        changeEl.style.color = 'var(--color-sell)';
    } else {
        changeEl.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
        changeEl.style.color = 'var(--text-secondary)';
    }

    // Signal status boxes and badges
    const signalStatusBox = document.getElementById('main-signal-status');
    signalStatusBox.className = 'signal-status-box ' + `signal-${data.signal.toLowerCase().replace('_', '-')}`;
    
    // Map signal code to readable format
    const signalLabels = {
        'GUCLU_AL': 'GÜÇLÜ AL',
        'AL': 'AL',
        'NOTR': 'NÖTR',
        'SAT': 'SAT',
        'GUCLU_SAT': 'GÜÇLÜ SAT'
    };
    signalBadge.innerText = signalLabels[data.signal] || data.signal;
    scoreBadge.innerText = `Skor: ${data.score > 0 ? '+' : ''}${data.score.toFixed(2)}`;

    // Update indicator stats
    rsiVal.innerText = data.indicators.rsi;
    rsiProgress.style.width = `${data.indicators.rsi}%`;
    
    // Recolor RSI progress based on levels
    if (data.indicators.rsi > 70) {
        rsiProgress.style.background = 'var(--color-sell)';
    } else if (data.indicators.rsi < 30) {
        rsiProgress.style.background = 'var(--color-buy)';
    } else {
        rsiProgress.style.background = 'var(--color-neutral)';
    }

    // MACD
    const macdData = data.indicators.macd;
    macdVal.innerHTML = `<span style="font-family: var(--font-mono)">L: ${macdData.line.toFixed(4)} | S: ${macdData.signal.toFixed(4)} | H: <span class="${macdData.hist >= 0 ? 'change-up' : 'change-down'}">${macdData.hist.toFixed(4)}</span></span>`;

    // Bollinger
    const bb = data.indicators.bollinger;
    bbVal.innerHTML = `<span style="font-family: var(--font-mono)">Üst: ${formatPrice(bb.upper)} | Alt: ${formatPrice(bb.lower)}</span>`;

    // EMA Stack
    const ema = data.indicators.ema;
    emaVal.innerHTML = `<span style="font-family: var(--font-mono)">EMA9: ${formatPrice(ema.fast)} | EMA21: ${formatPrice(ema.slow)} | EMA200: ${formatPrice(ema.trend)}</span>`;
}

// Render Sidebar Coin Ticker Items
function renderSidebarCoins() {
    const listContainer = document.getElementById('coin-list');
    listContainer.innerHTML = '';
    
    state.pairs.forEach(pair => {
        const itemData = state.lastResults[pair];
        const ticker = itemData ? itemData.ticker : null;
        const lastPrice = ticker ? formatPrice(ticker.last) : '-';
        const percent = ticker ? formatPercent(ticker.percentage) : '-';
        const changeClass = ticker && ticker.percentage >= 0 ? 'change-up' : 'change-down';
        
        let signalTag = '';
        if (itemData && itemData.signal) {
            let signalBg = 'var(--color-neutral-bg)';
            let signalColor = 'var(--color-neutral)';
            let sigText = 'NÖTR';
            
            if (itemData.signal.includes('AL')) {
                signalBg = 'var(--color-buy-bg)';
                signalColor = 'var(--color-buy)';
                sigText = itemData.signal === 'GUCLU_AL' ? 'G. AL' : 'AL';
            } else if (itemData.signal.includes('SAT')) {
                signalBg = 'var(--color-sell-bg)';
                signalColor = 'var(--color-sell)';
                sigText = itemData.signal === 'GUCLU_SAT' ? 'G. SAT' : 'SAT';
            }
            
            signalTag = `<span class="coin-signal-tag" style="background-color: ${signalBg}; color: ${signalColor}">${sigText}</span>`;
        }

        const div = document.createElement('div');
        div.className = `coin-item ${state.activeSymbol === pair ? 'active' : ''}`;
        div.setAttribute('data-sym', pair);
        div.innerHTML = `
            <div class="coin-item-left">
                <span class="coin-symbol">${pair}</span>
                ${signalTag}
            </div>
            <div class="coin-item-right">
                <span class="coin-price">${lastPrice} TL</span>
                <span class="coin-change ${changeClass}">${percent}</span>
            </div>
        `;
        
        div.addEventListener('click', () => selectActiveCoin(pair));
        listContainer.appendChild(div);
    });
}

// Render Signal Log Table Rows
function renderSignalLog() {
    const tbody = document.getElementById('signal-log-tbody');
    if (state.signalsHistory.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">Henüz sinyal üretilmedi. Sinyal döngüsü bekleniyor...</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = '';
    state.signalsHistory.forEach(sig => {
        const date = new Date(sig.timestamp * 1000);
        const timeStr = date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const tr = document.createElement('tr');
        
        let displaySig = sig.signal;
        if (sig.signal === 'GUCLU_AL') displaySig = 'GÜÇLÜ AL';
        if (sig.signal === 'GUCLU_SAT') displaySig = 'GÜÇLÜ SAT';
        if (sig.signal === 'NOTR') displaySig = 'NÖTR';
        
        tr.innerHTML = `
            <td class="log-time">${timeStr}</td>
            <td class="log-symbol">${sig.symbol}</td>
            <td class="log-tf">${sig.timeframe}</td>
            <td><span class="log-signal ${sig.signal}">${displaySig}</span></td>
            <td class="log-price">${formatPrice(sig.price)} TL</td>
            <td class="log-details">${sig.details ? sig.details.join(', ') : 'Trend Değişimi'}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Update Session Status Badge
function updateSessionStatus(status) {
    const badge = document.getElementById('session-status-badge');
    if (!badge) return;
    badge.innerHTML = `<span class="dot"></span> SEANS: ${status.toUpperCase()}`;
    if (status === 'Açık') {
        badge.className = 'connection-badge status-online';
    } else {
        badge.className = 'connection-badge status-offline';
    }
}

// Update Global Sentiment Score and Indices
function updateGlobalSentiment(gss, indices) {
    const gssValEl = document.getElementById('gss-value');
    const gssDescEl = document.getElementById('gss-desc');
    const gssBox = document.getElementById('gss-box');
    
    if (!gssValEl || !gssDescEl || !gssBox) return;
    
    gssValEl.innerText = gss.toFixed(2);
    
    // Update GSS box and description color
    gssBox.className = 'gss-box';
    if (gss >= 0.8) {
        gssDescEl.innerText = 'POZİTİF';
        gssDescEl.className = 'gss-desc gss-positive';
    } else if (gss <= -0.8) {
        gssDescEl.innerText = 'NEGATİF';
        gssDescEl.className = 'gss-desc gss-negative';
    } else {
        gssDescEl.innerText = 'NÖTR';
        gssDescEl.className = 'gss-desc gss-neutral';
    }
    
    // Update individual indices
    const idxNikkei = document.getElementById('idx-nikkei-val');
    const idxHangSeng = document.getElementById('idx-hangseng-val');
    const idxSP500 = document.getElementById('idx-sp500-val');
    
    if (indices) {
        if (indices.NIKKEI && idxNikkei) {
            const pct = indices.NIKKEI.percentage;
            idxNikkei.innerText = formatPercent(pct);
            idxNikkei.className = 'idx-val ' + (pct >= 0 ? 'idx-up' : 'idx-down');
        }
        if (indices.HANGSENG && idxHangSeng) {
            const pct = indices.HANGSENG.percentage;
            idxHangSeng.innerText = formatPercent(pct);
            idxHangSeng.className = 'idx-val ' + (pct >= 0 ? 'idx-up' : 'idx-down');
        }
        if (indices.SP500_FUT && idxSP500) {
            const pct = indices.SP500_FUT.percentage;
            idxSP500.innerText = formatPercent(pct);
            idxSP500.className = 'idx-val ' + (pct >= 0 ? 'idx-up' : 'idx-down');
        }
    }
}

// Connect WebSocket Server
function connectWebSocket() {
    let wsUrl;
    if (window.location.protocol === "file:") {
        wsUrl = "ws://127.0.0.1:8000/ws";
    } else {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        let host = window.location.host;
        wsUrl = `${protocol}//${host}/ws`;
    }
    
    console.log("[WS] Bağlanıyor:", wsUrl);
    
    try {
        ws = new WebSocket(wsUrl);
    } catch (e) {
        console.error("[WS] WebSocket oluşturulamadı:", e);
        setTimeout(connectWebSocket, 5000);
        return;
    }
    
    ws.onopen = () => {
        console.log("[WS] Bağlantı başarılı!");
        document.getElementById('connection-status').className = 'connection-badge status-online';
        document.getElementById('connection-status').innerHTML = '<span class="dot"></span> WEB: BAĞLI';
    };
    
    ws.onerror = (err) => {
        console.error("[WS] Bağlantı hatası:", err);
    };
    
    ws.onclose = (event) => {
        console.log("[WS] Bağlantı kapandı. Code:", event.code, "Reason:", event.reason);
        document.getElementById('connection-status').className = 'connection-badge status-offline';
        document.getElementById('connection-status').innerHTML = '<span class="dot"></span> WEB: KOPUK';
        updateBISTStatus('disconnected');
        updateSessionStatus('Kapalı');
        // 5 saniye sonra yeniden bağlanmayı dene
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        
        if (payload.type === 'welcome') {
            state.timeframe = payload.data.timeframe;
            state.pairs = payload.data.pairs;
            state.lastResults = payload.data.results || {};
            state.signalsHistory = payload.data.history || [];
            
            if (payload.data.bist_status) {
                updateBISTStatus(payload.data.bist_status);
            }
            if (payload.data.session_status) {
                updateSessionStatus(payload.data.session_status);
            }
            if (payload.data.gss !== undefined) {
                updateGlobalSentiment(payload.data.gss, payload.data.global_indices);
            }
            
            // Set active timeframe button state
            document.querySelectorAll('.tf-btn').forEach(btn => {
                if (btn.getAttribute('data-tf') === state.timeframe) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            document.getElementById('chart-tf-display').innerText = state.timeframe.toUpperCase();

            // Set active coin if available
            if (state.pairs.length > 0) {
                if (!state.pairs.includes(state.activeSymbol)) {
                    state.activeSymbol = state.pairs[0];
                }
                selectActiveCoin(state.activeSymbol);
            }
            
            renderSidebarCoins();
            renderSignalLog();

            // Eğer algoritmik strateji sekmesi aktifse karneyi de yükle/güncelle
            const algoContent = document.getElementById('content-algo');
            if (algoContent && algoContent.classList.contains('active')) {
                renderAlgoScorecard(state.lastResults);
            }
        }
        
        else if (payload.type === 'market_update') {
            state.timeframe = payload.data.timeframe;
            state.pairs = payload.data.pairs;
            state.lastResults = payload.data.results || {};
            
            if (payload.data.bist_status) {
                updateBISTStatus(payload.data.bist_status);
            }
            if (payload.data.session_status) {
                updateSessionStatus(payload.data.session_status);
            }
            if (payload.data.gss !== undefined) {
                updateGlobalSentiment(payload.data.gss, payload.data.global_indices);
            }
            
            renderSidebarCoins();
            
            // Eğer aktif coinin verisi geldiyse UI'ı güncelle
            const activeData = state.lastResults[state.activeSymbol];
            if (activeData) {
                updateActiveCoinStats(activeData);
            }
            
            if (payload.data.live_trading) {
                renderLiveTrading(payload.data.live_trading);
            }

            // Eğer algoritmik strateji sekmesi aktifse karneyi de gerçek zamanlı güncelle
            const algoContent = document.getElementById('content-algo');
            if (algoContent && algoContent.classList.contains('active')) {
                renderAlgoScorecard(state.lastResults);
            }
        }
        
        else if (payload.type === 'live_trading_update') {
            renderLiveTrading(payload.data);
        }
        
        else if (payload.type === 'new_signal') {
            const sig = payload.data;
            state.signalsHistory.unshift(sig);
            if (state.signalsHistory.length > 100) state.signalsHistory.pop();
            
            renderSignalLog();
            
            // Sesli uyarı çaldır (BUY -> true, SELL -> false)
            const isBuy = sig.signal.includes('AL');
            const isSell = sig.signal.includes('SAT');
            if (isBuy || isSell) {
                playSignalChime(isBuy);
                
                // Tarayıcı Bildirimi gönder
                if (Notification.permission === "granted") {
                    new Notification(`BIST Sinyal: ${sig.symbol}`, {
                        body: `${sig.timeframe} grafiğinde ${sig.signal} sinyali! Fiyat: ${formatPrice(sig.price)} TL`,
                        icon: '/favicon.ico'
                    });
                }
            }
        }
    };
}

// Request notification permission on first interaction
function initNotifications() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
}

// Toast Bildirim Sistemi
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const iconMap = {
        'success': 'fa-circle-check',
        'error': 'fa-circle-xmark',
        'warning': 'fa-triangle-exclamation',
        'info': 'fa-circle-info'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i class="fa-solid ${iconMap[type] || iconMap.info}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 350);
    }, duration);
}

// Pozisyon panelini güncelle
function updatePositionPanel() {
    const posPanel = document.getElementById('position-info');
    const pos = state.positions[state.activeSymbol];
    
    if (!pos || pos.amount <= 0) {
        posPanel.style.display = 'none';
        return;
    }
    
    posPanel.style.display = 'block';
    
    const activeResult = state.lastResults[state.activeSymbol];
    const currentPrice = activeResult ? activeResult.price : pos.entryPrice;
    const pnl = (currentPrice - pos.entryPrice) * pos.amount;
    const pnlPercent = ((currentPrice - pos.entryPrice) / pos.entryPrice * 100);
    
    document.getElementById('pos-symbol').textContent = state.activeSymbol.split('.')[0];
    document.getElementById('pos-qty').textContent = pos.amount.toFixed(2);
    document.getElementById('pos-entry').textContent = `${pos.entryPrice.toFixed(2)} TL`;
    
    const pnlEl = document.getElementById('pos-pnl');
    if (pnl >= 0) {
        pnlEl.textContent = `+${pnl.toFixed(2)} TL (+${pnlPercent.toFixed(1)}%)`;
        pnlEl.className = 'change-up';
    } else {
        pnlEl.textContent = `-${Math.abs(pnl).toFixed(2)} TL (${pnlPercent.toFixed(1)}%)`;
        pnlEl.className = 'change-down';
    }
}

// Paper Trading Logic (TL tabanlı)
function initPaperTrading() {
    const balanceEl = document.getElementById('paper-balance');
    const amountInput = document.getElementById('trade-amount-input');
    
    // LocalStorage bakiye kurtarma
    try {
        const savedBalance = localStorage.getItem('paper_balance');
        if (savedBalance) {
            state.paperBalance = parseFloat(savedBalance);
            balanceEl.innerText = `${state.paperBalance.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} TL`;
        }
        const savedPositions = localStorage.getItem('paper_positions');
        if (savedPositions) {
            state.positions = JSON.parse(savedPositions);
        }
    } catch (e) {
        console.warn("LocalStorage access denied:", e);
    }
    
    // Hızlı tutar butonları
    document.querySelectorAll('.quick-amt').forEach(btn => {
        btn.addEventListener('click', () => {
            amountInput.value = btn.getAttribute('data-amt');
        });
    });
    
    const buyBtn = document.getElementById('btn-mock-buy');
    const sellBtn = document.getElementById('btn-mock-sell');
    
    // SANAL AL butonu
    buyBtn.addEventListener('click', () => {
        const activeResult = state.lastResults[state.activeSymbol];
        if (!activeResult || !activeResult.price) {
            showToast(`${state.activeSymbol} için henüz fiyat verisi yok. Bekleyin...`, 'warning');
            return;
        }
        
        const price = activeResult.price;
        const tradeAmount = parseFloat(amountInput.value) || 1000;
        
        if (tradeAmount < 50) {
            showToast('Minimum işlem tutarı 50 TL!', 'warning');
            return;
        }
        
        if (state.paperBalance < tradeAmount) {
            showToast(`Yetersiz bakiye! Bakiye: ${state.paperBalance.toFixed(2)} TL`, 'error');
            return;
        }
        
        state.paperBalance -= tradeAmount;
        const boughtQty = tradeAmount / price;
        const coinName = state.activeSymbol.split('.')[0];
        
        if (state.positions[state.activeSymbol]) {
            const pos = state.positions[state.activeSymbol];
            const totalQty = pos.amount + boughtQty;
            const avgEntry = ((pos.amount * pos.entryPrice) + tradeAmount) / totalQty;
            state.positions[state.activeSymbol] = { entryPrice: avgEntry, amount: totalQty };
        } else {
            state.positions[state.activeSymbol] = { entryPrice: price, amount: boughtQty };
        }
        
        saveTradeState();
        balanceEl.innerText = `${state.paperBalance.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} TL`;
        balanceEl.style.color = '#fff';
        setTimeout(() => balanceEl.style.color = 'var(--color-buy)', 300);
        
        showToast(`✅ ${coinName} ALINDI — ${boughtQty.toFixed(2)} adet @ ${price.toFixed(2)} TL (${tradeAmount} TL)`, 'success', 4000);
        playSignalChime(true);
        updatePositionPanel();
    });
    
    // SANAL SAT butonu
    sellBtn.addEventListener('click', () => {
        const pos = state.positions[state.activeSymbol];
        const coinName = state.activeSymbol.split('.')[0];
        
        if (!pos || pos.amount <= 0) {
            showToast(`Elinizde ${coinName} pozisyonu bulunmuyor.`, 'warning');
            return;
        }
        
        const activeResult = state.lastResults[state.activeSymbol];
        if (!activeResult || !activeResult.price) {
            showToast(`${state.activeSymbol} için fiyat verisi yok. Bekleyin...`, 'warning');
            return;
        }
        
        const price = activeResult.price;
        const returnAmount = pos.amount * price;
        const profit = returnAmount - (pos.amount * pos.entryPrice);
        
        state.paperBalance += returnAmount;
        delete state.positions[state.activeSymbol];
        
        saveTradeState();
        balanceEl.innerText = `${state.paperBalance.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} TL`;
        
        if (profit >= 0) {
            balanceEl.style.color = 'var(--color-buy)';
            showToast(`🎉 ${coinName} SATILDI — Kâr: +${profit.toFixed(2)} TL (${pos.amount.toFixed(2)} adet @ ${price.toFixed(2)} TL)`, 'success', 5000);
        } else {
            balanceEl.style.color = 'var(--color-sell)';
            showToast(`📉 ${coinName} SATILDI — Zarar: -${Math.abs(profit).toFixed(2)} TL (${pos.amount.toFixed(2)} adet @ ${price.toFixed(2)} TL)`, 'error', 5000);
        }
        
        playSignalChime(profit >= 0);
        updatePositionPanel();
    });
}

// Trade state'i localStorage'a kaydet
function saveTradeState() {
    try {
        localStorage.setItem('paper_balance', state.paperBalance);
        localStorage.setItem('paper_positions', JSON.stringify(state.positions));
    } catch (e) {
        console.warn(e);
    }
}

// Config Modal Handlers
function initConfigModal() {
    const modal = document.getElementById('config-modal');
    const openBtn = document.getElementById('open-config-btn');
    const closeBtn = document.getElementById('close-config-btn');
    const cancelBtn = document.getElementById('cancel-config-btn');
    const saveBtn = document.getElementById('save-config-btn');
    const container = document.getElementById('pair-checkbox-container');
    const searchInput = document.getElementById('pair-search-input');
    const selectionCounter = document.getElementById('selection-counter');
    
    // BIST30 Components
    const BIST30_STOCKS = [
        "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", 
        "BRSAN.IS", "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", 
        "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS", 
        "KOZAA.IS", "KOZAL.IS", "MGROS.IS", "OYAKC.IS", "PETKM.IS", 
        "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", 
        "THYAO.IS", "TOASO.IS", "TUPRS.IS", "YKBNK.IS"
    ];

    const updateCounter = () => {
        if (!selectionCounter) return;
        const count = container.querySelectorAll('input[type="checkbox"]:checked').length;
        selectionCounter.innerText = `${count} Seçili`;
    };
    
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            container.querySelectorAll('.pair-checkbox-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                if (text.includes(query)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }
    
    // Quick Actions
    const btnSelectAll = document.getElementById('btn-select-all');
    const btnClearAll = document.getElementById('btn-clear-all');
    const btnSelectBist30 = document.getElementById('btn-select-bist30');

    if (btnSelectAll) {
        btnSelectAll.addEventListener('click', () => {
            container.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            updateCounter();
        });
    }
    
    if (btnClearAll) {
        btnClearAll.addEventListener('click', () => {
            container.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            updateCounter();
        });
    }

    if (btnSelectBist30) {
        btnSelectBist30.addEventListener('click', () => {
            container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                if (BIST30_STOCKS.includes(cb.value)) {
                    cb.checked = true;
                } else {
                    cb.checked = false;
                }
            });
            updateCounter();
        });
    }

    openBtn.addEventListener('click', async () => {
        try {
            const res = await fetch(`${API_BASE}/api/config`);
            const cfg = await res.json();
            state.allSupportedPairs = cfg.all_supported_pairs;
            
            // Reset search input
            if (searchInput) {
                searchInput.value = '';
            }
            
            // Load checkbox list
            container.innerHTML = '';
            state.allSupportedPairs.forEach(pair => {
                const checked = state.pairs.includes(pair) ? 'checked' : '';
                const label = document.createElement('label');
                label.className = 'pair-checkbox-item';
                label.innerHTML = `
                    <input type="checkbox" value="${pair}" ${checked}>
                    <span>${pair}</span>
                `;
                label.querySelector('input').addEventListener('change', updateCounter);
                container.appendChild(label);
            });
            
            updateCounter();
            modal.classList.add('active');
        } catch (e) {
            console.error(e);
        }
    });
    
    const closeModal = () => modal.classList.remove('active');
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    
    saveBtn.addEventListener('click', async () => {
        const checkedPairs = [];
        container.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
            checkedPairs.push(cb.value);
        });
        
        if (checkedPairs.length === 0) {
            alert("En az bir hisse seçmelisiniz!");
            return;
        }
        
        try {
            const res = await fetch(`${API_BASE}/api/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pairs: checkedPairs,
                    timeframe: state.timeframe
                })
            });
            
            if (res.ok) {
                const data = await res.json();
                state.pairs = data.pairs;
                renderSidebarCoins();
                closeModal();
            } else {
                alert("Yapılandırma kaydedilemedi.");
            }
        } catch (e) {
            console.error(e);
        }
    });
}

// Timeframe Changes
function initTimeframeHandlers() {
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const tf = e.currentTarget.getAttribute('data-tf');
            if (tf === state.timeframe) return;
            
            try {
                const res = await fetch(`${API_BASE}/api/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pairs: state.pairs,
                        timeframe: tf
                    })
                });
                
                if (res.ok) {
                    const data = await res.json();
                    state.timeframe = data.timeframe;
                    
                    document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
                    e.currentTarget.classList.add('active');
                    document.getElementById('chart-tf-display').innerText = state.timeframe.toUpperCase();
                    
                    // Reload active coin chart
                    loadChartData(state.activeSymbol);
                }
            } catch (e) {
                console.error(e);
            }
        });
    });
}

// Page Load Initializer
document.addEventListener('DOMContentLoaded', () => {
    console.log("[INIT] DOMContentLoaded tetiklendi.");
    
    // 1. Önce WebSocket bağlantısını kur (en kritik)
    try {
        console.log("[INIT] WebSocket bağlantısı kuruluyor...");
        connectWebSocket();
    } catch (e) {
        console.error("[INIT] WebSocket başlatma hatası:", e);
    }
    
    // 2. Grafik kütüphanesini başlat
    try {
        console.log("[INIT] Grafik başlatılıyor...");
        chart = new TradingChart('tv-chart');
    } catch (e) {
        console.error("[INIT] Grafik başlatma hatası:", e);
    }
    
    // 3. Diğer modüller
    try { initPaperTrading(); } catch (e) { console.error("[INIT] Paper Trading hatası:", e); }
    try { 
        fetch('/api/live-trading/status')
            .then(r => r.json())
            .then(data => renderLiveTrading(data))
            .catch(e => console.error("Live status error:", e));
    } catch (e) {}
    try { initConfigModal(); } catch (e) { console.error("[INIT] Config Modal hatası:", e); }
    try { initTimeframeHandlers(); } catch (e) { console.error("[INIT] Timeframe hatası:", e); }
    
    // Sabah analizini ilk yüklemede çek (arka planda)
    try { loadMorningReport(state.activeSymbol); } catch (e) { console.error("[INIT] Sabah Raporu hatası:", e); }
    
    // Bildirim izinleri
    document.body.addEventListener('click', () => {
        initNotifications();
    }, { once: true });
    
    console.log("[INIT] Başlatma tamamlandı.");
});

// Tab switching logic
function switchTab(tabId) {
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeBtn = document.getElementById(`tab-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    const activeContent = document.getElementById(`content-${tabId}`);
    if (activeContent) {
        activeContent.classList.add('active');
        activeContent.style.display = 'flex';
    }

    if (tabId === 'morning') {
        loadMorningReport(state.activeSymbol);
    } else if (tabId === 'algo') {
        loadAlgoReport();
    }
}

// Load Morning Report API
async function loadMorningReport(symbol = null) {
    const outlookTitle = document.getElementById('morning-outlook-title');
    const outlookGss = document.getElementById('morning-outlook-gss');
    const outlookDesc = document.getElementById('morning-outlook-desc');
    const rangeSupport = document.getElementById('morning-range-support');
    const rangeResistance = document.getElementById('morning-range-resistance');
    const rangeTrend = document.getElementById('morning-range-trend');
    const rangeSupportLabel = document.getElementById('morning-range-support-label');
    const rangeResistanceLabel = document.getElementById('morning-range-resistance-label');
    const rangeTrendLabel = document.getElementById('morning-range-trend-label');
    const recsList = document.getElementById('morning-recommendations-list');
    const newsFeed = document.getElementById('morning-news-feed');

    try {
        let url = `${API_BASE}/api/morning-report`;
        if (symbol) {
            url += `?symbol=${encodeURIComponent(symbol)}`;
        }
        const res = await fetch(url);
        if (!res.ok) throw new Error("Sabah analizi yüklenemedi.");
        const data = await res.json();

        // Update Labels based on symbol
        if (symbol) {
            const name = symbol.split('.')[0];
            if (rangeSupportLabel) rangeSupportLabel.innerText = `${name} Destek Seviyesi`;
            if (rangeResistanceLabel) rangeResistanceLabel.innerText = `${name} Direnç Seviyesi`;
            if (rangeTrendLabel) rangeTrendLabel.innerText = `${name} Gün İçi Eğilim`;
        } else {
            if (rangeSupportLabel) rangeSupportLabel.innerText = "BIST 100 Destek Seviyesi";
            if (rangeResistanceLabel) rangeResistanceLabel.innerText = "BIST 100 Direnç Seviyesi";
            if (rangeTrendLabel) rangeTrendLabel.innerText = "Genel Gün İçi Eğilim";
        }

        // 1. Outlook
        if (outlookTitle) {
            outlookTitle.innerText = data.outlook.title;
            outlookTitle.className = "outlook-title";
            if (data.outlook.class === 'gss-positive') {
                outlookTitle.style.color = 'var(--color-buy)';
            } else if (data.outlook.class === 'gss-negative') {
                outlookTitle.style.color = 'var(--color-sell)';
            } else {
                outlookTitle.style.color = 'var(--text-normal)';
            }
        }
        if (outlookGss) outlookGss.innerText = data.outlook.gss.toFixed(2);
        if (outlookDesc) outlookDesc.innerText = data.outlook.description;

        // 2. Range
        if (rangeSupport) rangeSupport.innerText = data.range_estimate.support;
        if (rangeResistance) rangeResistance.innerText = data.range_estimate.resistance;
        if (rangeTrend) {
            rangeTrend.innerText = data.range_estimate.trend;
            rangeTrend.className = "range-metric-value";
            if (data.range_estimate.trend.includes("Pozitif") || data.range_estimate.trend.includes("Yukarı")) {
                rangeTrend.classList.add("change-up");
                rangeTrend.style.color = 'var(--color-buy)';
            } else if (data.range_estimate.trend.includes("Negatif") || data.range_estimate.trend.includes("Aşağı")) {
                rangeTrend.classList.add("change-down");
                rangeTrend.style.color = 'var(--color-sell)';
            } else {
                rangeTrend.style.color = 'var(--text-normal)';
            }
        }

        // 3. Recommendations
        if (recsList) {
            recsList.innerHTML = '';
            if (data.recommended_stocks && data.recommended_stocks.length > 0) {
                data.recommended_stocks.forEach(rec => {
                    const item = document.createElement('div');
                    item.className = 'recommendation-item';
                    
                    const inds = rec.indicators_support || [];
                    const indicatorsHtml = inds.map(ind => `<span class="rec-ind-badge">${ind}</span>`).join('');
                    
                    const steps = rec.steps || [];
                    const stepsHtml = steps.map(step => `
                        <div class="rec-step-item">
                            <i class="fa-solid fa-angle-right"></i>
                            <span>${step}</span>
                        </div>
                    `).join('');

                    const strategy = rec.strategy || "Kademeli Alım";
                    const tpPct = rec.tp_pct ? `<span class="rec-pct">${rec.tp_pct}</span>` : "";
                    const slPct = rec.sl_pct ? `<span class="rec-pct">${rec.sl_pct}</span>` : "";
                    const horizon = rec.timeframe_horizon || "1-3 Seans";

                    item.innerHTML = `
                        <div class="rec-header">
                            <div class="rec-symbol-wrap">
                                <span class="rec-symbol">${rec.name}</span>
                                <span class="rec-badge">${rec.symbol}</span>
                                <span class="rec-strategy-badge">${strategy}</span>
                            </div>
                            <span class="rec-price">${formatPrice(rec.price)} TL</span>
                        </div>
                        
                        <div class="rec-stats-grid">
                            <div class="rec-stat-box">
                                <div class="rec-stat-lbl">Giriş Bölgesi</div>
                                <div class="rec-stat-num">${rec.entry_range || ''}</div>
                            </div>
                            <div class="rec-stat-box positive">
                                <div class="rec-stat-lbl">Hedef (Kâr Al)</div>
                                <div class="rec-stat-num tp">${rec.tp || ''} ${tpPct}</div>
                            </div>
                            <div class="rec-stat-box negative">
                                <div class="rec-stat-lbl">Zarar Kes</div>
                                <div class="rec-stat-num sl">${rec.sl || ''} ${slPct}</div>
                            </div>
                        </div>

                        <div class="rec-indicators-row">
                            ${indicatorsHtml}
                        </div>

                        <div class="rec-detail-title"><i class="fa-solid fa-bullseye"></i> Teknik Gerekçe</div>
                        <div class="rec-rationale">${rec.rationale || ''}</div>
                        
                        <div class="rec-detail-title"><i class="fa-solid fa-layer-group"></i> Kademeli Alım Adımları</div>
                        <div class="rec-steps-list">
                            ${stepsHtml}
                        </div>

                        <div class="rec-footer">
                            <div class="rec-horizon">
                                <i class="fa-regular fa-clock"></i>
                                <span>Vade: <strong>${horizon}</strong></span>
                            </div>
                            <div class="rec-risk">
                                <i class="fa-solid fa-shield-halved"></i>
                                <span>${rec.risk || ''}</span>
                            </div>
                        </div>
                    `;
                    recsList.appendChild(item);
                });
            } else {
                recsList.innerHTML = '<div class="empty-feed">Öneri bulunmamaktadır.</div>';
            }
        }
        // 3.5 Global Markets & VIOP
        const globalIndices = document.getElementById('morning-global-indices');
        if (globalIndices) {
            globalIndices.innerHTML = '';
            if (data.global_markets) {
                const indexNames = {
                    "VIOP_30": "VIOP 30 / BIST 30",
                    "NIKKEI": "Nikkei 225 (Japonya)",
                    "HANGSENG": "Hang Seng (Hong Kong)",
                    "SHANGHAI": "Shanghai Comp. (Çin)",
                    "SP500_FUT": "S&P 500 Vadeli",
                    "NASDAQ_FUT": "Nasdaq Vadeli"
                };

                Object.entries(data.global_markets).forEach(([key, info]) => {
                    const name = indexNames[key] || key;
                    const price = info.last ? formatPrice(info.last) : '-';
                    const changeVal = (info.percentage !== null && info.percentage !== undefined) ? info.percentage.toFixed(2) : '0.00';
                    const isUp = info.percentage > 0;
                    const isDown = info.percentage < 0;
                    const badgeClass = isUp ? 'trend-up' : (isDown ? 'trend-down' : 'trend-flat');
                    const sign = isUp ? '+' : '';
                    
                    const el = document.createElement('div');
                    el.className = 'global-idx-item';
                    el.innerHTML = `
                        <div class="global-idx-name-wrap">
                            <span class="global-idx-name">${name}</span>
                            <span class="global-idx-ticker">${info.ticker}</span>
                        </div>
                        <div class="global-idx-price-wrap">
                            <span class="global-idx-price">${price}</span>
                            <span class="global-idx-change ${badgeClass}">${sign}${changeVal}%</span>
                        </div>
                    `;
                    globalIndices.appendChild(el);
                });
            } else {
                globalIndices.innerHTML = '<div class="empty-feed">Küresel endeks verisi bulunamadı.</div>';
            }
        }

        // 4. News Feed
        if (newsFeed) {
            newsFeed.innerHTML = '';
            if (data.news && data.news.length > 0) {
                data.news.forEach(item => {
                    const el = document.createElement('a');
                    el.href = item.link;
                    el.target = '_blank';
                    el.className = 'news-item';
                    el.innerHTML = `
                        <span class="news-time">${item.time}</span>
                        <div class="news-content">
                            <div class="news-title">${item.title}</div>
                            <div class="news-source">${item.source}</div>
                        </div>
                    `;
                    newsFeed.appendChild(el);
                });
            } else {
                newsFeed.innerHTML = '<div class="empty-feed">Gündem haberi bulunmamaktadır.</div>';
            }
        }

        // 5. Sektörel Analiz (Heatmap)
        const sectorAnalysis = document.getElementById('morning-sector-analysis');
        if (sectorAnalysis) {
            sectorAnalysis.innerHTML = '';
            if (data.sector_analysis && data.sector_analysis.length > 0) {
                data.sector_analysis.forEach(sector => {
                    const el = document.createElement('div');
                    el.className = 'sector-item';
                    
                    let trendColor = 'var(--text-normal)';
                    let sign = '';
                    if (sector.color === 'positive') {
                        trendColor = 'var(--color-buy)';
                        sign = '+';
                    } else if (sector.color === 'negative') {
                        trendColor = 'var(--color-sell)';
                    }
                    
                    el.innerHTML = `
                        <div class="sector-name">${sector.name}</div>
                        <div class="sector-trend">
                            <span class="sector-trend-name" style="color: ${trendColor}">${sector.trend}</span>
                            <span class="sector-score" style="background: rgba(255,255,255,0.05); color: ${trendColor}">${sign}${sector.score}</span>
                        </div>
                    `;
                    sectorAnalysis.appendChild(el);
                });
            } else {
                sectorAnalysis.innerHTML = '<div class="empty-feed">Sektör verisi bulunamadı.</div>';
            }
        }

        // 6. Ekonomik Takvim
        const calendarContainer = document.getElementById('morning-economic-calendar');
        if (calendarContainer) {
            calendarContainer.innerHTML = '';
            if (data.economic_calendar && data.economic_calendar.length > 0) {
                data.economic_calendar.forEach(event => {
                    const el = document.createElement('div');
                    el.className = `calendar-item importance-${event.importance}`;
                    el.innerHTML = `
                        <div class="calendar-time">${event.time}</div>
                        <div class="calendar-country">${event.country}</div>
                        <div class="calendar-event">${event.event}</div>
                    `;
                    calendarContainer.appendChild(el);
                });
            } else {
                calendarContainer.innerHTML = '<div class="empty-feed">Bugün için veri takvimi boş.</div>';
            }
        }

    } catch (error) {
        console.error("Sabah raporu yükleme hatası:", error);
    }
}

// Algoritmik Strateji & Odak Sekmesi Verilerini Yükle
async function loadAlgoReport() {
    const gssBadge = document.getElementById('algo-gss-badge');
    const gssDesc = document.getElementById('algo-gss-desc');
    const viopChange = document.getElementById('algo-viop-change');
    const viopDesc = document.getElementById('algo-viop-desc');
    const analystNote = document.getElementById('algo-analyst-note');
    const scorecardList = document.getElementById('algo-scorecard-list');

    try {
        // Skor tablosunda yükleniyor durumunu göster
        if (scorecardList) {
            scorecardList.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Algoritmik veriler hesaplanıyor...</div>';
        }

        // Makro & Duyarlılık verileri için sabah raporunu çekelim
        let morningData = null;
        try {
            const morningRes = await fetch(`${API_BASE}/api/morning-report`);
            if (morningRes.ok) {
                morningData = await morningRes.json();
            }
        } catch (e) {
            console.error("[ALGO] Makro rapor yüklenirken hata:", e);
        }

        // Makro ve Duyarlılık Arayüzünü Güncelle
        if (morningData) {
            // 1. GSS Skoru
            const gss = morningData.outlook.gss !== undefined ? morningData.outlook.gss : 0.00;
            if (gssBadge) {
                gssBadge.innerText = gss.toFixed(2);
                gssBadge.className = 'gss-score-badge';
                if (gss > 0.5) gssBadge.classList.add('positive');
                else if (gss < -0.5) gssBadge.classList.add('negative');
            }
            if (gssDesc) {
                gssDesc.innerText = morningData.outlook.description || 'Küresel endeks verileri analiz edilemedi.';
            }

            // 2. VIOP & BIST 30 Durumu
            const viopInfo = morningData.global_markets ? morningData.global_markets.VIOP_30 : null;
            if (viopInfo) {
                const viopPct = viopInfo.percentage || 0.00;
                if (viopChange) {
                    viopChange.innerText = formatPercent(viopPct);
                    viopChange.className = viopPct > 0 ? 'trend-up' : (viopPct < 0 ? 'trend-down' : 'trend-flat');
                    viopChange.style.color = viopPct > 0 ? 'var(--color-buy)' : (viopPct < 0 ? 'var(--color-sell)' : 'var(--text-muted)');
                }
                if (viopDesc) {
                    viopDesc.innerHTML = `VIOP 30 endeksi şu anda <strong>${formatPrice(viopInfo.last)}</strong> seviyesinde ve günün başından bu yana <strong>${formatPercent(viopPct)}</strong> değişim gösterdi. Bu durum BIST seans açılışı öncesi vadeli tarafta <strong>${viopPct > 0 ? 'alıcılı' : (viopPct < 0 ? 'satıcılı' : 'yatay')}</strong> bir eğilime işaret ediyor.`;
                }
            } else {
                if (viopDesc) viopDesc.innerText = 'VIOP 30 vadelisi ve BIST 30 verisi şu an alınamıyor.';
            }

            // 3. Baş Stratejist Notu (Ekonomist Yorumu)
            if (analystNote) {
                const g = morningData.global_markets || {};
                const nikkei = g.NIKKEI ? g.NIKKEI.percentage : 0.00;
                const hangseng = g.HANGSENG ? g.HANGSENG.percentage : 0.00;
                const sp500 = g.SP500_FUT ? g.SP500_FUT.percentage : 0.00;
                
                let comment = `<strong>📈 KÜRESEL VİOP & MAKRO KORELASYON ÖZETİ:</strong><br>Asya seansında Nikkei 225 %${nikkei.toFixed(2)} ve Hang Seng %${hangseng.toFixed(2)} seyrederken, ABD vadeli endeksleri (S&P 500 Vadeli %${sp500.toFixed(2)}) işlem görmektedir. Makro korelasyon matrisi ${sp500 >= 0 ? 'risk-on (alıcı iştahı yüksek)' : 'risk-off (güvenli liman arayışı)'} bir görünüme işaret ediyor.<br><br><strong>🤖 ALGORİTMİK STRATEJİ & GÜNLÜK ODAK:</strong><br>`;
                
                if (gss > 1.5) {
                    comment += `GSS (${gss.toFixed(2)}) aşırı ralli bölgesinde. Algoritmamız <strong>"Mean Reversion Scalping"</strong> modundadır. Piyasada genel bir coşku (FOMO) olsa bile, tepe noktalardan (Bollinger Üst Bandı) kâr realizasyonları (SHORT) hedeflenmeli, fiyatın ortalamaya geri dönmesi beklenmelidir. Gün içi agresif alımlardan kaçının.`;
                } else if (gss > 0.5) {
                    comment += `GSS (${gss.toFixed(2)}) pozitif/yatay. Güne sakin bir başlangıç bekliyoruz. BIST tarafında endeksten ziyade hisse bazlı (Alfa) fırsatlara odaklanıyoruz. Dar bantta hareket eden hisselerde, alt banttan sekme yakalandığı anda (RSI < 35) kısa hedefli scalping işlemleri devreye alınmalıdır.`;
                } else if (gss < -1.5) {
                    comment += `GSS (${gss.toFixed(2)}) <strong>Kriz/Panik Bölgesinde!</strong> Küresel piyasalarda ciddi bir kan kaybı var. Algoritmamız tam bu anları bekler. BIST satıcılı açılsa dahi panik yapmıyoruz; hisseler Bollinger alt bandını deldiğinde ve RSI dibe vurduğunda (Oversold), "Kazanma Makinesi" acımasızca dipten toplayıp ilk zıplamada kârı alıp çıkacaktır. Nakit hazır bekleyin.`;
                } else if (gss < -0.5) {
                    comment += `GSS (${gss.toFixed(2)}) negatif. Satıcılı bir baskı hakim. Algoritmik odak: Bıçak düşerken tutmaya çalışmıyoruz. Fiyatın Bollinger alt bandında konsolide olmasını bekleyip, RSI'da pozitif uyumsuzluk görüldüğü ilk çeyrek saatte (15m) milisaniyelik vur-kaç (scalping) pozisyonları kurguluyoruz.`;
                } else {
                    comment += `GSS (${gss.toFixed(2)}) tamamen nötr (Testere Piyasası). Mean Reversion stratejisinin en kârlı olduğu gün! BIST 100 yönsüz kalacaktır. Algoritma her iki yöne de (Bollinger altından AL, üstünden SAT) sürekli çift yönlü dar bant işlemleri yapacak. Hızlı kâr al hedeflerine sadık kalın.`;
                }
                
                analystNote.innerHTML = comment;
            }
        }

        // Göstergelerin ham analiz verilerini API'den çekelim (varsa state.lastResults kullanalım)
        let results = state.lastResults;
        if (!results || Object.keys(results).length === 0) {
            try {
                const res = await fetch(`${API_BASE}/api/results`);
                if (res.ok) {
                    results = await res.json();
                    state.lastResults = results;
                }
            } catch (e) {
                console.error("[ALGO] Analiz verileri çekilirken hata:", e);
            }
        }

        renderAlgoScorecard(results);

    } catch (error) {
        console.error("Algoritmik strateji tabı yüklenirken hata oluştu:", error);
        if (scorecardList) {
            scorecardList.innerHTML = '<div class="empty-feed">Veriler yüklenirken bir hata oluştu. Lütfen tekrar deneyin.</div>';
        }
    }
}

// Takip Listesi Algoritmik Karnesini Ekrana Bas
function renderAlgoScorecard(results) {
    const scorecardList = document.getElementById('algo-scorecard-list');
    if (!scorecardList) return;

    if (!results || Object.keys(results).length === 0) {
        scorecardList.innerHTML = '<div class="empty-feed">Hesaplanmış algoritmik veri bulunmamaktadır.</div>';
        return;
    }

    scorecardList.innerHTML = '';

    Object.entries(results).forEach(([symbol, data]) => {
        const name = symbol.split('.')[0];
        const signal = data.signal || 'NOTR';
        const score = data.score !== undefined ? data.score : 0.0;
        const price = data.price || 0.0;
        const indicators = data.indicators || {};

        // 1. Sinyal Rozeti
        let sigClass = 'neutral';
        let sigText = 'NÖTR';
        if (signal.includes('AL') || signal.includes('BUY')) {
            sigClass = 'buy';
            sigText = signal === 'GUCLU_AL' ? 'GÜÇLÜ AL' : 'AL';
        } else if (signal.includes('SAT') || signal.includes('SELL')) {
            sigClass = 'sell';
            sigText = signal === 'GUCLU_SAT' ? 'GÜÇLÜ SAT' : 'SAT';
        }

        // 2. Skor Çubuğu Dolgusu (Skor genelde -5 ile +5 arası. 0-100% arasına normalize edelim)
        const scorePct = Math.min(100, Math.max(0, (score + 5) * 10));
        const scoreFillClass = score > 0 ? 'pos' : (score < 0 ? 'neg' : '');

        // 3. RSI Detayları
        const rsiVal = indicators.rsi !== undefined ? indicators.rsi : 50.0;
        let rsiText = 'Nötr';
        let rsiClass = '';
        if (rsiVal < 30) {
            rsiText = 'Aşırı Satım';
            rsiClass = 'up'; // Aşırı satım yükseliş sinyalidir
        } else if (rsiVal > 70) {
            rsiText = 'Aşırı Alım';
            rsiClass = 'down'; // Aşırı alım düşüş sinyalidir
        }

        // 4. MACD Detayları
        const macd = indicators.macd || {};
        const macdHist = macd.hist !== undefined ? macd.hist : 0.0;
        let macdText = 'Yatay';
        let macdClass = '';
        if (macdHist > 0) {
            macdText = 'Boğa';
            macdClass = 'up';
        } else if (macdHist < 0) {
            macdText = 'Ayı';
            macdClass = 'down';
        }

        // 5. EMA Detayları
        const ema = indicators.ema || {};
        const emaFast = ema.fast || 0.0;
        const emaSlow = ema.slow || 0.0;
        const emaTrend = ema.trend || 0.0;
        let emaText = 'Sıkışma';
        let emaClass = 'warning';
        if (emaFast > emaSlow && price > emaTrend) {
            emaText = 'Yükseliş';
            emaClass = 'up';
        } else if (emaFast < emaSlow && price < emaTrend) {
            emaText = 'Düşüş';
            emaClass = 'down';
        }

        // 6. Bollinger Bantları (İşlem Bandı)
        const bb = indicators.bollinger || {};
        const bbLower = bb.lower || price * 0.98;
        const bbUpper = bb.upper || price * 1.02;

        // 7. Dinamik Risk Hesaplama
        let riskClass = 'medium';
        let riskText = 'Orta';
        const rsiDiff = Math.abs(rsiVal - 50);
        const bbSpread = (bbUpper - bbLower) / price;
        if (rsiDiff > 22 || bbSpread > 0.08) {
            riskClass = 'high';
            riskText = 'Yüksek';
        } else if (rsiDiff < 10 && bbSpread < 0.03) {
            riskClass = 'low';
            riskText = 'Düşük';
        }

        const item = document.createElement('div');
        item.className = 'scorecard-item';
        item.innerHTML = `
            <div class="sc-header">
                <div class="sc-symbol-group">
                    <span class="sc-symbol">${name}</span>
                    <span class="sc-name">${symbol}</span>
                </div>
                <span class="sc-signal-badge ${sigClass}">${sigText}</span>
            </div>

            <div class="sc-header" style="margin-bottom: 0.5rem;">
                <div class="sc-price">${formatPrice(price)} TL</div>
                <div class="sc-price-score">
                    <div class="sc-score-wrapper">
                        <span class="sc-score-val">${score > 0 ? '+' : ''}${score.toFixed(2)}</span>
                        <div class="sc-score-bar">
                            <div class="sc-score-fill ${scoreFillClass}" style="width: ${scorePct}%"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="sc-indicators-row">
                <div class="sc-ind-box">
                    <span class="sc-ind-lbl">RSI</span>
                    <span class="sc-ind-val ${rsiClass}">${rsiVal.toFixed(1)} (${rsiText})</span>
                </div>
                <div class="sc-ind-box">
                    <span class="sc-ind-lbl">MACD Hist</span>
                    <span class="sc-ind-val ${macdClass}">${macdHist.toFixed(4)} (${macdText})</span>
                </div>
                <div class="sc-ind-box">
                    <span class="sc-ind-lbl">EMA Durum</span>
                    <span class="sc-ind-val ${emaClass}">${emaText}</span>
                </div>
            </div>

            <div class="sc-footer">
                <div class="sc-target-range">Bollinger Bandı: <strong>${formatPrice(bbLower)} - ${formatPrice(bbUpper)} TL</strong></div>
                <div class="sc-risk-label ${riskClass}">Risk: ${riskText}</div>
            </div>
        `;
        scorecardList.appendChild(item);
    });
}

// SIMULATION AND BACKTEST
async function runSimulation() {
    const symbol = document.getElementById('sim-symbol').value || 'THYAO.IS';
    const startDate = document.getElementById('sim-start').value;
    const endDate = document.getElementById('sim-end').value;
    const balance = parseFloat(document.getElementById('sim-balance').value) || 10000;
    const riskPct = parseFloat(document.getElementById('sim-risk').value) || 10;
    
    const btn = document.getElementById('sim-start-btn');
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Test Ediliyor...';
    btn.disabled = true;
    
    try {
        const payload = {
            symbol: symbol,
            timeframe: "15m",
            days_back: 30, // fallback
            initial_balance: balance,
            risk_per_trade: riskPct / 100.0,
            start_date: startDate || null,
            end_date: endDate || null
        };
        
        const response = await fetch(`${API_BASE}/api/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Simülasyon hatası");
        }
        
        const res = data.simulation_result;
        
        document.getElementById('sim-results').style.display = 'block';
        document.getElementById('sim-win-rate').innerText = `%${res.win_rate_pct.toFixed(2)}`;
        
        const np = document.getElementById('sim-net-profit');
        np.innerText = `${res.net_profit.toFixed(2)} TL`;
        np.style.color = res.net_profit > 0 ? '#4ade80' : '#ef4444';
        
        const pf = document.getElementById('sim-profit-factor');
        pf.innerText = res.profit_factor !== undefined ? res.profit_factor.toFixed(2) : '0.00';
        pf.style.color = (res.profit_factor !== undefined && res.profit_factor >= 1.0) ? '#4ade80' : '#ef4444';
        
        const md = document.getElementById('sim-max-drawdown');
        md.innerText = res.max_drawdown_pct !== undefined ? `%${res.max_drawdown_pct.toFixed(2)}` : '%0.00';
        md.style.color = (res.max_drawdown_pct !== undefined && res.max_drawdown_pct > 15) ? '#ef4444' : '#4ade80';
        
        document.getElementById('sim-final-balance').innerText = `${res.final_balance.toFixed(2)} TL`;
        
        const tbody = document.getElementById('sim-trades-body');
        tbody.innerHTML = '';
        
        res.trades.forEach(t => {
            const tr = document.createElement('tr');
            const isWin = t.pnl && t.pnl > 0;
            const pnlColor = t.pnl ? (isWin ? '#4ade80' : '#ef4444') : '#ccc';
            const pnlText = t.pnl ? `${t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(2)} TL` : '-';
            
            tr.innerHTML = `
                <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em;">${t.timestamp.split(' ')[0]}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em;">
                    <span style="display:inline-block; padding:3px 6px; border-radius:4px; font-weight:bold; background:${t.action.includes('LONG') ? 'rgba(74, 222, 128, 0.2)' : 'rgba(239, 68, 68, 0.2)'}; color:${t.action.includes('LONG') ? '#4ade80' : '#ef4444'};">${t.action}</span>
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em; font-family: monospace;">${t.price}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em; font-weight: bold; color: ${pnlColor};">${pnlText}</td>
            `;
            tbody.appendChild(tr);
        });
        
        const dailyBody = document.getElementById('sim-daily-body');
        if (dailyBody) {
            dailyBody.innerHTML = '';
            if (res.daily_breakdown && res.daily_breakdown.length > 0) {
                // Reverse to show newest day first
                const reversedDaily = [...res.daily_breakdown].reverse();
                reversedDaily.forEach(d => {
                    const dTr = document.createElement('tr');
                    const isWin = d.daily_pnl && d.daily_pnl > 0;
                    const isLoss = d.daily_pnl && d.daily_pnl < 0;
                    const pnlColor = isWin ? '#4ade80' : (isLoss ? '#ef4444' : '#ccc');
                    const pnlText = d.daily_pnl !== 0 ? `${isWin ? '+' : ''}${d.daily_pnl.toFixed(2)} TL` : '0.00 TL';
                    
                    dTr.innerHTML = `
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em;">${d.date}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em; color: ${pnlColor}; font-weight: bold;">${pnlText}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-size: 0.9em;">${d.equity.toFixed(2)} TL</td>
                    `;
                    dailyBody.appendChild(dTr);
                });
            } else {
                dailyBody.innerHTML = '<tr><td colspan="3" style="padding: 8px; text-align: center;">Yeterli veri yok</td></tr>';
            }
        }
        
        showToast("Simülasyon başarıyla tamamlandı!", "success");
        
    } catch (err) {
        console.error(err);
        showToast(err.message, "error");
    } finally {
        btn.innerHTML = 'Testi Başlat';
        btn.disabled = false;
    }
}

// ==========================================
// LIVE PAPER TRADING LOGIC
// ==========================================

let isLiveTradingActive = false;

async function toggleLiveTrading() {
    const btn = document.getElementById('btn-toggle-live');
    const newState = !isLiveTradingActive;
    
    try {
        btn.disabled = true;
        const response = await fetch('/api/live-trading/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: newState })
        });
        
        const res = await response.json();
        if (res.status === 'success') {
            isLiveTradingActive = res.is_active;
            
            if (isLiveTradingActive) {
                btn.innerHTML = '<i class="fa-solid fa-stop"></i> Durdur';
                btn.className = 'btn btn-danger';
                document.getElementById('live-status-text').innerText = 'ÇALIŞIYOR';
                document.getElementById('live-status-text').style.color = 'var(--color-buy)';
                showToast("Canlı Test Motoru Başlatıldı", "success");
            } else {
                btn.innerHTML = '<i class="fa-solid fa-play"></i> Başlat';
                btn.className = 'btn btn-secondary';
                document.getElementById('live-status-text').innerText = 'DURDURULDU';
                document.getElementById('live-status-text').style.color = 'var(--color-warning)';
                showToast("Canlı Test Motoru Durduruldu", "warning");
            }
        }
    } catch (e) {
        showToast("Motor durumu değiştirilemedi: " + e.message, "error");
    } finally {
        btn.disabled = false;
    }
}

function renderLiveTrading(data) {
    if (!data) return;
    
    // Update State if changed externally
    if (data.is_active !== isLiveTradingActive) {
        isLiveTradingActive = data.is_active;
        const btn = document.getElementById('btn-toggle-live');
        if (isLiveTradingActive) {
            btn.innerHTML = '<i class="fa-solid fa-stop"></i> Durdur';
            btn.className = 'btn btn-danger';
            document.getElementById('live-status-text').innerText = 'ÇALIŞIYOR';
            document.getElementById('live-status-text').style.color = 'var(--color-buy)';
        } else {
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Başlat';
            btn.className = 'btn btn-secondary';
            document.getElementById('live-status-text').innerText = 'DURDURULDU';
            document.getElementById('live-status-text').style.color = 'var(--color-warning)';
        }
    }
    
    document.getElementById('live-balance').innerText = formatPrice(data.balance) + ' TL';
    document.getElementById('live-equity').innerText = formatPrice(data.equity) + ' TL';
    
    const pnlEl = document.getElementById('live-pnl');
    pnlEl.innerText = formatPrice(data.open_pnl) + ' TL';
    pnlEl.className = 'stat-value ' + (data.open_pnl > 0 ? 'change-up' : (data.open_pnl < 0 ? 'change-down' : ''));
    
    if (data.daily_drawdown_halt) {
        document.getElementById('live-status-text').innerText = 'HALT (%3 ZARAR KESİLDİ)';
        document.getElementById('live-status-text').style.color = 'var(--color-sell)';
    }

    // Positions Table
    const tbody = document.getElementById('live-positions-tbody');
    if (!data.positions || data.positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Aktif pozisyon yok.</td></tr>';
    } else {
        tbody.innerHTML = data.positions.map(pos => `
            <tr>
                <td><strong>${pos.symbol}</strong></td>
                <td><span class="badge badge-${pos.side === 'LONG' ? 'buy' : 'sell'}">${pos.side}</span></td>
                <td>${formatPrice(pos.entry_price)}</td>
                <td>${formatPrice(pos.current_price)}</td>
                <td class="${pos.pnl > 0 ? 'change-up' : 'change-down'}">${formatPrice(pos.pnl)} TL</td>
                <td class="${pos.pnl_percent > 0 ? 'change-up' : 'change-down'}">%${pos.pnl_percent.toFixed(2)}</td>
            </tr>
        `).join('');
    }
    
    // Logs
    const consoleBox = document.getElementById('live-console-box');
    if (data.recent_logs && data.recent_logs.length > 0) {
        const currentCount = consoleBox.childElementCount;
        const lastLogText = consoleBox.lastElementChild ? consoleBox.lastElementChild.innerText : '';
        const newLastLog = data.recent_logs[data.recent_logs.length - 1];
        
        if (currentCount !== data.recent_logs.length || lastLogText !== newLastLog) {
            consoleBox.innerHTML = data.recent_logs.map(log => `<div>${log}</div>`).join('');
            consoleBox.scrollTop = consoleBox.scrollHeight;
        }
    }
}

// ═══════════════════════════════════════════════
// GAP HUNTER
// ═══════════════════════════════════════════════

async function fetchGapHunter() {
    const container = document.getElementById('gap-hunter-results');
    const btn = document.getElementById('btn-refresh-gap');
    
    if (!container || !btn) return;
    
    // UI Update
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Taranıyor...';
    container.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Piyasa verileri analiz ediliyor, lütfen bekleyin...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/api/gap-hunter`);
        const data = await response.json();
        
        if (data.status === 'success') {
            if (data.candidates && data.candidates.length > 0) {
                container.innerHTML = data.candidates.map(c => {
                    let scoreDesc = "";
                    if (c.score >= 80) {
                        scoreDesc = "<span style='color:#10b981; font-weight:bold;'><i class='fa-solid fa-fire'></i> ALIM BÖLGESİ (Tavan Adayı)</span> - Ertesi gün gap-up yapma ihtimali çok yüksek.";
                    } else if (c.score >= 50) {
                        scoreDesc = "<span style='color:#f59e0b;'><i class='fa-solid fa-eye'></i> Yakın Takip (Potansiyel Var)</span> - İzlemeye değer ancak tam onay almamış.";
                    } else {
                        scoreDesc = "<span style='color:#ef4444;'><i class='fa-solid fa-ban'></i> ALINMAZ (Zayıf Kapanış)</span> - Sadece listeyi görmeniz için eklenmiştir.";
                    }
                    
                    return `
                    <div class="signal-card" style="border-left: 4px solid #FFD700; background: rgba(255, 215, 0, 0.05);">
                        <div class="sig-header">
                            <span class="sig-symbol">${c.symbol}</span>
                            <span class="sig-badge" style="background: rgba(255, 215, 0, 0.2); color: #FFD700; font-weight: bold;">SKOR: ${c.score} / 100</span>
                        </div>
                        <div class="sig-body">
                            <div class="sig-detail" style="margin-bottom: 10px; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">
                                ${scoreDesc}
                            </div>
                            <div class="sig-detail"><span>Günün Zirvesine Yakınlık:</span> <strong>%${(c.close_ratio * 100).toFixed(1)}</strong></div>
                            <div class="sig-detail"><span>Hacim İvmesi:</span> <strong>${c.vol_ratio.toFixed(1)}x Ort.</strong></div>
                            <div class="sig-detail"><span>Günlük Değişim:</span> <strong>%${c.pct_change.toFixed(2)}</strong></div>
                            <div class="sig-detail" style="margin-top: 10px; font-size: 0.85rem; color: #a1a1aa;">
                                ${c.details.map(d => `<i class="fa-solid fa-check"></i> ${d}`).join('<br>')}
                            </div>
                        </div>
                        <div class="sig-footer">
                            <button class="btn btn-sm" onclick="selectActiveCoin('${c.symbol}.IS'); switchTab('dashboard');" style="width: 100%; border: 1px solid #FFD700; color: #FFD700; background: transparent;">
                                Grafikte İncele
                            </button>
                        </div>
                    </div>
                `}).join('');
            } else {
                container.innerHTML = '<div class="text-center text-muted" style="padding: 30px;">Şu an için kriterlere uyan (Tavan/Gap potansiyeli yüksek) hisse bulunamadı. Lütfen kapanışa (17:50) daha yakın bir saatte tekrar deneyin.</div>';
            }
        } else {
            throw new Error("Veri çekilemedi");
        }
    } catch (error) {
        console.error("Gap Hunter error:", error);
        container.innerHTML = `<div class="text-center" style="color: #ef4444; padding: 20px;">
            <i class="fa-solid fa-triangle-exclamation"></i> Veriler alınırken bir hata oluştu.
        </div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Şimdi Tara';
    }
}
