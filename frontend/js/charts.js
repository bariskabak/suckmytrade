class TradingChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        
        this.init();
    }

    init() {
        if (!this.container) return;

        // Container içeriğini temizle
        this.container.innerHTML = '';

        if (typeof LightweightCharts === 'undefined') {
            console.error("LightweightCharts CDN is not available.");
            this.container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); text-align: center; padding: 2rem;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; color: var(--color-sell); margin-bottom: 0.5rem;"></i>
                    <p style="font-weight: 600;">Grafik Yüklenemedi</p>
                    <p style="font-size: 0.8rem; margin-top: 0.25rem;">TradingView grafik kütüphanesi yüklenemedi. İnternet bağlantınızı kontrol edin.</p>
                </div>
            `;
            return;
        }

        // Grafik genişlik ve yüksekliği
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 350;

        // Grafik Oluşturma ve Premium Stil Ayarları
        this.chart = LightweightCharts.createChart(this.container, {
            width: width,
            height: height,
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: '#9ca3af',
                fontSize: 11,
                fontFamily: 'Outfit, sans-serif',
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: '#6b7280',
                    width: 1,
                    style: 3, // dashed
                    labelBackgroundColor: '#1f2937',
                },
                horzLine: {
                    color: '#6b7280',
                    width: 1,
                    style: 3,
                    labelBackgroundColor: '#1f2937',
                },
            },
            rightPriceScale: {
                borderColor: 'rgba(255, 255, 255, 0.08)',
                autoScale: true,
            },
            timeScale: {
                borderColor: 'rgba(255, 255, 255, 0.08)',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        // Candlestick Serisi
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#00ff88',
            downColor: '#ff4a5a',
            borderUpColor: '#00ff88',
            borderDownColor: '#ff4a5a',
            wickUpColor: '#00ff88',
            wickDownColor: '#ff4a5a',
        });

        // Hacim Serisi (Grafik altında yarı şeffaf panel)
        this.volumeSeries = this.chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // Ayrı ölçekte (overlay) göstermek için
        });

        // Hacim serisini grafiğin alt kısmına çekme
        this.volumeSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        // Boyutlandırma İzleyicisi (Resize observer)
        window.addEventListener('resize', () => {
            if (this.chart && this.container) {
                this.chart.resize(this.container.clientWidth, this.container.clientHeight);
            }
        });
    }

    setData(candleData) {
        if (!this.chart || !this.candleSeries) return;

        // Mum verilerini yükle
        this.candleSeries.setData(candleData);

        // Hacim verilerini yükle
        const volumeData = candleData.map(c => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(0, 255, 136, 0.25)' : 'rgba(255, 74, 90, 0.25)'
        }));
        this.volumeSeries.setData(volumeData);

        // Grafiği sığdır
        this.chart.timeScale().fitContent();
    }

    updateData(candle) {
        if (!this.chart || !this.candleSeries) return;
        this.candleSeries.update(candle);
        this.volumeSeries.update({
            time: candle.time,
            value: candle.volume,
            color: candle.close >= candle.open ? 'rgba(0, 255, 136, 0.25)' : 'rgba(255, 74, 90, 0.25)'
        });
    }
}
window.TradingChart = TradingChart;
