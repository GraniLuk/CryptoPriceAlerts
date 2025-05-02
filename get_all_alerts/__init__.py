import json
import logging

import azure.functions as func

from shared_code.utils import get_alerts_from_azure
from telegram_logging_handler import app_logger


async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function "get_all_alerts" processed a request.')

    try:
        logging.info("Attempting to fetch alerts from Azure...")
        alerts = get_alerts_from_azure("alerts.json")
        logging.info(f"Successfully retrieved {len(alerts)} alerts")

        alerts = [alert for alert in alerts if not alert["triggered_date"]]
        logging.info(f"Filtered to {len(alerts)} non-triggered alerts")

        message = "📊 Current Price Alerts:\n\n"

        # Group alerts by type
        single_alerts = [a for a in alerts if a.get("type") == "single"]
        ratio_alerts = [a for a in alerts if a.get("type") == "ratio"]

        if single_alerts:
            message += "🎯 Single Symbol Alerts:\n"
            for alert in single_alerts:
                message += f"Symbol: ${alert['symbol']}\n"
                message += f"Price: ${alert['price']}\n"
                message += f"Operator: {alert['operator']}\n"
                message += f"Description: {alert['description']}\n"
                
                # Display triggers if present
                if 'triggers' in alert and alert['triggers']:
                    message += "Triggers:\n"
                    for trigger in alert['triggers']:
                        if trigger['type'] == 'bybit_action':
                            message += f"- Bybit: {trigger['action']}\n"
                            
                            # Display additional action parameters based on action type
                            if trigger['action'] == 'open_position':
                                params = trigger.get('params', {})
                                message += f"  Side: {params.get('side', 'N/A')}\n"
                                message += f"  Quantity: {params.get('qty', 'N/A')}\n"
                                if 'leverage' in params:
                                    message += f"  Leverage: {params.get('leverage')}x\n"
                            elif trigger['action'] == 'set_tp_sl':
                                params = trigger.get('params', {})
                                if 'take_profit' in params:
                                    message += f"  Take Profit: ${params.get('take_profit')}\n"
                                if 'stop_loss' in params:
                                    message += f"  Stop Loss: ${params.get('stop_loss')}\n"
                
                message += "---------------\n"

        if ratio_alerts:
            message += "\n📈 Ratio Alerts:\n"
            for alert in ratio_alerts:
                message += f"Pair: {alert['symbol1']}/{alert['symbol2']}\n"
                message += f"Ratio: {alert['price']}\n"
                message += f"Operator: {alert['operator']}\n"
                message += f"Description: {alert['description']}\n"
                
                # Display triggers if present
                if 'triggers' in alert and alert['triggers']:
                    message += "Triggers:\n"
                    for trigger in alert['triggers']:
                        if trigger['type'] == 'bybit_action':
                            message += f"- Bybit: {trigger['action']}\n"
                            
                            # Display additional action parameters based on action type
                            if trigger['action'] == 'open_position':
                                params = trigger.get('params', {})
                                message += f"  Side: {params.get('side', 'N/A')}\n"
                                message += f"  Quantity: {params.get('qty', 'N/A')}\n"
                                if 'leverage' in params:
                                    message += f"  Leverage: {params.get('leverage')}x\n"
                            elif trigger['action'] == 'set_tp_sl':
                                params = trigger.get('params', {})
                                if 'take_profit' in params:
                                    message += f"  Take Profit: ${params.get('take_profit')}\n"
                                if 'stop_loss' in params:
                                    message += f"  Stop Loss: ${params.get('stop_loss')}\n"
                
                message += "---------------\n"

        return func.HttpResponse(
            body=json.dumps({"alerts": alerts}),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        app_logger.error(f"Error in get_all_alerts: {str(e)}")
        app_logger.error(f"Error type: {type(e).__name__}")
        app_logger.error(
            "Error details: ", exc_info=True
        )  # This will log the full stack trace
        return func.HttpResponse(
            body=json.dumps({"error": str(e), "error_type": type(e).__name__}),
            mimetype="application/json",
            status_code=500,
        )
