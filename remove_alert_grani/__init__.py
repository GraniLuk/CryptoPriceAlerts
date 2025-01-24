import logging
import azure.functions as func
from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    try:
        req_body = req.get_json()
        alert_id = req_body.get('id')

        if not alert_id:
            return func.HttpResponse(
                "Missing alert ID",
                status_code=400
            )

        current_alerts = get_alerts_from_azure('alerts.json')
        
        # Find and remove the alert with matching ID
        filtered_alerts = [alert for alert in current_alerts if alert.get('id') != alert_id]
        
        if len(filtered_alerts) == len(current_alerts):
            return func.HttpResponse(
                f"Alert with ID {alert_id} not found",
                status_code=404
            )

        save_alerts_to_azure('alerts.json', filtered_alerts)

        return func.HttpResponse(
            "Alert removed successfully",
            status_code=200
        )

    except Exception as e:
        return func.HttpResponse(
            f"Error removing alert: {str(e)}",
            status_code=500
        )
