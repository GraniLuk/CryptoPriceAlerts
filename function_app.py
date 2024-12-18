import logging
import configparser
from telegram import Bot
import asyncio
from datetime import datetime
import azure.functions as func
import requests
import json
from azure.storage.fileshare import ShareFileClient
import locale

app = func.FunctionApp()

    # Send to Telegram if enabled
async def send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message):
    if telegram_enabled:
        bot = Bot(token=telegram_token)
        for chat_id in telegram_chat_ids:
            await bot.send_message(chat_id=chat_id, text=f"{message}")

# Alert entity class
class Alert:
    def __init__(self, symbol, price, operator, description, triggered_date):
        self.symbol = symbol
        self.price = float(price)
        self.operator = operator
        self.description = description
        self.triggered_date = triggered_date

# Define the mapping dictionary
ASSET_TO_API_ID = {
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
    "COMP": "compound-governance-token",
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
    "RMRK": "rmrk",
    "DYM": "dymension",
    "GMT": "stepn",
    "GST": "green-satoshi-token-bsc"
}

def get_crypto_price(symbol, api_key):
    # Using CoinGecko API
    api_symbol = ASSET_TO_API_ID.get(symbol.upper())
    if not api_symbol:
        logging.error(f"Symbol '{symbol}' not found in mapping")
        return None

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={api_symbol}&vs_currencies=usd&x_cg_demo_api_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        logging.info(f"Response from CoinGecko: {data}")
        if api_symbol in data:
            return data[api_symbol]['usd']
        else:
            logging.error(f"Symbol '{api_symbol}' not found in response")
            return None
    else:
        logging.error(f"Error fetching price for {symbol}: {response.status_code}")
        return None

def get_alerts_from_azure(file_name):
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        share_name = config.get('AZURE_STORAGE', 'ShareName')
        storage_account_name = config.get('AZURE_STORAGE', 'StorageAccountName')
        account_key = config.get('AZURE_STORAGE', 'StorageAccountKey')
        file_url = f"https://{storage_account_name}.file.core.windows.net/"
        
        # Create a ShareFileClient
        file_client = ShareFileClient(
            account_url=file_url,
            credential=account_key,
            share_name=share_name,
            file_path=file_name) 
        
        # Download the file content
        download_stream = file_client.download_file()
        file_content = download_stream.readall().decode('utf-8')
        
        # Parse the JSON content
        alerts = json.loads(file_content)
        return alerts
    except Exception as e:
        print(f"Error in get_alerts_from_azure: {e}")
        return None

def save_alerts_to_azure(file_name, alerts_content):
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        share_name = config.get('AZURE_STORAGE', 'ShareName')
        storage_account_name = config.get('AZURE_STORAGE', 'StorageAccountName')
        account_key = config.get('AZURE_STORAGE', 'StorageAccountKey')
        file_url = f"https://{storage_account_name}.file.core.windows.net/"
        
        # Create a ShareFileClient
        file_client = ShareFileClient(
            account_url=file_url,
            credential=account_key,
            share_name=share_name,
            file_path=file_name) 
        
        # Convert alerts content to JSON string bytes
        json_content = json.dumps(alerts_content, indent=4).encode('utf-8')
        
        # Upload the updated content back to Azure Storage
        file_client.upload_file(json_content)
        print(f"Alerts successfully saved to Azure Storage: {file_name}")
        
    except Exception as e:
        logging.error(f"Error in save_alerts_to_azure: {e}")

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=True,
                   use_monitor=False)
def AlertsFunctionGrani(myTimer: func.TimerRequest) -> None:
    
    try:
        # Get connection string and bot token from app settings
        config = configparser.ConfigParser()
        config.read('config.ini')
        telegram_enabled = config.getboolean('TELEGRAM', 'Enabled')
        telegram_token = config.get('TELEGRAM', 'Token')
        telegram_chat_ids = config.get('TELEGRAM', 'ChatIDs').split(',')
        coingecko_api_key = config.get('COINGECKO', 'ApiKey')

        # Fetch alerts from Azure Storage File Shares
        alerts = get_alerts_from_azure('alerts.json')
        
        if alerts is None:
            print("Failed to get alerts from Azure Storage.")
            return
        
        # Filter out alerts that have already been triggered
        alerts = [alert for alert in alerts if not alert['triggered_date']]
        
        any_alert_triggered = False
        
        for alert in alerts:
            current_price = get_crypto_price(alert['symbol'], coingecko_api_key)
            
            if current_price:
                condition_met = False
                
                if alert['operator'] == ">" and current_price > alert['price']:
                    condition_met = True
                elif alert['operator'] == "<" and current_price < alert['price']:
                    condition_met = True
                
                if condition_met:
                    message = f"🚨 Alert for {alert['symbol']}!\n"
                    message += f"Current price: ${current_price}\n"
                    message += f"Alert condition: ${alert['price']} {alert['operator']}\n"
                    message += f"Description: {alert['description']}"
                    # Update triggered_date
                    alert['triggered_date'] = datetime.now().isoformat()
                    any_alert_triggered = True
                    
                    # Send message to Telegram
                    asyncio.run(send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message))
                    logging.info(f"Alert sent for {alert['symbol']}")
        
        # Save updated alerts back to the Azure Storage File Share only if any alert was triggered
        if any_alert_triggered:
            save_alerts_to_azure('alerts.json', alerts)
                    
    except Exception as e:
        logging.error(f"Error in AlertsFunction: {str(e)}")

def insert_new_alert_grani_internal(symbol: str, price: float, operator: str, description: str) -> None:
    """
    Insert a new alert into alarms.json
    
    Args:
        symbol (str): Trading symbol
        price (float): Target price
        operator (str): Comparison operator (>, <, =)
        description (str): Alert description
    """
    # Load existing alerts
    current_alerts = get_alerts_from_azure('alerts.json')
    
    # Create new alert
    new_alert = {
        "symbol": symbol,
        "price": price,
        "operator": operator,
        "description": description,
        "triggered_date": ""
    }
    
    # Append new alert
    current_alerts.append(new_alert)
    
    # Save updated alerts
    save_alerts_to_azure('alerts.json', current_alerts)

@app.route(route="insert_new_alert_grani", auth_level=func.AuthLevel.FUNCTION)
def insert_new_alert_grani(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    try:
        req_body = req.get_json()
        symbol = req_body.get('symbol')
        price = req_body.get('price')
        operator = req_body.get('operator')
        description = req_body.get('description')

        # Validate required fields
        if not all([symbol, price, operator, description]):
            return func.HttpResponse(
                "Missing required fields. Please provide symbol, price, operator, and description.",
                status_code=400
            )
        # Call the alert insertion function
        insert_new_alert_grani_internal(symbol, price, operator, description)

        return func.HttpResponse(
            f"Alert created successfully for {symbol}",
            status_code=200
        )

    except ValueError as ve:
        return func.HttpResponse(
            f"Invalid price format: {str(ve)}",
            status_code=400
        )
    except Exception as e:
        return func.HttpResponse(
            f"Error creating alert: {str(e)}",
            status_code=500
        )
    
@app.route(route="get_all_alerts", methods=["GET"])
def get_all_alerts(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function "get_all_alerts" processed a request.')
    
    try:
        alerts = get_alerts_from_azure('alerts.json')
        # Filter out alerts that have already been triggered
        alerts = [alert for alert in alerts if not alert['triggered_date']]
        config = configparser.ConfigParser()
        config.read('config.ini')
        telegram_enabled = config.getboolean('TELEGRAM', 'Enabled')
        telegram_token = config.get('TELEGRAM', 'Token')
        telegram_chat_ids = config.get('TELEGRAM', 'ChatIDs').split(',')
        
        # Format alerts for Telegram message
        message = "Current Price Alerts:\n\n"
        for alert in alerts:
            message += f"Symbol: ${alert['symbol']}\n"
            message += f"Price: ${alert['price']}\n"
            message += f"Operator: {alert['operator']}\n"
            message += f"Description: {alert['description']}\n"
            message += "---------------\n"
            
        # Send to Telegram
        asyncio.run(send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message))
        
        response_body = {
            "alerts": alerts
        }
        
        return func.HttpResponse(
            body=json.dumps(response_body),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Error in get_all_alerts: {str(e)}")
        return func.HttpResponse(
            body=json.dumps({"error": str(e)}),
            mimetype="application/json", 
            status_code=500
        )