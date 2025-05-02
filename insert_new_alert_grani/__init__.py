import logging
from uuid import uuid4

import azure.functions as func

from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        req_body = req.get_json()
        alert_type = req_body.get(
            "type", "single"
        )  # Default to single for backward compatibility

        if alert_type == "ratio":
            symbol1 = req_body.get("symbol1").upper()
            symbol2 = req_body.get("symbol2").upper()
            price = req_body.get("price")
            operator = req_body.get("operator")
            description = req_body.get("description")

            if not all([symbol1, symbol2, price, operator, description]):
                return func.HttpResponse(
                    "Missing required fields. Please provide symbol1, symbol2, price, operator, and description.",
                    status_code=400,
                )

            new_alert = {
                "id": str(uuid4()),
                "type": "ratio",
                "symbol1": symbol1,
                "symbol2": symbol2,
                "price": price,
                "operator": operator,
                "description": description,
                "triggered_date": "",
            }
        else:
            # Handle standard single symbol alerts
            symbol = req_body.get("symbol").upper()
            price = req_body.get("price")
            operator = req_body.get("operator")
            description = req_body.get("description")

            if not all([symbol, price, operator, description]):
                return func.HttpResponse(
                    "Missing required fields. Please provide symbol, price, operator, and description.",
                    status_code=400,
                )

            new_alert = {
                "id": str(uuid4()),
                "type": "single",
                "symbol": symbol,
                "price": price,
                "operator": operator,
                "description": description,
                "triggered_date": "",
            }

        # Process triggers if provided
        if "triggers" in req_body:
            # Validate triggers
            triggers = req_body.get("triggers")
            if not isinstance(triggers, list):
                return func.HttpResponse(
                    "The 'triggers' field must be a list of trigger objects.",
                    status_code=400,
                )

            valid_triggers = []

            for trigger in triggers:
                trigger_type = trigger.get("type")
                if not trigger_type:
                    return func.HttpResponse(
                        "Each trigger must have a 'type' field.", status_code=400
                    )

                # Validate Bybit action triggers
                if trigger_type == "bybit_action":
                    action = trigger.get("action")
                    if not action:
                        return func.HttpResponse(
                            "Bybit triggers must have an 'action' field.",
                            status_code=400,
                        )

                    if action not in ["open_position", "close_position", "set_tp_sl"]:
                        return func.HttpResponse(
                            f"Invalid Bybit action: {action}. Valid actions are: open_position, close_position, set_tp_sl",
                            status_code=400,
                        )

                    params = trigger.get("params", {})
                    if action == "open_position" and (
                        "side" not in params or "qty" not in params
                    ):
                        return func.HttpResponse(
                            "Open position actions require 'side' and 'qty' parameters.",
                            status_code=400,
                        )

                    valid_triggers.append(trigger)

                # Future trigger types can be validated here
                # elif trigger_type == 'some_other_type':
                #    ...validation logic...

            if valid_triggers:
                new_alert["triggers"] = valid_triggers

        current_alerts = get_alerts_from_azure("alerts.json")
        current_alerts.append(new_alert)
        save_alerts_to_azure("alerts.json", current_alerts)

        return func.HttpResponse("Alert created successfully", status_code=200)

    except ValueError as ve:
        return func.HttpResponse(f"Invalid price format: {str(ve)}", status_code=400)
    except Exception as e:
        return func.HttpResponse(f"Error creating alert: {str(e)}", status_code=500)
