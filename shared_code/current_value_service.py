from typing import Optional, Dict, Any
from shared_code.candle_data_manager import CandleDataManager
from shared_code.indicators.rsi_calculator import RSICalculator
from datetime import datetime
from telegram_logging_handler import app_logger

class CurrentValueService:
    """Service for fetching current values for all alert types"""
    
    def __init__(self):
        self.candle_manager = CandleDataManager()
        self.rsi_calculator = RSICalculator()
    
    def get_single_alert_current_value(self, symbol: str) -> Dict[str, Any]:
        """Get current value for single symbol alert"""
        try:
            # Use the enhanced fallback method that auto-fetches if needed
            latest_candle = self.candle_manager.get_latest_candle_with_fallback(symbol, "5m")
            
            if latest_candle:
                return {
                    "current_price": latest_candle.close,
                    "price_range": {
                        "low": latest_candle.low,
                        "high": latest_candle.high
                    },
                    "last_updated": latest_candle.timestamp.isoformat(),
                    "source": "auto_saved_data"
                }
            
        except Exception as e:
            app_logger.error(f"Error getting current value for {symbol}: {e}")
        
        return {
            "current_price": None,
            "error": "Unable to fetch current price"
        }
    
    def get_ratio_alert_current_value(self, symbol1: str, symbol2: str) -> Dict[str, Any]:
        """Get current value for ratio alert - now leverages auto-saved data"""
        try:
            value1 = self.get_single_alert_current_value(symbol1)
            value2 = self.get_single_alert_current_value(symbol2)
            
            if value1.get("current_price") and value2.get("current_price"):
                ratio = value1["current_price"] / value2["current_price"]
                
                return {
                    "current_ratio": ratio,
                    "symbol1_price": value1["current_price"],
                    "symbol2_price": value2["current_price"],
                    "last_updated": max(value1.get("last_updated", ""), value2.get("last_updated", "")),
                    "source": "auto_saved_data"
                }
            
        except Exception as e:
            app_logger.error(f"Error getting ratio value for {symbol1}/{symbol2}: {e}")
        
        return {
            "current_ratio": None,
            "error": "Unable to calculate current ratio"
        }
    
    def get_indicator_alert_current_value(self, symbol: str, indicator_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get current indicator value using auto-saved data"""
        try:
            if indicator_type.lower() == "rsi":
                timeframe = config.get("timeframe", "5m")
                period = config.get("period", 14)
                
                # Set calculator period
                self.rsi_calculator.period = period
                
                # Get RSI data (this will use stored candles that were auto-saved)
                rsi_data = self.rsi_calculator.get_rsi_data(symbol, timeframe)
                
                if rsi_data:
                    # Get current price using auto-saved data
                    price_data = self.get_single_alert_current_value(symbol)
                    
                    return {
                        "current_rsi": rsi_data.value,
                        "rsi_status": {
                            "is_overbought": rsi_data.is_overbought,
                            "is_oversold": rsi_data.is_oversold,
                            "trend": rsi_data.trend
                        },
                        "current_price": price_data.get("current_price"),
                        "config": {
                            "period": period,
                            "timeframe": timeframe,
                            "overbought_level": config.get("overbought_level", 70),
                            "oversold_level": config.get("oversold_level", 30)
                        },
                        "last_updated": datetime.now().isoformat()
                    }
            
        except Exception as e:
            app_logger.error(f"Error getting indicator value for {symbol}: {e}")
        
        return {
            "current_rsi": None,
            "error": "Unable to calculate current RSI"
        }
