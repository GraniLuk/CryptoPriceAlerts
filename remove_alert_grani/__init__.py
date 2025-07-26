import logging
import json

import azure.functions as func

from shared_code.table_storage import AlertTableStorage
from telegram_logging_handler import app_logger


def main(req: func.HttpRequest) -> func.HttpResponse:
    app_logger.info("Processing remove alert request via HTTP API")

    try:
        req_body = req.get_json()
        alert_id = req_body.get("id")
        alert_type = req_body.get("type")  # Optional: 'price', 'indicator', or auto-detect

        if not alert_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing alert ID"}),
                status_code=400,
                mimetype="application/json"
            )

        removed_from = []
        alert_found = False

        # Initialize table storage
        table_storage = AlertTableStorage()
        if not table_storage.service_client:
            return func.HttpResponse(
                json.dumps({"error": "Table storage not available"}),
                status_code=503,
                mimetype="application/json"
            )

        # Try removing from price alerts (if not specifically indicator type)
        if alert_type != 'indicator':
            try:
                price_table = table_storage.get_table_client("pricealerts")
                if price_table:
                    # Find the price alert by ID
                    price_entities = list(price_table.query_entities(f"RowKey eq '{alert_id}'"))
                    
                    if price_entities:
                        # Remove the first matching alert (should be unique)
                        alert_entity = price_entities[0]
                        price_table.delete_entity(
                            partition_key=alert_entity["PartitionKey"],
                            row_key=alert_entity["RowKey"]
                        )
                        removed_from.append("price alerts")
                        alert_found = True
                        app_logger.info(f"Removed price alert with ID {alert_id}")
                    else:
                        app_logger.info(f"Price alert with ID {alert_id} not found")
                else:
                    app_logger.warning("Price alerts table not available")
            except Exception as e:
                app_logger.error(f"Error removing from price alerts: {e}")

        # Try removing from indicator alerts (if not specifically price type)
        if alert_type != 'price':
            try:
                indicator_table = table_storage.get_table_client("indicatoralerts")
                if indicator_table:
                    # Find the indicator alert by ID
                    indicator_entities = list(indicator_table.query_entities(f"RowKey eq '{alert_id}'"))
                    
                    if indicator_entities:
                        # Remove the first matching alert (should be unique)
                        alert_entity = indicator_entities[0]
                        indicator_table.delete_entity(
                            partition_key=alert_entity["PartitionKey"],
                            row_key=alert_entity["RowKey"]
                        )
                        removed_from.append("indicator alerts")
                        alert_found = True
                        app_logger.info(f"Removed indicator alert with ID {alert_id}")
                    else:
                        app_logger.info(f"Indicator alert with ID {alert_id} not found")
                else:
                    app_logger.warning("Indicator alerts table not available")
            except Exception as e:
                app_logger.error(f"Error removing from indicator alerts: {e}")

        # Return appropriate response
        if alert_found:
            if len(removed_from) > 1:
                message = f"Alert with ID {alert_id} removed from {' and '.join(removed_from)}"
            else:
                message = f"Alert with ID {alert_id} removed from {removed_from[0]}"
            
            response_data = {
                "success": True,
                "message": message,
                "removed_from": removed_from,
                "alert_id": alert_id
            }
            
            return func.HttpResponse(
                json.dumps(response_data, indent=2),
                mimetype="application/json",
                status_code=200
            )
        else:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Alert with ID {alert_id} not found in any alert storage",
                    "alert_id": alert_id
                }),
                mimetype="application/json",
                status_code=404
            )

    except ValueError as e:
        app_logger.error(f"Invalid JSON in request body: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON in request body: {str(e)}"}),
            mimetype="application/json",
            status_code=400
        )
    except Exception as e:
        app_logger.error(f"Error removing alert: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error", 
                "details": str(e)
            }),
            mimetype="application/json",
            status_code=500
        )
