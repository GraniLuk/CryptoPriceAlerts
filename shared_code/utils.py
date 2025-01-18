import logging
import os
import json
from telegram import Bot
from azure.storage.fileshare import ShareServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from telegram_logging_handler import app_logger

async def send_telegram_message(telegram_enabled, telegram_token, chat_id, message):
    if not telegram_enabled:
        return
        
    bot = Bot(token=telegram_token)
    async with bot:  # This handles cleanup automatically
        await bot.send_message(chat_id=chat_id.strip(), text=message)

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
        app_logger.error(f"Error in get_alerts_from_azure: {e}")
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
        app_logger.error(f"Error in save_alerts_to_azure: {e}") 

