import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from telegram_logging_handler import app_logger

@dataclass
class RSIData:
    value: float
    is_overbought: bool
    is_oversold: bool
    previous_value: float
    trend: str  # "rising", "falling", "neutral"

class RSICalculator:
    def __init__(self, period: int = 14):
        self.period = period
        from shared_code.candle_data_manager import CandleDataManager
        self.candle_manager = CandleDataManager()
    
    def calculate_rsi(self, prices: List[float]) -> Optional[float]:
        """Calculate RSI for given price series using the standard formula"""
        if len(prices) < self.period + 1:
            app_logger.warning(f"Insufficient data for RSI calculation: {len(prices)} < {self.period + 1}")
            return None
        
        try:
            # Convert to pandas DataFrame for easier calculation
            df = pd.DataFrame({'price': pd.Series(prices, dtype=float)})
            
            # Calculate price changes (deltas)
            delta = df['price'].diff()
            
            # Separate gains and losses
            gains = delta.where(delta > 0, 0.0)
            losses = -delta.where(delta < 0, 0.0)
            
            # Calculate simple moving averages of gains and losses for the first RSI value
            avg_gain = gains.rolling(window=self.period).mean()
            avg_loss = losses.rolling(window=self.period).mean()
            
            # For subsequent values, use exponential smoothing (Wilder's smoothing)
            # This is the standard RSI calculation method
            for i in range(self.period, len(gains)):
                avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (self.period - 1) + gains.iloc[i]) / self.period
                avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (self.period - 1) + losses.iloc[i]) / self.period
            
            # Calculate Relative Strength (RS)
            rs = avg_gain / avg_loss
            
            # Calculate RSI
            rsi = 100 - (100 / (1 + rs))
            
            # Return the last RSI value
            last_rsi = rsi.iloc[-1]
            
            if pd.isna(last_rsi):
                app_logger.warning("RSI calculation resulted in NaN")
                return None
                
            return float(last_rsi)
            
        except Exception as e:
            app_logger.error(f"Error calculating RSI: {e}")
            return None
    
    def get_rsi_data(self, symbol: str, timeframe: str = "5m", overbought: float = 70, oversold: float = 30) -> Optional[RSIData]:
        """Get current RSI data for symbol using stored candle data"""
        try:
            # Ensure we have sufficient candle data (need extra for accuracy)
            required_candles = self.period + 20  # Extra buffer for calculation accuracy
            
            if not self.candle_manager.ensure_sufficient_data(symbol, timeframe, required_candles):
                app_logger.warning(f"Could not ensure sufficient candle data for {symbol} {timeframe}")
                return None
            
            # Get closing prices from stored candle data
            prices = self.candle_manager.get_closing_prices(symbol, timeframe, required_candles)
            
            if len(prices) < self.period + 1:
                app_logger.warning(f"Insufficient price data for RSI calculation: {len(prices)} < {self.period + 1}")
                return None
            
            # Calculate current RSI
            current_rsi = self.calculate_rsi(prices)
            
            # Calculate previous RSI (for trend detection)
            previous_rsi = None
            if len(prices) > self.period + 1:
                previous_rsi = self.calculate_rsi(prices[:-1])
            
            if current_rsi is None:
                app_logger.warning(f"Failed to calculate RSI for {symbol}")
                return None
            
            # Determine trend
            trend = "neutral"
            if previous_rsi is not None:
                diff = current_rsi - previous_rsi
                if diff > 1:  # RSI increased by more than 1 point
                    trend = "rising"
                elif diff < -1:  # RSI decreased by more than 1 point
                    trend = "falling"
            
            rsi_data = RSIData(
                value=current_rsi,
                is_overbought=current_rsi >= overbought,
                is_oversold=current_rsi <= oversold,
                previous_value=previous_rsi or 0,
                trend=trend
            )
            
            app_logger.info(f"RSI calculated for {symbol} {timeframe}: {current_rsi:.2f} ({trend})")
            return rsi_data
            
        except Exception as e:
            app_logger.error(f"Error calculating RSI for {symbol}: {e}")
            return None
    
    def get_rsi_simple(self, prices: List[float], overbought: float = 70, oversold: float = 30) -> Optional[RSIData]:
        """Calculate RSI directly from a list of prices (for testing or simple use cases)"""
        try:
            if len(prices) < self.period + 1:
                return None
            
            current_rsi = self.calculate_rsi(prices)
            previous_rsi = self.calculate_rsi(prices[:-1]) if len(prices) > self.period + 1 else None
            
            if current_rsi is None:
                return None
            
            # Determine trend
            trend = "neutral"
            if previous_rsi is not None:
                diff = current_rsi - previous_rsi
                if diff > 1:
                    trend = "rising"
                elif diff < -1:
                    trend = "falling"
            
            return RSIData(
                value=current_rsi,
                is_overbought=current_rsi >= overbought,
                is_oversold=current_rsi <= oversold,
                previous_value=previous_rsi or 0,
                trend=trend
            )
            
        except Exception as e:
            app_logger.error(f"Error in simple RSI calculation: {e}")
            return None
