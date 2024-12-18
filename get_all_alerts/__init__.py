import logging
import azure.functions as func
import json
import os
import asyncio
from shared_code.utils import get_alerts_from_azure, send_telegram_message

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function "get_all_alerts" processed a request.')
    
    try:
        alerts = get_alerts_from_azure('alerts.json')
        alerts = [alert for alert in alerts if not alert['triggered_date']]
        
        telegram_enabled = os.environ["TELEGRAM_ENABLED"].lower() == "true"
        telegram_token = os.environ["TELEGRAM_TOKEN"]
        telegram_chat_ids = os.environ["TELEGRAM_CHAT_IDS"].split(',')
        
        message = "Current Price Alerts:\n\n"
        for alert in alerts:
            message += f"Symbol: ${alert['symbol']}\n"
            message += f"Price: ${alert['price']}\n"
            message += f"Operator: {alert['operator']}\n"
            message += f"Description: {alert['description']}\n"
            message += "---------------\n"
            
        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_ids, message)
        
        return func.HttpResponse(
            body=json.dumps({"alerts": alerts}),
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