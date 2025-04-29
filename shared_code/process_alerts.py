from datetime import datetime
import json
import logging
import os
from telegram_logging_handler import app_logger
from shared_code.price_cache import price_cache
from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure, send_telegram_message
from shared_code.price_check import get_crypto_candle
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
            if alert.get('type') == 'ratio':
                # For ratio alerts, we need prices for both symbols
                # Get candle data for both symbols
                candle1 = get_crypto_candle(alert['symbol1'])
                candle2 = get_crypto_candle(alert['symbol2'])
                
                if candle1 and candle2:
                    # When checking ratios, we need to consider the most extreme cases
                    # For ratio > alert: check highest value of symbol1 / lowest value of symbol2
                    # For ratio < alert: check lowest value of symbol1 / highest value of symbol2
                    if alert['operator'] == ">":
                        # Most optimistic ratio for triggering ">" condition: high1/low2
                        if candle2.low != 0:  # Prevent division by zero
                            ratio = candle1.high / candle2.low
                            condition_met = ratio > alert['price']
                    elif alert['operator'] == "<":
                        # Most optimistic ratio for triggering "<" condition: low1/high2
                        if candle2.high != 0:  # Prevent division by zero
                            ratio = candle1.low / candle2.high
                            condition_met = ratio < alert['price']
                    
                    # Use current close prices for logging metrics
                    if candle2.close != 0:
                        current_ratio = candle1.close / candle2.close
                        # Log metric with current ratio
                        log_custom_metric(
                            name="crypto_ratio",
                            value=current_ratio,
                            attributes={"symbol1": alert['symbol1'], "symbol2": alert['symbol2']}
                        )
                        logging.info(f"Logged ratio metric for {alert['symbol1']}/{alert['symbol2']}: {current_ratio:.4f}")
                        
                    if condition_met:
                        # For display in notification, use current close prices
                        current_ratio = candle1.close / candle2.close if candle2.close != 0 else 0
                        message = f"🚨 Ratio Alert for {alert['symbol1']}/{alert['symbol2']}!\n"
                        message += f"Current ratio: {current_ratio:.4f}\n"
                        message += f"Alert condition: {alert['price']} {alert['operator']}\n"
                        message += f"Current prices:\n"
                        message += f"{alert['symbol1']}: ${candle1.close:.2f} (Range: ${candle1.low:.2f}-${candle1.high:.2f})\n"
                        message += f"{alert['symbol2']}: ${candle2.close:.2f} (Range: ${candle2.low:.2f}-${candle2.high:.2f})\n"
                        message += f"Description: {alert['description']}"
                        alert['triggered_date'] = datetime.now().isoformat()
                        any_alert_triggered = True
                        
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
                        logging.info(f"Ratio alert sent for {alert['symbol1']}/{alert['symbol2']}")
            
            else:
                # Handle single symbol alerts
                alert['symbol'] = alert['symbol'].upper()
                candle = get_crypto_candle(alert['symbol'])
                
                if candle:
                    # Check if candle meets condition
                    condition_met = candle.meets_condition(alert['price'], alert['operator'])
                    
                    if condition_met:
                        message = f"🚨 Alert for {alert['symbol']}!\n"
                        message += f"Current price: ${candle.close:.2f}\n"
                        message += f"Price range in last 5 min: ${candle.low:.2f}-${candle.high:.2f}\n"
                        message += f"Alert condition: ${alert['price']} {alert['operator']}\n"
                        message += f"Description: {alert['description']}"
                        alert['triggered_date'] = datetime.now().isoformat()
                        any_alert_triggered = True
                        
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
                        logging.info(f"Alert sent for {alert['symbol']}")

        if any_alert_triggered:
            save_alerts_to_azure('alerts.json', alerts)
        
        price_cache.clear()
                    
    except Exception as e:
        app_logger.error(f"Error processing alerts: {str(e)}")