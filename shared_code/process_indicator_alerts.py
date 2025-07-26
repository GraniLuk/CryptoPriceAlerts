from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from shared_code.indicators.rsi_calculator import RSICalculator
from shared_code.utils import send_telegram_message
from datetime import datetime
import os
from telegram_logging_handler import app_logger

async def process_indicator_alerts():
    """Process all indicator-based alerts"""
    try:
        table_storage = AlertTableStorage()
        
        if not table_storage.service_client:
            app_logger.warning("Table storage not available, skipping indicator alerts")
            return
            
        indicator_table = table_storage.get_table_client("indicatoralerts")
        
        if not indicator_table:
            app_logger.warning("Indicator alerts table not available")
            return
        
        # Get all active indicator alerts
        filter_query = "Enabled eq true and TriggeredDate eq ''"
        alerts = list(indicator_table.query_entities(filter_query))
        
        if not alerts:
            app_logger.info("No active indicator alerts found")
            return
        
        app_logger.info(f"Processing {len(alerts)} indicator alerts")
        
        any_alert_triggered = False
        
        for alert_entity in alerts:
            try:
                alert = IndicatorAlert.from_table_entity(alert_entity)
                
                if alert.indicator_type == "rsi":
                    triggered = await process_rsi_alert(alert)
                    if triggered:
                        # Update the alert as triggered
                        alert.triggered_date = datetime.now().isoformat()
                        indicator_table.update_entity(alert.to_table_entity())
                        any_alert_triggered = True
                        app_logger.info(f"RSI alert triggered and updated: {alert.id}")
                else:
                    app_logger.warning(f"Unknown indicator type: {alert.indicator_type}")
                    
            except Exception as e:
                app_logger.error(f"Error processing indicator alert {alert_entity.get('RowKey', 'unknown')}: {e}")
                continue
        
        if any_alert_triggered:
            app_logger.info("Indicator alerts processing completed with triggers")
        else:
            app_logger.info("Indicator alerts processing completed - no triggers")
        
    except Exception as e:
        app_logger.error(f"Error processing indicator alerts: {e}")

async def process_rsi_alert(alert: IndicatorAlert) -> bool:
    """Process a single RSI alert"""
    try:
        config = alert.config
        rsi_calculator = RSICalculator(period=config.get("period", 14))
        
        # Get RSI data for the symbol
        rsi_data = rsi_calculator.get_rsi_data(
            symbol=alert.symbol,
            timeframe=config.get("timeframe", "5m"),
            overbought=config.get("overbought_level", 70),
            oversold=config.get("oversold_level", 30)
        )
        
        if not rsi_data:
            app_logger.warning(f"Could not get RSI data for {alert.symbol}")
            return False
        
        condition_met = False
        message = f"🔔 RSI Alert for {alert.symbol}!\n"
        
        # Check different RSI conditions
        if alert.condition == "overbought" and rsi_data.is_overbought:
            condition_met = True
            message += f"📈 RSI is OVERBOUGHT: {rsi_data.value:.2f}\n"
        elif alert.condition == "oversold" and rsi_data.is_oversold:
            condition_met = True
            message += f"📉 RSI is OVERSOLD: {rsi_data.value:.2f}\n"
        elif alert.condition == "crossover_overbought":
            # RSI crossed above overbought level
            overbought_level = config.get("overbought_level", 70)
            if (rsi_data.value >= overbought_level and 
                rsi_data.previous_value < overbought_level):
                condition_met = True
                message += f"🔺 RSI crossed above overbought level ({overbought_level}): {rsi_data.value:.2f}\n"
        elif alert.condition == "crossover_oversold":
            # RSI crossed below oversold level
            oversold_level = config.get("oversold_level", 30)
            if (rsi_data.value <= oversold_level and 
                rsi_data.previous_value > oversold_level):
                condition_met = True
                message += f"🔻 RSI crossed below oversold level ({oversold_level}): {rsi_data.value:.2f}\n"
        elif alert.condition == "exit_overbought":
            # RSI exited overbought (crossed back below overbought level)
            overbought_level = config.get("overbought_level", 70)
            if (rsi_data.value < overbought_level and 
                rsi_data.previous_value >= overbought_level):
                condition_met = True
                message += f"🔄 RSI exited overbought zone: {rsi_data.value:.2f}\n"
        elif alert.condition == "exit_oversold":
            # RSI exited oversold (crossed back above oversold level)
            oversold_level = config.get("oversold_level", 30)
            if (rsi_data.value > oversold_level and 
                rsi_data.previous_value <= oversold_level):
                condition_met = True
                message += f"🔄 RSI exited oversold zone: {rsi_data.value:.2f}\n"
        
        if condition_met:
            # Add additional RSI information
            message += f"Previous RSI: {rsi_data.previous_value:.2f}\n"
            message += f"Trend: {rsi_data.trend.upper()}\n"
            message += f"Timeframe: {config.get('timeframe', '5m')}\n"
            message += f"Description: {alert.description}"
            
            # Send Telegram notification
            try:
                telegram_enabled = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
                if telegram_enabled:
                    telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
                    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
                    
                    if telegram_token and telegram_chat_id:
                        await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
                    else:
                        app_logger.warning("Telegram enabled but token or chat_id missing")
                else:
                    app_logger.info("Telegram notifications disabled")
            except Exception as e:
                app_logger.error(f"Error sending Telegram message for alert {alert.id}: {e}")
            
            app_logger.info(f"RSI alert triggered for {alert.symbol}: {alert.condition} at {rsi_data.value:.2f}")
            return True
        else:
            app_logger.debug(f"RSI condition not met for {alert.symbol}: {alert.condition}, RSI={rsi_data.value:.2f}")
        
        return False
        
    except Exception as e:
        app_logger.error(f"Error processing RSI alert for {alert.symbol}: {e}")
        return False
