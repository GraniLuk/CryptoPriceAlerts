import logging
import os
import requests
from telegram_logging_handler import app_logger
from dataclasses import dataclass
from typing import Optional
from shared_code.price_cache import price_cache

@dataclass
class CandleData:
    open: float
    high: float
    low: float
    close: float
    
    def meets_condition(self, price: float, operator: str) -> bool:
        """Check if the candle meets the alert condition"""
        if operator == ">":
            return self.high > price
        elif operator == "<":
            return self.low < price
        elif operator == "=":
            # For equals, we check if the price was ever touched within the candle
            return self.low <= price <= self.high
        return False

# Asset mapping dictionary
ASSET_TO_COINGECKO_API_ID = {
    "BTC": "bitcoin",
    "DOT": "polkadot",
    "BNB": "binancecoin",
    "MATIC": "matic-network",
    "FLOW": "flow",
    "ATOM": "cosmos",
    "OSMO": "osmosis",
    "ETH": "ethereum",
    "BUSD": "busd",
    "CHZ": "chiliz",
    "HBAR": "hedera-hashgraph",
    "USDT": "tether",
    "XRP": "ripple",
    "SHIB": "shiba-inu",
    "KCS": "kucoin-shares",
    "OLE": "openleverage",
    "LINK": "chainlink",
    "PAXG": "pax-gold",
    "RUNE": "thorchain",
    "SAND": "the-sandbox",
    "SOLO": "solo-coin",
    "BETH": "binance-eth",
    "ALGO": "algorand",
    "AKT": "akash-network",
    "KUJI": "kujira",
    "DYM": "dymension",
    "GMT": "stepn",
    "GST": "green-satoshi-token-bsc"
}

KUCOIN_SYMBOLS = {'AKT', 'KCS', 'DYM', 'VIRTUAL'}

def get_crypto_price(symbol):
    """Legacy function that gets just the current price - maintained for compatibility"""
    # First check the cache
    cached_price = price_cache.get_price(symbol)
    if cached_price is not None:
        app_logger.info(f"Using cached price for {symbol}: {cached_price}")
        return cached_price
    
    # If not in cache, fetch from API
    price = None
    if symbol in KUCOIN_SYMBOLS:
        price = get_crypto_price_kucoin(symbol)
    elif symbol == 'GST':
        price = get_gst_bsc_price_from_coinmarketcap()
    else:
        price = get_crypto_price_binance(symbol)
    
    # Cache the result if we got a valid price
    if price is not None:
        price_cache.set_price(symbol, price)
        
    return price

def get_crypto_candle(symbol) -> Optional[CandleData]:
    """Get 5-minute candle data for a symbol with caching"""
    # First check the cache for the current price - we'll still need to 
    # fetch the candle data for high/low, but this avoids duplicate API calls
    cached_price = price_cache.get_price(symbol)
    
    candle = None
    
    if symbol in KUCOIN_SYMBOLS:
        candle = get_crypto_candle_kucoin(symbol)
    elif symbol == 'GST':
        # For GST we have only the current price from CMC, so we create a candle with the same value
        price = cached_price if cached_price is not None else get_gst_bsc_price_from_coinmarketcap()
        if price:
            candle = CandleData(open=price, high=price, low=price, close=price)
    else:
        candle = get_crypto_candle_binance(symbol)
    
    # If we got valid candle data, cache the close price
    if candle:
        price_cache.set_price(symbol, candle.close)
    # If we have a cached price but couldn't get candle data, create a candle with the cached price
    elif cached_price is not None:
        app_logger.info(f"Using cached price to create candle for {symbol}: {cached_price}")
        candle = CandleData(open=cached_price, high=cached_price, low=cached_price, close=cached_price)
    
    return candle

def get_crypto_price_coingecko(symbol, api_key):
    api_symbol = ASSET_TO_COINGECKO_API_ID.get(symbol.upper())
    if not api_symbol:
        app_logger.error(f"Symbol '{symbol}' not found in mapping")
        return None

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={api_symbol}&vs_currencies=usd&x_cg_demo_api_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        logging.info(f"Response from CoinGecko: {data}")
        return data[api_symbol]['usd'] if api_symbol in data else None
    else:
        app_logger.error(f"Error fetching price for {symbol}: {response.status_code}")
        return None
    
def get_crypto_price_binance(symbol):
    """Legacy function - gets only the current price"""
    # Binance uses a specific format for symbols, usually like "BTCUSDT"
    binance_symbol = f"{symbol.upper()}USDT"  # Adjust for USD pairing; you may need different pairs.
    
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from Binance: {data}")
            return float(data['price']) if 'price' in data else None
        else:
            app_logger.error(f"Error fetching price for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None

def get_crypto_candle_binance(symbol) -> Optional[CandleData]:
    """Gets 5-minute candle data from Binance"""
    binance_symbol = f"{symbol.upper()}USDT"
    
    # Fetch 5-minute klines (candlestick data)
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=5m&limit=1"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0:
                # Binance kline format: [Open time, Open, High, Low, Close, Volume, ...]
                candle = data[0]
                return CandleData(
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4])
                )
            else:
                app_logger.error(f"No candle data returned for {symbol}")
                return None
        else:
            app_logger.error(f"Error fetching candle for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception during candle fetch: {e}")
        return None
    
def get_crypto_price_kucoin(symbol):
    kucoin_symbol = f"{symbol.upper()}-USDT"  # KuCoin uses a dash to separate trading pairs.
    
    url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={kucoin_symbol}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '200000':
                logging.info(f"Response from KuCoin: {data}")
                return float(data['data']['price']) if 'data' in data and 'price' in data['data'] else None
            else:
                app_logger.error(f"Error from KuCoin API: {data.get('msg')}")
                return None
        else:
            app_logger.error(f"Error fetching price for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None
    
def get_crypto_candle_kucoin(symbol) -> Optional[CandleData]:
    """Gets 5-minute candle data from KuCoin"""
    kucoin_symbol = f"{symbol.upper()}-USDT"
    
    # Fetch 5-minute klines (candlestick data)
    # KuCoin API format: /api/v1/market/candles?type=5min&symbol=<symbol>&startAt=<time_in_seconds>
    url = f"https://api.kucoin.com/api/v1/market/candles?type=5min&symbol={kucoin_symbol}&limit=1"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data.get('code') == '200000' and data.get('data') and len(data['data']) > 0:
                # KuCoin candle format: [timestamp, open, close, high, low, volume, turnover]
                candle = data['data'][0]
                return CandleData(
                    open=float(candle[1]),
                    high=float(candle[3]),  # High is at index 3 in KuCoin response
                    low=float(candle[4]),   # Low is at index 4 in KuCoin response
                    close=float(candle[2])  # Close is at index 2 in KuCoin response
                )
            else:
                app_logger.error(f"No candle data returned for {symbol} from KuCoin")
                return None
        else:
            app_logger.error(f"Error fetching candle for {symbol} from KuCoin: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception during KuCoin candle fetch: {e}")
        return None

def get_crypto_price_coinmarketcap(symbol, api_key):
    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key,
    }
    params = {
        'symbol': symbol.upper(),
        'convert': 'USD'
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from CoinMarketCap: {data}")
            if 'data' in data and symbol.upper() in data['data']:
                return float(data['data'][symbol.upper()]['quote']['USD']['price'])
            else:
                app_logger.error(f"Symbol '{symbol}' not found in CoinMarketCap data")
                return None
        else:
            app_logger.error(f"Error fetching price for {symbol}: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None
    
def get_gst_bsc_price_from_coinmarketcap():
    api_key = os.environ["COINMARKETCAP_API_KEY"]
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key,
    }
    
    params = {
        'id': '20236',  # Use the unique CoinMarketCap ID for GST on BSC
        'convert': 'USD'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from CoinMarketCap: {data}")
            return float(data['data']['20236']['quote']['USD']['price'])  # Extract price using ID
        else:
            app_logger.error(f"Error fetching price for GST on BSC: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None