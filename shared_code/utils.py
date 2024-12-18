import logging
import os
import json
from telegram import Bot
import asyncio
import requests
from azure.storage.fileshare import ShareFileClient

# Asset mapping dictionary
ASSET_TO_API_ID = {
    "BTC": "bitcoin",
    "DOT": "polkadot",
    # ... (rest of the mapping)
}

async def send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message):
    if telegram_enabled:
        bot = Bot(token=telegram_token)
        for chat_id in telegram_chat_ids:
            await bot.send_message(chat_id=chat_id, text=f"{message}")

def get_crypto_price(symbol, api_key):
    api_symbol = ASSET_TO_API_ID.get(symbol.upper())
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

def get_alerts_from_azure(file_name):
    try:
        share_name = os.environ["AZURE_STORAGE_SHARE_NAME"]
        storage_account_name = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT"]
        account_key = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT_KEY"]
        file_url = f"https://{storage_account_name}.file.core.windows.net/"
        
        file_client = ShareFileClient(
            account_url=file_url,
            credential=account_key,
            share_name=share_name,
            file_path=file_name)
        
        download_stream = file_client.download_file()
        file_content = download_stream.readall().decode('utf-8')
        return json.loads(file_content)
    except Exception as e:
        logging.error(f"Error in get_alerts_from_azure: {e}")
        return None

def save_alerts_to_azure(file_name, alerts_content):
    try:
        share_name = os.environ["AZURE_STORAGE_SHARE_NAME"]
        storage_account_name = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT"]
        account_key = os.environ["AZURE_STORAGE_STORAGE_ACCOUNT_KEY"]
        file_url = f"https://{storage_account_name}.file.core.windows.net/"
        
        file_client = ShareFileClient(
            account_url=file_url,
            credential=account_key,
            share_name=share_name,
            file_path=file_name)
        
        json_content = json.dumps(alerts_content, indent=4).encode('utf-8')
        file_client.upload_file(json_content)
        logging.info(f"Alerts successfully saved to Azure Storage: {file_name}")
        
    except Exception as e:
        logging.error(f"Error in save_alerts_to_azure: {e}") 