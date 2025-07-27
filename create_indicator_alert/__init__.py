import azure.functions as func
import json
import logging
from datetime import datetime
import uuid

from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from telegram_logging_handler import app_logger


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP API endpoint to create a new indicator alert (RSI, etc.)
    
    POST /api/create_indicator_alert
    
    Request Body:
    {
        "symbol": "BTC",
        "indicator_type": "rsi",
        "config": {
            "period": 14,
            "overbought_level": 75,
            "oversold_level": 25,
            "timeframe": "5m"
        },
        "description": "BTC RSI threshold monitoring alert"
    }
    
    Note: The 'condition' parameter is no longer required. 
    All RSI alerts now monitor for any threshold crossovers automatically.
    """
    app_logger.info('Creating new indicator alert via HTTP API')
    
    try:
        # Validate HTTP method
        if req.method != 'POST':
            return func.HttpResponse(
                json.dumps({"error": "Only POST method is allowed"}),
                status_code=405,
                mimetype="application/json"
            )
        
        # Parse request body
        try:
            req_body = req.get_json()
            if not req_body:
                return func.HttpResponse(
                    json.dumps({"error": "Request body is required"}),
                    status_code=400,
                    mimetype="application/json"
                )
        except ValueError as e:
            return func.HttpResponse(
                json.dumps({"error": f"Invalid JSON in request body: {str(e)}"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Validate required fields
        required_fields = ["symbol", "indicator_type", "config"]
        missing_fields = [field for field in required_fields if field not in req_body]
        if missing_fields:
            return func.HttpResponse(
                json.dumps({"error": f"Missing required fields: {', '.join(missing_fields)}"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Validate indicator type
        if req_body["indicator_type"] != "rsi":
            return func.HttpResponse(
                json.dumps({"error": "Currently only 'rsi' indicator type is supported"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Set default condition for RSI (no longer used but kept for compatibility)
        condition = req_body.get("condition", "threshold_crossover")
        
        # Validate config for RSI
        config = req_body["config"]
        if not isinstance(config, dict):
            return func.HttpResponse(
                json.dumps({"error": "Config must be an object"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Set default values for RSI config
        rsi_config = {
            "period": config.get("period", 14),
            "overbought_level": config.get("overbought_level", 70),
            "oversold_level": config.get("oversold_level", 30),
            "timeframe": config.get("timeframe", "5m")
        }
        
        # Validate config values
        if not isinstance(rsi_config["period"], int) or rsi_config["period"] < 2:
            return func.HttpResponse(
                json.dumps({"error": "Period must be an integer >= 2"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not (0 < rsi_config["overbought_level"] <= 100):
            return func.HttpResponse(
                json.dumps({"error": "Overbought level must be between 1 and 100"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not (0 <= rsi_config["oversold_level"] < 100):
            return func.HttpResponse(
                json.dumps({"error": "Oversold level must be between 0 and 99"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if rsi_config["oversold_level"] >= rsi_config["overbought_level"]:
            return func.HttpResponse(
                json.dumps({"error": "Oversold level must be less than overbought level"}),
                status_code=400,
                mimetype="application/json"
            )
        
        valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
        if rsi_config["timeframe"] not in valid_timeframes:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Invalid timeframe. Valid options: {', '.join(valid_timeframes)}"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Generate unique alert ID
        alert_id = str(uuid.uuid4())
        
        # Create standardized Telegram trigger message
        symbol = req_body["symbol"].upper()
        indicator_type = req_body["indicator_type"].upper()
        timeframe = rsi_config["timeframe"]
        
        # Generate message for threshold crossover monitoring
        message = f"� {symbol} RSI Alert: Monitoring threshold crossovers on {timeframe} timeframe (Overbought: {rsi_config['overbought_level']}, Oversold: {rsi_config['oversold_level']})"
        
        # Always use Telegram trigger
        triggers = [{"type": "telegram", "message": message}]
        
        # Create the indicator alert
        alert = IndicatorAlert(
            id=alert_id,
            symbol=symbol,
            indicator_type=req_body["indicator_type"],
            condition=condition,
            config=rsi_config,
            description=req_body.get("description", f"{symbol} {indicator_type} threshold monitoring alert"),
            triggers=triggers,
            enabled=req_body.get("enabled", True),
            created_date=datetime.now().isoformat(),
            triggered_date=""
        )
        
        # Save to table storage
        table_storage = AlertTableStorage()
        if not table_storage.service_client:
            return func.HttpResponse(
                json.dumps({"error": "Table storage not available"}),
                status_code=503,
                mimetype="application/json"
            )
        
        indicator_table = table_storage.get_table_client("indicatoralerts")
        if not indicator_table:
            return func.HttpResponse(
                json.dumps({"error": "Indicator alerts table not available"}),
                status_code=503,
                mimetype="application/json"
            )
        
        # Save the alert
        entity = alert.to_table_entity()
        indicator_table.upsert_entity(entity)
        
        app_logger.info(f"Created indicator alert: {alert.id} for {alert.symbol} {alert.indicator_type} threshold monitoring")
        
        # Return success response
        response_data = {
            "success": True,
            "message": "Indicator alert created successfully",
            "alert": {
                "id": alert.id,
                "symbol": alert.symbol,
                "indicator_type": alert.indicator_type,
                "condition": alert.condition,
                "config": alert.config,
                "description": alert.description,
                "enabled": alert.enabled,
                "created_date": alert.created_date
            }
        }
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=201,
            mimetype="application/json"
        )
        
    except Exception as e:
        app_logger.error(f"Error creating indicator alert: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "details": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
