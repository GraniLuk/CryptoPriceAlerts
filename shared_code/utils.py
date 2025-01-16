import logging
import os
import json
from telegram import Bot
import requests
from azure.storage.fileshare import ShareServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from datetime import datetime

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

async def send_telegram_message(telegram_enabled, telegram_token, chat_id, message):
    if not telegram_enabled:
        return
        
    bot = Bot(token=telegram_token)
    async with bot:  # This handles cleanup automatically
        await bot.send_message(chat_id=chat_id.strip(), text=message)


def get_crypto_price(symbol, api_key):
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

def get_alerts_from_azure(file_name):
    try:
        share_name = os.environ["AZURE_STORAGE_SHARE_NAME"]
        storage_account_name = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT"]
        account_key = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT_KEY"]
        
        # Create credential with account name
        credential = AzureNamedKeyCredential(storage_account_name, account_key)
        
        # Create service client
        service_client = ShareServiceClient(
            account_url=f"https://{storage_account_name}.file.core.windows.net",
            credential=credential
        )
        
        # Get share client
        share_client = service_client.get_share_client(share_name)
        
        # Get file client
        file_client = share_client.get_file_client(file_name)
        
        # Download and process file
        download_stream = file_client.download_file()
        file_content = download_stream.readall().decode('utf-8')
        
        alerts = json.loads(file_content)
        return alerts
    except Exception as e:
        logging.error(f"Error in get_alerts_from_azure: {e}")
        return None

def save_alerts_to_azure(file_name, alerts_content):
    try:
        share_name = os.environ["AZURE_STORAGE_SHARE_NAME"]
        storage_account_name = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT"]
        account_key = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT_KEY"]
        
        # Create credential with account name
        credential = AzureNamedKeyCredential(storage_account_name, account_key)
        
        # Create service client
        service_client = ShareServiceClient(
            account_url=f"https://{storage_account_name}.file.core.windows.net",
            credential=credential
        )
        
        # Get share client
        share_client = service_client.get_share_client(share_name)
        
        # Get file client
        file_client = share_client.get_file_client(file_name)
        
        # Convert alerts content to JSON string bytes
        json_content = json.dumps(alerts_content, indent=4).encode('utf-8')
        
        # Upload the updated content back to Azure Storage
        file_client.upload_file(json_content)
        logging.info(f"Alerts successfully saved to Azure Storage: {file_name}")
        
    except Exception as e:
        logging.error(f"Error in save_alerts_to_azure: {e}") 

