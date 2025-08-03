import json
import logging

import azure.functions as func

from shared_code.utils import get_alerts_from_azure
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from shared_code.current_value_service import CurrentValueService
from telegram_logging_handler import app_logger


async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function "get_all_alerts" processed a request.')

    try:
        # Get query parameters for filtering
        alert_type = req.params.get('type')  # 'price', 'indicator', or 'all' (default)
        symbol_filter = req.params.get('symbol')
        enabled_filter = req.params.get('enabled')
        
        all_alerts = []
        
        # Get price alerts from alerts.json
        logging.info("Attempting to fetch price alerts from Azure...")
        price_alerts = get_alerts_from_azure("alerts.json")
        if price_alerts is None:
            logging.warning("Error retrieving price alerts from Azure")
            price_alerts = []
        else:
            logging.info(f"Successfully retrieved {len(price_alerts)} price alerts")
            
            # Filter non-triggered price alerts and add type
            price_alerts = [alert for alert in price_alerts if not alert.get("triggered_date")]
            for alert in price_alerts:
                alert["alert_type"] = "price"  # Add type field for consistency
            
            # Apply filters to price alerts
            if symbol_filter:
                price_alerts = [alert for alert in price_alerts 
                              if alert.get("symbol", "").upper() == symbol_filter.upper()]
            
            if enabled_filter is not None:
                enabled_bool = enabled_filter.lower() == 'true'
                price_alerts = [alert for alert in price_alerts 
                              if alert.get("enabled", True) == enabled_bool]
            
            all_alerts.extend(price_alerts)
        
        # Get indicator alerts from table storage
        if alert_type != 'price':  # Don't fetch indicator alerts if only price alerts requested
            try:
                table_storage = AlertTableStorage()
                if table_storage.service_client:
                    indicator_table = table_storage.get_table_client("indicatoralerts")
                    if indicator_table:
                        logging.info("Attempting to fetch indicator alerts from table storage...")
                        
                        # Build filter query for table storage
                        filter_parts = []
                        if symbol_filter:
                            filter_parts.append(f"PartitionKey eq '{symbol_filter.upper()}'")
                        if enabled_filter is not None:
                            enabled_bool = enabled_filter.lower() == 'true'
                            filter_parts.append(f"Enabled eq {str(enabled_bool).lower()}")
                        
                        # Query indicator alerts
                        filter_query = " and ".join(filter_parts) if filter_parts else None
                        if filter_query:
                            indicator_entities = list(indicator_table.query_entities(filter_query))
                        else:
                            indicator_entities = list(indicator_table.list_entities())
                        
                        # Convert to alert objects
                        indicator_alerts = []
                        for entity in indicator_entities:
                            try:
                                alert = IndicatorAlert.from_table_entity(entity)
                                # Convert to dict format matching price alerts
                                alert_dict = {
                                    "id": alert.id,
                                    "alert_type": "indicator",
                                    "symbol": alert.symbol,
                                    "indicator_type": alert.indicator_type,
                                    "condition": alert.condition,
                                    "config": alert.config,
                                    "description": alert.description,
                                    "enabled": alert.enabled,
                                    "created_date": alert.created_date,
                                    "triggered_date": alert.triggered_date if alert.triggered_date else None,
                                    "triggers": alert.triggers
                                }
                                indicator_alerts.append(alert_dict)
                            except Exception as e:
                                logging.warning(f"Failed to parse indicator alert {entity.get('RowKey', 'unknown')}: {e}")
                        
                        logging.info(f"Successfully retrieved {len(indicator_alerts)} indicator alerts")
                        all_alerts.extend(indicator_alerts)
                    else:
                        logging.warning("Indicator alerts table not available")
                else:
                    logging.warning("Table storage not available for indicator alerts")
            except Exception as e:
                logging.error(f"Error fetching indicator alerts: {e}")
        
        # Apply alert type filter
        if alert_type == 'price':
            all_alerts = [alert for alert in all_alerts if alert.get("alert_type") == "price"]
        elif alert_type == 'indicator':
            all_alerts = [alert for alert in all_alerts if alert.get("alert_type") == "indicator"]
        # 'all' or None means return both types
        
        logging.info(f"Total alerts after filtering: {len(all_alerts)}")
        
        # Initialize current value service
        current_value_service = CurrentValueService()
        
        # Enhance alerts with current values
        enhanced_alerts = []
        
        for alert in all_alerts:
            try:
                enhanced_alert = alert.copy()
                
                if alert.get("alert_type") == "price":
                    if alert.get("type") == "ratio":
                        # Add current ratio value
                        current_value = current_value_service.get_ratio_alert_current_value(
                            alert["symbol1"], alert["symbol2"]
                        )
                        enhanced_alert["current_value"] = current_value
                    else:
                        # Add current price value
                        current_value = current_value_service.get_single_alert_current_value(
                            alert["symbol"]
                        )
                        enhanced_alert["current_value"] = current_value
                        
                elif alert.get("alert_type") == "indicator":
                    # Add current indicator value
                    current_value = current_value_service.get_indicator_alert_current_value(
                        alert["symbol"], 
                        alert["indicator_type"], 
                        alert["config"]
                    )
                    enhanced_alert["current_value"] = current_value
                
                enhanced_alerts.append(enhanced_alert)
                
            except Exception as e:
                logging.warning(f"Failed to enhance alert {alert.get('id', 'unknown')} with current value: {e}")
                enhanced_alerts.append(alert)  # Add without enhancement
        
        # Legacy price alerts count for backward compatibility
        price_alerts_count = len([alert for alert in enhanced_alerts if alert.get("alert_type") == "price"])
        logging.info(f"Filtered to {price_alerts_count} non-triggered price alerts")

        # Build response message for backward compatibility
        message = "📊 Current Alerts:\n\n"

        # Group price alerts by type for display
        price_alerts_for_display = [a for a in enhanced_alerts if a.get("alert_type") == "price"]
        single_alerts = [a for a in price_alerts_for_display if a.get("type") == "single"]
        ratio_alerts = [a for a in price_alerts_for_display if a.get("type") == "ratio"]

        if single_alerts:
            message += "🎯 Single Symbol Price Alerts:\n"
            for alert in single_alerts:
                message += f"Symbol: {alert['symbol']}\n"
                message += f"Target Price: ${alert['price']} {alert['operator']}\n"
                
                # Add current value to message
                if "current_value" in alert and alert["current_value"].get("current_price"):
                    current = alert["current_value"]
                    message += f"Current Price: ${current['current_price']:.4f}\n"
                    if "price_range" in current:
                        message += f"24h Range: ${current['price_range']['low']:.4f}-${current['price_range']['high']:.4f}\n"
                
                message += f"Description: {alert['description']}\n"

                # Display triggers if present
                if "triggers" in alert and alert["triggers"]:
                    message += "Triggers:\n"
                    for trigger in alert["triggers"]:
                        if trigger["type"] == "bybit_action":
                            message += f"- Bybit: {trigger['action']}\n"

                            # Display additional action parameters based on action type
                            if trigger["action"] == "open_position":
                                params = trigger.get("params", {})
                                message += f"  Side: {params.get('side', 'N/A')}\n"
                                message += f"  Quantity: {params.get('qty', 'N/A')}\n"
                                if "leverage" in params:
                                    message += f"  Leverage: {params.get('leverage')}x\n"
                            elif trigger["action"] == "set_tp_sl":
                                params = trigger.get("params", {})
                                if "take_profit" in params:
                                    message += f"  Take Profit: ${params.get('take_profit')}\n"
                                if "stop_loss" in params:
                                    message += f"  Stop Loss: ${params.get('stop_loss')}\n"

                message += "---------------\n"

        if ratio_alerts:
            message += "\n📈 Ratio Price Alerts:\n"
            for alert in ratio_alerts:
                message += f"Pair: {alert['symbol1']}/{alert['symbol2']}\n"
                message += f"Target Ratio: {alert['price']} {alert['operator']}\n"
                
                # Add current ratio to message
                if "current_value" in alert and alert["current_value"].get("current_ratio"):
                    current = alert["current_value"]
                    message += f"Current Ratio: {current['current_ratio']:.6f}\n"
                    message += f"Prices: {alert['symbol1']}=${current['symbol1_price']:.4f}, {alert['symbol2']}=${current['symbol2_price']:.4f}\n"
                
                message += f"Description: {alert['description']}\n"

                # Display triggers if present
                if "triggers" in alert and alert["triggers"]:
                    message += "Triggers:\n"
                    for trigger in alert["triggers"]:
                        if trigger["type"] == "bybit_action":
                            message += f"- Bybit: {trigger['action']}\n"

                            # Display additional action parameters based on action type
                            if trigger["action"] == "open_position":
                                params = trigger.get("params", {})
                                message += f"  Side: {params.get('side', 'N/A')}\n"
                                message += f"  Quantity: {params.get('qty', 'N/A')}\n"
                                if "leverage" in params:
                                    message += f"  Leverage: {params.get('leverage')}x\n"
                            elif trigger["action"] == "set_tp_sl":
                                params = trigger.get("params", {})
                                if "take_profit" in params:
                                    message += f"  Take Profit: ${params.get('take_profit')}\n"
                                if "stop_loss" in params:
                                    message += f"  Stop Loss: ${params.get('stop_loss')}\n"

                message += "---------------\n"

        # Add indicator alerts with current values
        indicator_alerts_for_display = [a for a in enhanced_alerts if a.get("alert_type") == "indicator"]
        if indicator_alerts_for_display:
            message += "\n📊 RSI Indicator Alerts:\n"
            for alert in indicator_alerts_for_display:
                message += f"Symbol: {alert['symbol']}\n"
                message += f"Indicator: {alert['indicator_type'].upper()}\n"
                message += f"Condition: {alert['condition']}\n"
                
                # Add current RSI value
                if "current_value" in alert and alert["current_value"].get("current_rsi"):
                    current = alert["current_value"]
                    message += f"Current RSI: {current['current_rsi']:.2f}\n"
                    message += f"Current Price: ${current['current_price']:.4f}\n"
                    if current.get("rsi_status"):
                        status = current["rsi_status"]
                        if status.get("is_overbought"):
                            message += "Status: 🔴 Overbought\n"
                        elif status.get("is_oversold"):
                            message += "Status: 🟢 Oversold\n"
                        else:
                            message += f"Status: ⚪ Neutral\n"
                
                message += f"Config: RSI({alert['config']['period']}) - OB:{alert['config']['overbought_level']} OS:{alert['config']['oversold_level']}\n"
                message += f"Timeframe: {alert['config']['timeframe']}\n"
                message += f"Description: {alert['description']}\n"
                message += f"Enabled: {'Yes' if alert['enabled'] else 'No'}\n"
                message += "---------------\n"

        # Return enhanced response
        response_data = {
            "alerts": enhanced_alerts,  # Now includes current_value field
            "summary": {
                "total_alerts": len(enhanced_alerts),
                "price_alerts": len([a for a in enhanced_alerts if a.get("alert_type") == "price"]),
                "indicator_alerts": len([a for a in enhanced_alerts if a.get("alert_type") == "indicator"]),
                "filters_applied": {
                    "type": alert_type,
                    "symbol": symbol_filter,
                    "enabled": enabled_filter
                }
            },
            "message": message  # For backward compatibility
        }

        return func.HttpResponse(
            body=json.dumps(response_data),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        app_logger.error(f"Error in get_all_alerts: {str(e)}")
        app_logger.error(f"Error type: {type(e).__name__}")
        app_logger.error("Error details: ", exc_info=True)  # This will log the full stack trace
        return func.HttpResponse(
            body=json.dumps({"error": str(e), "error_type": type(e).__name__}),
            mimetype="application/json",
            status_code=500,
        )
