import logging
import os
import requests

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

KUCOIN_SYMBOLS = {'AKT', 'KCS'}

def get_crypto_price(symbol):
    if symbol in KUCOIN_SYMBOLS:
        return get_crypto_price_kucoin(symbol)
    if symbol == 'GST':
        return get_gst_bsc_price_from_coinmarketcap()
    else:
        return get_crypto_price_binance(symbol)

def get_crypto_price_coingecko(symbol, api_key):
    api_symbol = ASSET_TO_COINGECKO_API_ID.get(symbol.upper())
    if not api_symbol:
        logging.error(f"Symbol '{symbol}' not found in mapping")
        return None

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={api_symbol}&vs_currencies=usd&x_cg_demo_api_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        logging.info(f"Response from CoinGecko: {data}")
        return data[api_symbol]['usd'] if api_symbol in data else None
    else:
        logging.error(f"Error fetching price for {symbol}: {response.status_code}")
        return None
    
def get_crypto_price_binance(symbol):
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
            logging.error(f"Error fetching price for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
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
                logging.error(f"Error from KuCoin API: {data.get('msg')}")
                return None
        else:
            logging.error(f"Error fetching price for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
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
                logging.error(f"Symbol '{symbol}' not found in CoinMarketCap data")
                return None
        else:
            logging.error(f"Error fetching price for {symbol}: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
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
            logging.error(f"Error fetching price for GST on BSC: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        logging.error(f"Request exception occurred: {e}")
        return None