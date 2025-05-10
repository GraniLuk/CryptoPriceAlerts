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
        # Use empty local alerts if Azure storage variables are not set
        share_name = os.environ.get("AZURE_STORAGE_SHARE_NAME")
        storage_account_name = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT")
        account_key = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT_KEY")
        
        # If any of these are missing, read from local alerts.json file for development
        if not all([share_name, storage_account_name, account_key]):
            app_logger.warning("Azure Storage credentials not set, using local alerts.json file for development")
            try:
                local_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alerts.json")
                with open(local_file_path, 'r') as f:
                    alerts = json.load(f)
                    app_logger.info(f"Loaded {len(alerts)} alerts from local file")
                    return alerts
            except Exception as e:
                app_logger.error(f"Error reading local alerts file: {e}")
                return []
        
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
        share_name = os.environ.get("AZURE_STORAGE_SHARE_NAME")
        storage_account_name = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT")
        account_key = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT_KEY")
        
        # If any of these are missing, write to local alerts.json file for development
        if not all([share_name, storage_account_name, account_key]):
            app_logger.warning("Azure Storage credentials not set, saving to local alerts.json file")
            try:
                local_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alerts.json")
                with open(local_file_path, 'w') as f:
                    json.dump(alerts_content, f, indent=4)
                app_logger.info(f"Saved {len(alerts_content)} alerts to local file")
                return
            except Exception as e:
                app_logger.error(f"Error writing to local alerts file: {e}")
                return
        
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

