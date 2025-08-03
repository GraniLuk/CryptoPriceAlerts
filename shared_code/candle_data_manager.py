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
        self._cache = {}  # In-memory cache
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._dedup_cache = {}  # Deduplication cache for recent saves
        self._dedup_ttl = 60  # 1 minute deduplication window
    
    def store_current_candle(self, symbol: str, candle_data: CandleData, timeframe: str = "5m") -> bool:
        """Store a single current candle with deduplication"""
        try:
            if not self.candle_table:
                return False
            
            # Create deduplication key
            dedup_key = f"{symbol}_{timeframe}_{candle_data.timestamp.replace(second=0, microsecond=0)}"
            current_time = datetime.now()
            
            # Check if we recently saved this exact candle
            if dedup_key in self._dedup_cache:
                last_save_time = self._dedup_cache[dedup_key]
                if (current_time - last_save_time).total_seconds() < self._dedup_ttl:
                    app_logger.debug(f"Skipping duplicate candle save for {symbol} at {candle_data.timestamp}")
                    return True  # Return True since data is already saved
            
            # Use upsert to handle duplicates at storage level
            entity = candle_data.to_table_entity()
            self.candle_table.upsert_entity(entity)
            
            # Update caches
            cache_key = f"{symbol}_{timeframe}_latest"
            self._cache[cache_key] = (candle_data, current_time)
            self._dedup_cache[dedup_key] = current_time
            
            # Clean old dedup entries periodically
            self._cleanup_dedup_cache()
            
            return True
            
        except Exception as e:
            app_logger.error(f"Error storing candle for {symbol}: {e}")
            return False
    
    def _cleanup_dedup_cache(self):
        """Clean old entries from deduplication cache"""
        if len(self._dedup_cache) > 1000:  # Clean when cache gets large
            current_time = datetime.now()
            keys_to_remove = []
            
            for key, timestamp in self._dedup_cache.items():
                if (current_time - timestamp).total_seconds() > self._dedup_ttl * 2:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._dedup_cache[key]
    
    def get_latest_candle(self, symbol: str, timeframe: str = "5m") -> Optional[CandleData]:
        """Get latest candle from storage"""
        try:
            if not self.candle_table:
                return None
                
            partition_key = f"{symbol}_{timeframe}"
            filter_query = f"PartitionKey eq '{partition_key}'"
            entities = list(self.candle_table.query_entities(filter_query))
            
            if not entities:
                return None
            
            # Sort by RowKey (timestamp) descending and get the latest
            entities.sort(key=lambda x: int(x["RowKey"]), reverse=True)
            latest_entity = entities[0]
            
            # Handle datetime field properly
            timestamp_value = latest_entity.get("Timestamp")
            if isinstance(timestamp_value, str):
                timestamp = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            elif timestamp_value is None:
                timestamp = datetime.fromtimestamp(int(latest_entity["RowKey"]))
            else:
                timestamp = timestamp_value
            
            return CandleData(
                symbol=latest_entity["Symbol"],
                timeframe=latest_entity["Timeframe"],
                timestamp=timestamp,
                open=float(latest_entity["Open"]),
                high=float(latest_entity["High"]),
                low=float(latest_entity["Low"]),
                close=float(latest_entity["Close"]),
                volume=float(latest_entity["Volume"])
            )
            
        except Exception as e:
            app_logger.error(f"Error getting latest candle for {symbol}: {e}")
            return None
    
    def get_latest_candle_with_fallback(self, symbol: str, timeframe: str = "5m") -> Optional[CandleData]:
        """Get latest candle with intelligent fallback to live data"""
        try:
            # First try cache
            cache_key = f"{symbol}_{timeframe}_latest"
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if (datetime.now() - timestamp).seconds < self._cache_ttl:
                    return cached_data
            
            # Then try storage
            latest_stored = self.get_latest_candle(symbol, timeframe)
            if latest_stored:
                # Check if stored data is recent enough (within 10 minutes)
                time_diff = datetime.now() - latest_stored.timestamp
                if time_diff.total_seconds() <= 600:  # 10 minutes
                    return latest_stored
            
            # If no recent data, trigger live fetch which will auto-save
            from shared_code.price_check import get_crypto_candle
            live_candle = get_crypto_candle(symbol, timeframe, auto_save=True)
            
            if live_candle:
                # Convert to CandleData format
                candle_data = CandleData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.now(),
                    open=live_candle.open,
                    high=live_candle.high,
                    low=live_candle.low,
                    close=live_candle.close,
                    volume=0.0  # Volume not available from legacy methods
                )
                return candle_data
            
        except Exception as e:
            app_logger.error(f"Error getting latest candle with fallback for {symbol}: {e}")
        
        return None
        
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
