from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from shared_code.indicators.rsi_calculator import RSICalculator
from shared_code.utils import send_telegram_message
from datetime import datetime, timezone
import os
from telegram_logging_handler import app_logger

def should_check_timeframe(timeframe: str) -> bool:
    """
    Determine if it's the right time to check alerts for a given timeframe.
    Returns True if we're within 5 minutes after a new candle should have formed.
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Map timeframe to minutes
        timeframe_minutes = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080
        }
        
        interval_minutes = timeframe_minutes.get(timeframe.lower())
        if not interval_minutes:
            app_logger.warning(f"Unknown timeframe: {timeframe}, defaulting to check")
            return True
        
        # For timeframes 5 minutes or less, always check (too frequent to optimize)
        if interval_minutes <= 5:
            return True
        
        # Calculate minutes since the epoch
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        minutes_since_epoch = int((now - epoch).total_seconds() / 60)
        
        # Calculate how many minutes past the last candle boundary we are
        minutes_past_boundary = minutes_since_epoch % interval_minutes
        
        # Check if we're within 5 minutes after a new candle boundary
        # This gives enough time for the new candle data to be available
        is_time_to_check = minutes_past_boundary <= 5
        
        if not is_time_to_check:
            app_logger.debug(f"Skipping {timeframe} check - {minutes_past_boundary} minutes past boundary (waiting for ≤5 minutes)")
        
        return is_time_to_check
        
    except Exception as e:
        app_logger.error(f"Error checking timeframe timing for {timeframe}: {e}")
        return True  # Default to checking if there's an error

async def process_indicator_alerts():
    """Process all indicator-based alerts, but only when it's time for new candle data"""
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
        
        # Group alerts by timeframe to optimize checking
        alerts_by_timeframe = {}
        for alert_entity in alerts:
            try:
                alert = IndicatorAlert.from_table_entity(alert_entity)
                timeframe = alert.config.get("timeframe", "5m")
                
                if timeframe not in alerts_by_timeframe:
                    alerts_by_timeframe[timeframe] = []
                alerts_by_timeframe[timeframe].append(alert)
                
            except Exception as e:
                app_logger.error(f"Error parsing alert {alert_entity.get('RowKey', 'unknown')}: {e}")
                continue
        
        app_logger.info(f"Found alerts for timeframes: {list(alerts_by_timeframe.keys())}")
        
        any_alert_triggered = False
        alerts_processed = 0
        alerts_skipped = 0
        
        for timeframe, timeframe_alerts in alerts_by_timeframe.items():
            # Check if it's time to process alerts for this timeframe
            if not should_check_timeframe(timeframe):
                app_logger.debug(f"Skipping {len(timeframe_alerts)} alerts for timeframe {timeframe} - not time for new candle")
                alerts_skipped += len(timeframe_alerts)
                continue
            
            app_logger.info(f"Processing {len(timeframe_alerts)} alerts for timeframe {timeframe}")
            
            for alert in timeframe_alerts:
                try:
                    if alert.indicator_type == "rsi":
                        triggered = await process_rsi_alert(alert)
                        if triggered:
                            # Note: triggered_date is not automatically set - manual control required
                            any_alert_triggered = True
                            app_logger.info(f"RSI alert triggered: {alert.id}")
                        alerts_processed += 1
                    else:
                        app_logger.warning(f"Unknown indicator type: {alert.indicator_type}")
                        
                except Exception as e:
                    app_logger.error(f"Error processing indicator alert {alert.id}: {e}")
                    continue
        
        app_logger.info(f"Alerts processed: {alerts_processed}, skipped: {alerts_skipped}")
        
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
        timeframe = config.get("timeframe", "5m")
        
        app_logger.debug(f"Checking RSI alert for {alert.symbol} on {timeframe} timeframe")
        
        rsi_calculator = RSICalculator(period=config.get("period", 14))
        
        # Get RSI data for the symbol
        rsi_data = rsi_calculator.get_rsi_data(
            symbol=alert.symbol,
            timeframe=timeframe,
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
            message += f"Timeframe: {timeframe}\n"
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
