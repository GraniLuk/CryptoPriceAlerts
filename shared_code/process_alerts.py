import logging
import os
from datetime import datetime

from shared_code.bybit_integration import execute_bybit_action
from shared_code.price_cache import price_cache
from shared_code.price_check import get_crypto_candle
from shared_code.ratio_metric import log_custom_metric
from shared_code.utils import (
    get_alerts_from_azure,
    save_alerts_to_azure,
    send_telegram_message,
)
from telegram_logging_handler import app_logger


async def process_alerts():
    try:
        telegram_enabled = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
        telegram_token = os.environ.get("TELEGRAM_TOKEN", "") if telegram_enabled else ""
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "") if telegram_enabled else ""
        coingecko_api_key = os.environ.get("COINGECKO_API_KEY", "")

        alerts = get_alerts_from_azure("alerts.json")

        if alerts is None:
            app_logger.error("Failed to get alerts from Azure Storage.")
            return

        alerts = [alert for alert in alerts if not alert["triggered_date"]]
        any_alert_triggered = False

        for alert in alerts:
            condition_met = False

            # Handle different alert types
            if alert.get("type") == "ratio":
                # For ratio alerts, we need prices for both symbols
                # Get candle data for both symbols (auto_save=True by default)
                candle1 = get_crypto_candle(alert["symbol1"])  # auto_save=True by default
                candle2 = get_crypto_candle(alert["symbol2"])  # auto_save=True by default

                if candle1 and candle2:
                    # When checking ratios, we need to consider the most extreme cases
                    # For ratio > alert: check highest value of symbol1 / lowest value of symbol2
                    # For ratio < alert: check lowest value of symbol1 / highest value of symbol2
                    if alert["operator"] == ">":
                        # Most optimistic ratio for triggering ">" condition: high1/low2
                        if candle2.low != 0:  # Prevent division by zero
                            ratio = candle1.high / candle2.low
                            condition_met = ratio > alert["price"]
                    elif alert["operator"] == "<":
                        # Most optimistic ratio for triggering "<" condition: low1/high2
                        if candle2.high != 0:  # Prevent division by zero
                            ratio = candle1.low / candle2.high
                            condition_met = ratio < alert["price"]

                    # Use current close prices for logging metrics
                    if candle2.close != 0:
                        current_ratio = candle1.close / candle2.close
                        # Log metric with current ratio
                        log_custom_metric(
                            name="crypto_ratio",
                            value=current_ratio,
                            attributes={
                                "symbol1": alert["symbol1"],
                                "symbol2": alert["symbol2"],
                            },
                        )
                        logging.info(
                            f"Logged ratio metric for {alert['symbol1']}/{alert['symbol2']}: {current_ratio:.4f}"
                        )

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

                        # Execute triggers if defined
                        if "triggers" in alert and alert["triggers"]:
                            trigger_results = await execute_triggers(alert, message)
                            # Add trigger results to the message
                            for result in trigger_results:
                                message += f"\n\n{result}"

                        alert["triggered_date"] = datetime.now().isoformat()
                        any_alert_triggered = True

                        await send_telegram_message(
                            telegram_enabled, telegram_token, telegram_chat_id, message
                        )
                        logging.info(f"Ratio alert sent for {alert['symbol1']}/{alert['symbol2']}")

            else:
                # Handle standard single symbol alerts
                alert["symbol"] = alert["symbol"].upper()
                candle = get_crypto_candle(alert["symbol"])  # auto_save=True by default

                if candle:
                    # Check if candle meets condition
                    condition_met = candle.meets_condition(alert["price"], alert["operator"])

                    if condition_met:
                        message = f"🚨 Alert for {alert['symbol']}!\n"
                        message += f"Current price: ${candle.close:.2f}\n"
                        message += (
                            f"Price range in last 5 min: ${candle.low:.2f}-${candle.high:.2f}\n"
                        )
                        message += f"Alert condition: ${alert['price']} {alert['operator']}\n"
                        message += f"Description: {alert['description']}"

                        # Execute triggers if defined
                        if "triggers" in alert and alert["triggers"]:
                            trigger_results = await execute_triggers(alert, message)
                            # Add trigger results to the message
                            for result in trigger_results:
                                message += f"\n\n{result}"

                        alert["triggered_date"] = datetime.now().isoformat()
                        any_alert_triggered = True

                        await send_telegram_message(
                            telegram_enabled, telegram_token, telegram_chat_id, message
                        )
                        logging.info(f"Alert sent for {alert['symbol']}")

        if any_alert_triggered:
            save_alerts_to_azure("alerts.json", alerts)

        price_cache.clear()

    except Exception as e:
        app_logger.error(f"Error processing alerts: {str(e)}")


async def execute_triggers(alert, message):
    """Execute all triggers defined in the alert"""
    results = []

    try:
        if "triggers" not in alert or not alert["triggers"]:
            return results

        for trigger in alert["triggers"]:
            trigger_type = trigger.get("type")

            # Handle Bybit trading triggers
            if trigger_type == "bybit_action":
                action = trigger.get("action")
                params = trigger.get("params", {})

                # Add symbol from alert if not in params
                if "symbol" not in params and trigger_type == "bybit_action":
                    if "symbol" in alert:
                        params["symbol"] = alert["symbol"]
                    elif "symbol1" in alert:
                        # For ratio alerts, use symbol1 as the default trading pair
                        params["symbol"] = alert["symbol1"]

                # Execute the Bybit action
                result = execute_bybit_action(action, params)

                if result["success"]:
                    results.append(f"✅ Bybit action '{action}' executed successfully")
                else:
                    results.append(
                        f"❌ Bybit action failed: {result.get('message', 'Unknown error')}"
                    )

            # Future: Add other trigger types here
            # elif trigger_type == 'some_other_action':
            #     ...

    except Exception as e:
        error_msg = f"Error executing triggers: {str(e)}"
        app_logger.error(error_msg)
        results.append(f"❌ {error_msg}")

    return results
