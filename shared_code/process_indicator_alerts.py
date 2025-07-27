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
                        # Note: triggered_date is not automatically set - manual control required
                        any_alert_triggered = True
                        app_logger.info(f"RSI alert triggered: {alert.id}")
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
    """Process a single RSI alert - triggers on any threshold crossover"""
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
        
        # Check for any RSI threshold crossovers
        overbought_level = config.get("overbought_level", 70)
        oversold_level = config.get("oversold_level", 30)
        
        # RSI crossed above overbought level
        if (rsi_data.value >= overbought_level and 
            rsi_data.previous_value < overbought_level):
            condition_met = True
            message += f"🔺 RSI crossed above overbought level ({overbought_level}): {rsi_data.value:.2f}\n"
        # RSI crossed below oversold level
        elif (rsi_data.value <= oversold_level and 
              rsi_data.previous_value > oversold_level):
            condition_met = True
            message += f"🔻 RSI crossed below oversold level ({oversold_level}): {rsi_data.value:.2f}\n"
        # RSI exited overbought (crossed back below overbought level)
        elif (rsi_data.value < overbought_level and 
              rsi_data.previous_value >= overbought_level):
            condition_met = True
            message += f"🔄 RSI exited overbought zone: {rsi_data.value:.2f}\n"
        # RSI exited oversold (crossed back above oversold level)
        elif (rsi_data.value > oversold_level and 
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
            
            # Determine which condition was triggered for logging
            if rsi_data.value >= overbought_level and rsi_data.previous_value < overbought_level:
                condition_type = "crossover_overbought"
            elif rsi_data.value <= oversold_level and rsi_data.previous_value > oversold_level:
                condition_type = "crossover_oversold"
            elif rsi_data.value < overbought_level and rsi_data.previous_value >= overbought_level:
                condition_type = "exit_overbought"
            else:
                condition_type = "exit_oversold"
                
            app_logger.info(f"RSI alert triggered for {alert.symbol}: {condition_type} at {rsi_data.value:.2f}")
            return True
        else:
            app_logger.debug(f"No RSI threshold crossover for {alert.symbol}: RSI={rsi_data.value:.2f}, Previous={rsi_data.previous_value:.2f}")
        
        return False
        
    except Exception as e:
        app_logger.error(f"Error processing RSI alert for {alert.symbol}: {e}")
        return False
