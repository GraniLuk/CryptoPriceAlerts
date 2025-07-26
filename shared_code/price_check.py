import logging
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import requests

from shared_code.price_cache import price_cache
from telegram_logging_handler import app_logger


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
    "GST": "green-satoshi-token-bsc",
}

KUCOIN_SYMBOLS = {"AKT", "KCS", "DYM", "VIRTUAL"}

# Timeframe mapping for different exchanges
TIMEFRAME_MAPPING = {
    "binance": {
        "1m": "1m", "5m": "5m", "15m": "15m", 
        "1h": "1h", "4h": "4h", "1d": "1d"
    },
    "kucoin": {
        "1m": "1min", "5m": "5min", "15m": "15min",
        "1h": "1hour", "4h": "4hour", "1d": "1day"
    }
}


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
    elif symbol == "GST":
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
    elif symbol == "GST":
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
        candle = CandleData(
            open=cached_price, high=cached_price, low=cached_price, close=cached_price
        )

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
        return data[api_symbol]["usd"] if api_symbol in data else None
    else:
        app_logger.error(f"Error fetching price for {symbol}: {response.status_code}")
        return None


def get_crypto_price_binance(symbol):
    """Legacy function - gets only the current price"""
    # Binance uses a specific format for symbols, usually like "BTCUSDT"
    binance_symbol = (
        f"{symbol.upper()}USDT"  # Adjust for USD pairing; you may need different pairs.
    )

    url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from Binance: {data}")
            return float(data["price"]) if "price" in data else None
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
                    close=float(candle[4]),
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
            if data.get("code") == "200000":
                logging.info(f"Response from KuCoin: {data}")
                return (
                    float(data["data"]["price"])
                    if "data" in data and "price" in data["data"]
                    else None
                )
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

            if data.get("code") == "200000" and data.get("data") and len(data["data"]) > 0:
                # KuCoin candle format: [timestamp, open, close, high, low, volume, turnover]
                candle = data["data"][0]
                return CandleData(
                    open=float(candle[1]),
                    high=float(candle[3]),  # High is at index 3 in KuCoin response
                    low=float(candle[4]),  # Low is at index 4 in KuCoin response
                    close=float(candle[2]),  # Close is at index 2 in KuCoin response
                )
            else:
                app_logger.error(f"No candle data returned for {symbol} from KuCoin")
                return None
        else:
            app_logger.error(
                f"Error fetching candle for {symbol} from KuCoin: {response.status_code}"
            )
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception during KuCoin candle fetch: {e}")
        return None


def get_crypto_price_coinmarketcap(symbol, api_key):
    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": api_key,
    }
    params = {"symbol": symbol.upper(), "convert": "USD"}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from CoinMarketCap: {data}")
            if "data" in data and symbol.upper() in data["data"]:
                return float(data["data"][symbol.upper()]["quote"]["USD"]["price"])
            else:
                app_logger.error(f"Symbol '{symbol}' not found in CoinMarketCap data")
                return None
        else:
            app_logger.error(
                f"Error fetching price for {symbol}: {response.status_code} - {response.text}"
            )
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None


def get_gst_bsc_price_from_coinmarketcap():
    api_key = os.environ["COINMARKETCAP_API_KEY"]
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": api_key,
    }

    params = {"id": "20236", "convert": "USD"}  # Use the unique CoinMarketCap ID for GST on BSC

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response from CoinMarketCap: {data}")
            return float(data["data"]["20236"]["quote"]["USD"]["price"])  # Extract price using ID
        else:
            app_logger.error(
                f"Error fetching price for GST on BSC: {response.status_code} - {response.text}"
            )
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception occurred: {e}")
        return None


def get_crypto_candle_historical(symbol: str, timeframe: str = "5m", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data with configurable timeframe"""
    try:
        if symbol in KUCOIN_SYMBOLS:
            return get_crypto_candle_historical_kucoin(symbol, timeframe, limit)
        elif symbol == "GST":
            # GST only has current price, so we'll create mock historical data
            current_price = get_gst_bsc_price_from_coinmarketcap()
            if current_price:
                return create_mock_historical_data(current_price, timeframe, limit)
            return None
        else:
            return get_crypto_candle_historical_binance(symbol, timeframe, limit)
    except Exception as e:
        app_logger.error(f"Error fetching historical candles for {symbol}: {e}")
        return None


def get_crypto_candle_historical_binance(symbol: str, timeframe: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data from Binance with configurable timeframe"""
    binance_symbol = f"{symbol.upper()}USDT"
    binance_timeframe = TIMEFRAME_MAPPING["binance"].get(timeframe, "5m")
    
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={binance_timeframe}&limit={limit}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0:
                candles = []
                for candle in data:
                    # Binance kline format: [Open time, Open, High, Low, Close, Volume, ...]
                    candles.append({
                        'timestamp': datetime.fromtimestamp(int(candle[0]) / 1000),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })
                return candles
            else:
                app_logger.error(f"No historical candle data returned for {symbol}")
                return None
        else:
            app_logger.error(f"Error fetching historical candles for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception during historical candle fetch: {e}")
        return None


def get_crypto_candle_historical_kucoin(symbol: str, timeframe: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data from KuCoin with configurable timeframe"""
    kucoin_symbol = f"{symbol.upper()}-USDT"
    kucoin_timeframe = TIMEFRAME_MAPPING["kucoin"].get(timeframe, "5min")
    
    url = f"https://api.kucoin.com/api/v1/market/candles?type={kucoin_timeframe}&symbol={kucoin_symbol}&limit={limit}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data.get("code") == "200000" and data.get("data") and len(data["data"]) > 0:
                candles = []
                for candle in data["data"]:
                    # KuCoin candle format: [timestamp, open, close, high, low, volume, turnover]
                    candles.append({
                        'timestamp': datetime.fromtimestamp(int(candle[0])),
                        'open': float(candle[1]),
                        'high': float(candle[3]),
                        'low': float(candle[4]),
                        'close': float(candle[2]),
                        'volume': float(candle[5])
                    })
                # Sort by timestamp (oldest first) for consistent processing
                candles.sort(key=lambda x: x['timestamp'])
                return candles
            else:
                app_logger.error(f"No historical candle data returned for {symbol} from KuCoin")
                return None
        else:
            app_logger.error(f"Error fetching historical candles for {symbol} from KuCoin: {response.status_code}")
            return None
    except requests.RequestException as e:
        app_logger.error(f"Request exception during KuCoin historical candle fetch: {e}")
        return None


def create_mock_historical_data(current_price: float, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    """Create mock historical data for symbols that only have current price (like GST)"""
    candles = []
    
    # Calculate time delta based on timeframe
    time_deltas = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1)
    }
    
    delta = time_deltas.get(timeframe, timedelta(minutes=5))
    current_time = datetime.now()
    
    # Create historical data with slight price variations (±2%)
    import random
    for i in range(limit):
        timestamp = current_time - (delta * (limit - i))
        
        # Add small random variations to simulate price movement
        variation = random.uniform(-0.02, 0.02)  # ±2%
        price_with_variation = current_price * (1 + variation)
        
        # Create OHLC with small variations
        high_variation = random.uniform(0, 0.01)  # 0-1% higher
        low_variation = random.uniform(-0.01, 0)  # 0-1% lower
        
        candles.append({
            'timestamp': timestamp,
            'open': price_with_variation,
            'high': price_with_variation * (1 + high_variation),
            'low': price_with_variation * (1 + low_variation),
            'close': price_with_variation,
            'volume': 0.0  # No volume data available
        })
    
    return candles


def get_crypto_candle_enhanced(symbol: str, timeframe: str = "5m") -> Optional[CandleData]:
    """Enhanced version of get_crypto_candle with timeframe support"""
    # For backwards compatibility, if timeframe is 5m, use existing method
    if timeframe == "5m":
        return get_crypto_candle(symbol)
    
    # For other timeframes, get the latest candle from historical data
    historical_data = get_crypto_candle_historical(symbol, timeframe, 1)
    
    if historical_data and len(historical_data) > 0:
        latest_candle = historical_data[-1]
        return CandleData(
            open=latest_candle['open'],
            high=latest_candle['high'],
            low=latest_candle['low'],
            close=latest_candle['close']
        )
    
    # Fallback to current method if historical data unavailable
    return get_crypto_candle(symbol)
