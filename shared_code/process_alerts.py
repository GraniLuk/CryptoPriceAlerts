from datetime import datetime
import logging
import os

from shared_code.price_cache import price_cache
from shared_code.utils import get_alerts_from_azure, get_crypto_price, get_crypto_price_binance, save_alerts_to_azure, send_telegram_message


async def process_alerts():
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
            condition_met = False
            
            if alert.get('type') == 'ratio':
                # Handle ratio alerts
                price1 = price_cache.get_price(alert['symbol1'])
                if price1 is None:
                    price1 = get_crypto_price(alert['symbol1'], coingecko_api_key)
                    price_cache.set_price(alert['symbol1'], price1)
                    
                price2 = price_cache.get_price(alert['symbol2'])
                if price2 is None:
                    price2 = get_crypto_price(alert['symbol2'], coingecko_api_key)
                    price_cache.set_price(alert['symbol2'], price2)
                    
                if price1 and price2 and price2 != 0:
                    ratio = price1 / price2
                    if alert['operator'] == ">" and ratio > alert['price']:
                        condition_met = True
                    elif alert['operator'] == "<" and ratio < alert['price']:
                        condition_met = True
                        
                    if condition_met:
                        message = f"🚨 Ratio Alert for {alert['symbol1']}/{alert['symbol2']}!\n"
                        message += f"Current ratio: {ratio:.4f}\n"
                        message += f"Alert condition: {alert['price']} {alert['operator']}\n"
                        message += f"Current prices:\n"
                        message += f"{alert['symbol1']}: ${price1:.2f}\n"
                        message += f"{alert['symbol2']}: ${price2:.2f}\n"
                        message += f"Description: {alert['description']}"
                        alert['triggered_date'] = datetime.now().isoformat()
                        any_alert_triggered = True
                        
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message)
                        logging.info(f"Ratio alert sent for {alert['symbol1']}/{alert['symbol2']}")
            
            else:
                # Handle existing single symbol alerts
                current_price = price_cache.get_price(alert['symbol'])
                if current_price is None:
                    current_price = get_crypto_price_binance(alert['symbol'], coingecko_api_key)
                    price_cache.set_price(alert['symbol'], current_price)
                
                if current_price:
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
        
        price_cache.clear()
                    
    except Exception as e:
        logging.error(f"Error processing alerts: {str(e)}") 