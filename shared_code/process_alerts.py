from datetime import datetime
import json
import logging
import os
from telegram_logging_handler import app_logger
from shared_code.price_cache import price_cache
from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure, send_telegram_message
from shared_code.price_check import get_crypto_price
from shared_code.bybit_integration import execute_bybit_action
from ratio_metric import log_custom_metric


async def process_alerts():
    try:
        telegram_enabled = os.environ["TELEGRAM_ENABLED"].lower() == "true"
        telegram_token = os.environ["TELEGRAM_TOKEN"]
        telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]
        coingecko_api_key = os.environ["COINGECKO_API_KEY"]

        alerts = get_alerts_from_azure('alerts.json')

        if alerts is None:
            app_logger.error("Failed to get alerts from Azure Storage.")
            return
        
        alerts = [alert for alert in alerts if not alert['triggered_date']]
        any_alert_triggered = False
        
        for alert in alerts:
            condition_met = False
            
            # Handle different alert types
            if alert.get('type') == 'ratio':
                # Handle ratio alerts
                price1 = price_cache.get_price(alert['symbol1'])
                if price1 is None:
                    price1 = get_crypto_price(alert['symbol1'])
                    price_cache.set_price(alert['symbol1'], price1)
                    
                price2 = price_cache.get_price(alert['symbol2'])
                if price2 is None:
                    price2 = get_crypto_price(alert['symbol2'])
                    price_cache.set_price(alert['symbol2'], price2)
                    
                if price1 and price2 and price2 != 0:
                    ratio = price1 / price2
                    # metric logging
                    log_custom_metric(
                        name="crypto_ratio",
                        value=ratio,
                        attributes={"symbol1": alert['symbol1'], "symbol2": alert['symbol2']}
                    )
                    logging.info(f"Logged ratio metric for {alert['symbol1']}/{alert['symbol2']}: {ratio:.4f}")
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
                        
                        # Execute triggers if defined
                        if 'triggers' in alert and alert['triggers']:
                            trigger_results = await execute_triggers(alert, message)
                            # Add trigger results to the message
                            for result in trigger_results:
                                message += f"\n\n{result}"
                            
                        alert['triggered_date'] = datetime.now().isoformat()
                        any_alert_triggered = True
                        
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
                        logging.info(f"Ratio alert sent for {alert['symbol1']}/{alert['symbol2']}")
            
            else:
                # Handle standard single symbol alerts
                alert['symbol'] = alert['symbol'].upper()
                current_price = price_cache.get_price(alert['symbol'])
                if current_price is None:
                    current_price = get_crypto_price(alert['symbol'])
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
                        
                        # Execute triggers if defined
                        if 'triggers' in alert and alert['triggers']:
                            trigger_results = await execute_triggers(alert, message)
                            # Add trigger results to the message
                            for result in trigger_results:
                                message += f"\n\n{result}"
                            
                        alert['triggered_date'] = datetime.now().isoformat()
                        any_alert_triggered = True
                        
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
                        logging.info(f"Alert sent for {alert['symbol']}")

        if any_alert_triggered:
            save_alerts_to_azure('alerts.json', alerts)
        
        price_cache.clear()
                    
    except Exception as e:
        app_logger.error(f"Error processing alerts: {str(e)}")

async def execute_triggers(alert, message):
    """Execute all triggers defined in the alert"""
    results = []
    
    try:
        if 'triggers' not in alert or not alert['triggers']:
            return results
        
        for trigger in alert['triggers']:
            trigger_type = trigger.get('type')
            
            # Handle Bybit trading triggers
            if trigger_type == 'bybit_action':
                action = trigger.get('action')
                params = trigger.get('params', {})
                
                # Add symbol from alert if not in params
                if 'symbol' not in params and trigger_type == 'bybit_action':
                    if 'symbol' in alert:
                        params['symbol'] = alert['symbol']
                    elif 'symbol1' in alert:
                        # For ratio alerts, use symbol1 as the default trading pair
                        params['symbol'] = alert['symbol1']
                
                # Execute the Bybit action
                result = execute_bybit_action(action, params)
                
                if result['success']:
                    results.append(f"✅ Bybit action '{action}' executed successfully")
                else:
                    results.append(f"❌ Bybit action failed: {result.get('message', 'Unknown error')}")
            
            # Future: Add other trigger types here
            # elif trigger_type == 'some_other_action':
            #     ...
            
    except Exception as e:
        error_msg = f"Error executing triggers: {str(e)}"
        app_logger.error(error_msg)
        results.append(f"❌ {error_msg}")
        
    return results