import ccxt
import time

def test():
    print("Initializing ccxt.okx...")
    exchange = ccxt.okx({
        'enableRateLimit': True
    })
    
    # Try fetching BTC/USDT ticker
    try:
        print("Fetching BTC/USDT ticker...")
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"SUCCESS! Last price: {ticker['last']}")
    except Exception as e:
        print(f"FAILED to fetch ticker: {e}")
        
    # Try loading markets
    try:
        print("Loading markets...")
        markets = exchange.load_markets()
        print(f"SUCCESS! Number of markets: {len(markets)}")
    except Exception as e:
        print(f"FAILED to load markets: {e}")

    # Try fetching candles
    try:
        print("Fetching BTC/USDT 15m candles...")
        candles = exchange.fetch_ohlcv('BTC/USDT', timeframe='15m', limit=5)
        print(f"SUCCESS! Fetched {len(candles)} candles.")
        for c in candles:
            print(f"Time: {c[0]}, Open: {c[1]}, Close: {c[4]}")
    except Exception as e:
        print(f"FAILED to fetch candles: {e}")

if __name__ == "__main__":
    test()
