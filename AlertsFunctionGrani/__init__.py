import logging
import azure.functions as func
from datetime import datetime
import asyncio
import os
from shared_code.utils import (
    get_crypto_price,
    get_alerts_from_azure,
    save_alerts_to_azure,
    send_telegram_message
)
from shared_code.price_cache import price_cache

async def main(mytimer: func.TimerRequest) -> None:
    try:
        telegram_enabled = os.environ["TELEGRAM_ENABLED"].lower() == "true"
        telegram_token = os.environ["TELEGRAM_TOKEN"]
        telegram_chat_ids = os.environ["TELEGRAM_CHAT_IDS"]
        coingecko_api_key = os.environ["COINGECKO_API_KEY"]

        alerts = get_alerts_from_azure('alerts.json')
        
        if alerts is None:
            logging.error("Failed to get alerts from Azure Storage.")
            return
        
        alerts = [alert for alert in alerts if not alert['triggered_date']]
        any_alert_triggered = False
        
        for alert in alerts:
            # Check cache first
            current_price = price_cache.get_price(alert['symbol'])
            if current_price is None:
                # Fetch price from API if not cached
                current_price = get_crypto_price(alert['symbol'], coingecko_api_key)
                price_cache.set_price(alert['symbol'], current_price)
            
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
                    alert['triggered_date'] = datetime.now().isoformat()
                    any_alert_triggered = True
                    
                    await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message)
                    logging.info(f"Alert sent for {alert['symbol']}")
        
        if any_alert_triggered:
            save_alerts_to_azure('alerts.json', alerts)
                    
    except Exception as e:
        logging.error(f"Error in AlertsFunction: {str(e)}")