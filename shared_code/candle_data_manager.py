from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
from shared_code.price_check import get_crypto_candle_historical
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import CandleData
from telegram_logging_handler import app_logger

class CandleDataManager:
    """Manages candle data storage and retrieval for indicator calculations"""
    
    def __init__(self):
        self.table_storage = AlertTableStorage()
        self.candle_table = self.table_storage.get_table_client("candledata") if self.table_storage.service_client else None
        
    def fetch_and_store_candles(self, symbol: str, timeframe: str, limit: int = 100) -> bool:
        """Fetch candles using existing price_check methods and store in Azure Table Storage"""
        try:
            if not self.candle_table:
                app_logger.warning("Candle table not available, skipping storage")
                return False
                
            # Fetch historical candles using the enhanced price check system
            historical_candles = get_crypto_candle_historical(symbol, timeframe, limit)
            
            if not historical_candles:
                # Fallback: create a single candle from current price if no historical data
                from shared_code.price_check import get_crypto_candle
                current_candle = get_crypto_candle(symbol)
                if current_candle:
                    single_candle = CandleData(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=datetime.now(),
                        open=current_candle.open,
                        high=current_candle.high,
                        low=current_candle.low,
                        close=current_candle.close,
                        volume=0.0  # Volume not available from current method
                    )
                    self.candle_table.upsert_entity(single_candle.to_table_entity())
                    app_logger.info(f"Stored 1 current candle for {symbol} {timeframe}")
                    return True
                return False
            
            candles_stored = 0
            for candle_data in historical_candles:
                candle = CandleData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=candle_data['timestamp'],
                    open=candle_data['open'],
                    high=candle_data['high'],
                    low=candle_data['low'],
                    close=candle_data['close'],
                    volume=candle_data.get('volume', 0.0)
                )
                
                # Use upsert to handle duplicates gracefully
                self.candle_table.upsert_entity(candle.to_table_entity())
                candles_stored += 1
            
            app_logger.info(f"Stored {candles_stored} candles for {symbol} {timeframe}")
            return True
            
        except Exception as e:
            app_logger.error(f"Error fetching/storing candles for {symbol}: {e}")
            return False
    
    def get_historical_candles(self, symbol: str, timeframe: str, count: int) -> List[CandleData]:
        """Retrieve historical candles for indicator calculation"""
        try:
            if not self.candle_table:
                app_logger.warning("Candle table not available, returning empty list")
                return []
                
            partition_key = f"{symbol}_{timeframe}"
            
            # Query last 'count' candles, ordered by timestamp (RowKey is timestamp)
            filter_query = f"PartitionKey eq '{partition_key}'"
            entities = list(self.candle_table.query_entities(filter_query))
            
            # Sort by RowKey (timestamp as integer) descending and take last 'count' items
            entities.sort(key=lambda x: int(x["RowKey"]), reverse=True)
            entities = entities[:count]
            
            # Convert to CandleData objects and reverse to get chronological order
            candles = []
            for entity in entities:
                try:
                    # Handle datetime field properly
                    timestamp_value = entity.get("Timestamp")
                    if isinstance(timestamp_value, str):
                        timestamp = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                    elif timestamp_value is None:
                        # Fallback: use RowKey as timestamp
                        timestamp = datetime.fromtimestamp(int(entity["RowKey"]))
                    else:
                        timestamp = timestamp_value
                    
                    candle = CandleData(
                        symbol=entity["Symbol"],
                        timeframe=entity["Timeframe"],
                        timestamp=timestamp,
                        open=float(entity["Open"]),
                        high=float(entity["High"]),
                        low=float(entity["Low"]),
                        close=float(entity["Close"]),
                        volume=float(entity["Volume"])
                    )
                    candles.append(candle)
                except Exception as e:
                    app_logger.warning(f"Skipping invalid candle entity: {e}")
                    continue
            
            candles.reverse()  # Oldest to newest
            return candles
            
        except Exception as e:
            app_logger.error(f"Error retrieving candles for {symbol}: {e}")
            return []
    
    def get_closing_prices(self, symbol: str, timeframe: str, count: int) -> List[float]:
        """Get just closing prices for RSI calculation"""
        candles = self.get_historical_candles(symbol, timeframe, count)
        return [candle.close for candle in candles]
    
    def ensure_sufficient_data(self, symbol: str, timeframe: str, required_count: int) -> bool:
        """Ensure we have enough historical data, fetch if needed"""
        try:
            if not self.candle_table:
                app_logger.warning("Candle table not available, cannot ensure data")
                return False
                
            current_candles = self.get_historical_candles(symbol, timeframe, required_count)
            
            if len(current_candles) >= required_count:
                # Check if data is recent (within last hour for shorter timeframes)
                latest_candle = max(current_candles, key=lambda x: x.timestamp)
                time_diff = datetime.now() - latest_candle.timestamp
                
                # Define freshness requirements based on timeframe
                freshness_limits = {
                    "1m": timedelta(minutes=5),
                    "5m": timedelta(minutes=15),
                    "15m": timedelta(minutes=30),
                    "1h": timedelta(hours=2),
                    "4h": timedelta(hours=6),
                    "1d": timedelta(hours=25)
                }
                
                if time_diff <= freshness_limits.get(timeframe, timedelta(hours=1)):
                    return True
            
            # Need to fetch more/newer data
            fetch_count = max(required_count * 2, 100)  # Fetch extra for buffer
            return self.fetch_and_store_candles(symbol, timeframe, fetch_count)
            
        except Exception as e:
            app_logger.error(f"Error ensuring data for {symbol}: {e}")
            return False
