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
        single_alerts = [a for a in alerts if a.get("type") != "ratio"]
        ratio_alerts = [a for a in alerts if a.get("type") == "ratio"]

        if single_alerts:
            message += "🎯 Single Symbol Alerts:\n"
            for alert in single_alerts:
                message += f"Symbol: ${alert['symbol']}\n"
                message += f"Price: ${alert['price']}\n"
                message += f"Operator: {alert['operator']}\n"
                message += f"Description: {alert['description']}\n"
                message += "---------------\n"

        if ratio_alerts:
            message += "\n📈 Ratio Alerts:\n"
            for alert in ratio_alerts:
                message += f"Pair: {alert['symbol1']}/{alert['symbol2']}\n"
                message += f"Ratio: {alert['price']}\n"
                message += f"Operator: {alert['operator']}\n"
                message += f"Description: {alert['description']}\n"
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
