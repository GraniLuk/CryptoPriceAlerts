## Technical Indicators Alert System Feature

## Feature Overview

### Goal
Extend the existing crypto price alert system to support technical indicator-based alerts, starting with RSI (Relative Strength Index). This feature enables users to set alerts based on technical analysis conditions rather than just price thresholds.

### Key Components
- **Indicator Alerts**: New alert type for RSI conditions (overbought, oversold, crossovers)
- **Azure Table Storage Migration**: Move from alerts.json to scalable table storage
- **Candle Data Storage**: Dedicated table for storing historical price data needed for indicator calculations
- **RSI Calculation Engine**: Real-time RSI computation with configurable parameters
- **Enhanced API**: New endpoints for creating and managing indicator alerts

### Benefits
- **Scalability**: Azure Table Storage handles larger datasets efficiently
- **Performance**: Cached candle data enables faster indicator calculations
- **Flexibility**: Configurable indicator parameters (period, levels, timeframes)
- **Extensibility**: Foundation for adding more indicators (MACD, Bollinger Bands, etc.)
- **Reliability**: Structured data storage with proper indexing and querying

### Architecture Changes
- **Storage Layer**: Migrate from JSON files to Azure Table Storage (3 tables)
- **Data Layer**: New candle data collection and caching system
- **Processing Layer**: Enhanced alert processing with indicator calculations
- **API Layer**: New endpoints for indicator alert management

---

## Current Architecture Analysis

Your application currently has:
- **Alert Types**: Single symbol and ratio alerts stored in alerts.json
- **Storage**: Azure File Share for JSON file storage via `shared_code.utils`
- **Processing**: Timer-triggered functions (`AlertsFunctionGrani`, `AlertsFunctionGraniNight`)
- **API Endpoints**: Create (`insert_new_alert_grani`), Remove (`remove_alert_grani`), List (`get_all_alerts`)
- **Trigger System**: Bybit integration via `shared_code.process_alerts.execute_triggers`

## Iterative Implementation Plan

### Phase 1: Foundation Setup (Week 1)

#### 1.1 Azure Table Storage Setup

```python
from azure.data.tables import TableServiceClient, TableClient
from azure.core.credentials import AzureNamedKeyCredential
import os
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
from telegram_logging_handler import app_logger

class AlertTableStorage:
    """Central class for managing all Azure Table Storage operations"""
    
    def __init__(self):
        self.account_name = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT")
        self.account_key = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT_KEY")
        self.credential = AzureNamedKeyCredential(self.account_name, self.account_key)
        self.service_client = TableServiceClient(
            account_url=f"https://{self.account_name}.table.core.windows.net",
            credential=self.credential
        )
        
        # Initialize all required tables
        self._initialize_tables()
        
    def _initialize_tables(self):
        """Initialize all required tables for the alert system"""
        tables = [
            "pricealerts",      # Migrated price alerts
            "indicatoralerts",  # New indicator-based alerts
            "candledata"        # Historical candle data for indicators
        ]
        
        for table_name in tables:
            self.create_table_if_not_exists(table_name)
        
    def get_table_client(self, table_name: str) -> TableClient:
        return self.service_client.get_table_client(table_name)
    
    def create_table_if_not_exists(self, table_name: str):
        try:
            self.service_client.create_table_if_not_exists(table_name)
            app_logger.info(f"Table {table_name} ready")
        except Exception as e:
            app_logger.error(f"Error creating table {table_name}: {e}")
            
    def cleanup_old_candle_data(self, days_to_keep: int = 30):
        """Clean up old candle data to manage storage costs"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            candle_table = self.get_table_client("candledata")
            
            filter_query = f"Timestamp lt datetime'{cutoff_date.isoformat()}'"
            old_entities = candle_table.query_entities(filter_query)
            
            deleted_count = 0
            for entity in old_entities:
                candle_table.delete_entity(entity["PartitionKey"], entity["RowKey"])
                deleted_count += 1
                
            app_logger.info(f"Cleaned up {deleted_count} old candle records")
            
        except Exception as e:
            app_logger.error(f"Error cleaning up old candle data: {e}")
```

#### 1.2 Enhanced Alert Schema
```python
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

@dataclass
class RSIIndicatorConfig:
    period: int = 14
    overbought_level: float = 70
    oversold_level: float = 30
    timeframe: str = "5m"  # 1m, 5m, 15m, 1h, 4h, 1d

@dataclass
class IndicatorAlert:
    id: str
    symbol: str
    indicator_type: str  # "rsi", "macd", "bollinger", etc.
    condition: str  # "overbought", "oversold", "crossover", etc.
    config: Dict[str, Any]  # Indicator-specific configuration
    description: str
    triggers: List[Dict[str, Any]]
    created_date: str
    triggered_date: str = ""
    enabled: bool = True

    def to_table_entity(self) -> Dict[str, Any]:
        return {
            "PartitionKey": f"indicator_{self.symbol}",
            "RowKey": self.id,
            "Symbol": self.symbol,
            "IndicatorType": self.indicator_type,
            "Condition": self.condition,
            "Config": json.dumps(self.config),
            "Description": self.description,
            "Triggers": json.dumps(self.triggers),
            "CreatedDate": self.created_date,
            "TriggeredDate": self.triggered_date,
            "Enabled": self.enabled
        }
    
    @classmethod
    def from_table_entity(cls, entity: Dict[str, Any]) -> 'IndicatorAlert':
        return cls(
            id=entity["RowKey"],
            symbol=entity["Symbol"],
            indicator_type=entity["IndicatorType"],
            condition=entity["Condition"],
            config=json.loads(entity["Config"]),
            description=entity["Description"],
            triggers=json.loads(entity["Triggers"]),
            created_date=entity["CreatedDate"],
            triggered_date=entity.get("TriggeredDate", ""),
            enabled=entity.get("Enabled", True)
        )
```

#### 1.3 Candle Data Storage System

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
from shared_code.bybit_integration import get_crypto_candle
from shared_code.table_storage import AlertTableStorage

@dataclass
class CandleData:
    """Represents a single candle/OHLCV data point"""
    symbol: str
    timeframe: str  # "1m", "5m", "15m", "1h", "4h", "1d"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_table_entity(self) -> Dict[str, Any]:
        """Convert to Azure Table Storage entity"""
        return {
            "PartitionKey": f"{self.symbol}_{self.timeframe}",
            "RowKey": f"{int(self.timestamp.timestamp())}",
            "Symbol": self.symbol,
            "Timeframe": self.timeframe,
            "Timestamp": self.timestamp,
            "Open": self.open,
            "High": self.high,
            "Low": self.low,
            "Close": self.close,
            "Volume": self.volume,
            "LastUpdated": datetime.now()
        }
    
    @classmethod
    def from_table_entity(cls, entity: Dict[str, Any]) -> 'CandleData':
        """Create from Azure Table Storage entity"""
        return cls(
            symbol=entity["Symbol"],
            timeframe=entity["Timeframe"],
            timestamp=entity["Timestamp"],
            open=float(entity["Open"]),
            high=float(entity["High"]),
            low=float(entity["Low"]),
            close=float(entity["Close"]),
            volume=float(entity["Volume"])
        )

class CandleDataManager:
    """Manages candle data storage and retrieval for indicator calculations"""
    
    def __init__(self):
        self.table_storage = AlertTableStorage()
        self.candle_table = self.table_storage.get_table_client("candledata")
        
    def fetch_and_store_candles(self, symbol: str, timeframe: str, limit: int = 100) -> bool:
        """Fetch candles using existing price_check methods and store in Azure Table Storage"""
        try:
            # Import the enhanced get_crypto_candle function
            from shared_code.price_check import get_crypto_candle_historical
            
            # Fetch historical candles using the existing price check system
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
                    from telegram_logging_handler import app_logger
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
            
            from telegram_logging_handler import app_logger
            app_logger.info(f"Stored {candles_stored} candles for {symbol} {timeframe}")
            return True
            
        except Exception as e:
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error fetching/storing candles for {symbol}: {e}")
            return False
    
    def get_historical_candles(self, symbol: str, timeframe: str, count: int) -> List[CandleData]:
        """Retrieve historical candles for indicator calculation"""
        try:
            partition_key = f"{symbol}_{timeframe}"
            
            # Query last 'count' candles, ordered by timestamp (RowKey is timestamp)
            filter_query = f"PartitionKey eq '{partition_key}'"
            entities = list(self.candle_table.query_entities(
                filter_query, 
                select=["Symbol", "Timeframe", "Timestamp", "Open", "High", "Low", "Close", "Volume"]
            ))
            
            # Sort by timestamp descending and take last 'count' items
            entities.sort(key=lambda x: x["Timestamp"], reverse=True)
            entities = entities[:count]
            
            # Convert to CandleData objects and reverse to get chronological order
            candles = [CandleData.from_table_entity(entity) for entity in entities]
            candles.reverse()  # Oldest to newest
            
            return candles
            
        except Exception as e:
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error retrieving candles for {symbol}: {e}")
            return []
    
    def get_closing_prices(self, symbol: str, timeframe: str, count: int) -> List[float]:
        """Get just closing prices for RSI calculation"""
        candles = self.get_historical_candles(symbol, timeframe, count)
        return [candle.close for candle in candles]
    
    def ensure_sufficient_data(self, symbol: str, timeframe: str, required_count: int) -> bool:
        """Ensure we have enough historical data, fetch if needed"""
        try:
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
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error ensuring data for {symbol}: {e}")
            return False
```

#### 1.4 Migration Strategy
```python
from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
import json
from datetime import datetime

def migrate_existing_alerts_to_table():
    """Migrate existing alerts.json to Azure Table Storage and initialize candle data"""
    try:
        # Get existing alerts from JSON
        existing_alerts = get_alerts_from_azure("alerts.json")
        if not existing_alerts:
            print("No existing alerts found to migrate")
        
        table_storage = AlertTableStorage()
        # Tables are automatically created in AlertTableStorage.__init__()
        
        price_table = table_storage.get_table_client("pricealerts")
        
        # Initialize candle data manager for populating historical data
        from shared_code.candle_data_manager import CandleDataManager
        candle_manager = CandleDataManager()
        
        # Track unique symbols for candle data initialization
        symbols_to_populate = set()
        
        # Migrate price alerts with enhanced schema
        if existing_alerts:
            for alert in existing_alerts:
                entity = {
                    "PartitionKey": f"price_{alert.get('symbol', alert.get('symbol1', 'unknown'))}",
                    "RowKey": alert["id"],
                    "AlertType": alert.get("type", "single"),
                    "Symbol": alert.get("symbol", ""),
                    "Symbol1": alert.get("symbol1", ""),
                    "Symbol2": alert.get("symbol2", ""),
                    "Price": float(alert["price"]),
                    "Operator": alert["operator"],
                    "Description": alert["description"],
                    "Triggers": json.dumps(alert.get("triggers", [])),
                    "CreatedDate": alert.get("created_date", datetime.now().isoformat()),
                    "TriggeredDate": alert.get("triggered_date", ""),
                    "Enabled": True
                }
                price_table.upsert_entity(entity)
                
                # Collect symbols for candle data initialization
                if alert.get("symbol"):
                    symbols_to_populate.add(alert["symbol"])
                if alert.get("symbol1"):
                    symbols_to_populate.add(alert["symbol1"])
                if alert.get("symbol2"):
                    symbols_to_populate.add(alert["symbol2"])
        
        # Initialize candle data for common timeframes
        timeframes = ["5m", "15m", "1h", "4h", "1d"]
        
        # Add common symbols that might be used for indicator alerts
        common_symbols = ["BTC", "ETH", "BNB", "SOL", "ADA", "DOT", "AVAX", "MATIC"]
        symbols_to_populate.update(common_symbols)
        
        print(f"Initializing candle data for {len(symbols_to_populate)} symbols...")
        
        for symbol in symbols_to_populate:
            for timeframe in timeframes:
                success = candle_manager.fetch_and_store_candles(symbol, timeframe, 200)
                if success:
                    print(f"✓ Initialized {symbol} {timeframe} candle data")
                else:
                    print(f"✗ Failed to initialize {symbol} {timeframe} candle data")
        
        # Backup original alerts.json
        if existing_alerts:
            backup_name = f"alerts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            save_alerts_to_azure(backup_name, existing_alerts)
            print(f"Migration completed. Backup saved as {backup_name}")
        
        print("Migration and candle data initialization completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
```

#### 1.5 Enhanced Price Check Integration

```python
# Extensions to shared_code/price_check.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Timeframe mapping for different exchanges
TIMEFRAME_MAPPING = {
    "binance": {
        "1m": "1m", "5m": "5m", "15m": "15m", 
        "1h": "1h", "4h": "4h", "1d": "1d"
    },
    "kucoin": {
        "1m": "1min", "5m": "5min", "15m": "15min",
        "1h": "1hour", "4h": "4hour", "1d": "1day"
    }
}

def get_crypto_candle_historical(symbol: str, timeframe: str = "5m", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data with configurable timeframe"""
    try:
        if symbol in KUCOIN_SYMBOLS:
            return get_crypto_candle_historical_kucoin(symbol, timeframe, limit)
        elif symbol == "GST":
            # GST only has current price, so we'll create mock historical data
            current_price = get_gst_bsc_price_from_coinmarketcap()
            if current_price:
                return create_mock_historical_data(current_price, timeframe, limit)
            return None
        else:
            return get_crypto_candle_historical_binance(symbol, timeframe, limit)
    except Exception as e:
        from telegram_logging_handler import app_logger
        app_logger.error(f"Error fetching historical candles for {symbol}: {e}")
        return None

def get_crypto_candle_historical_binance(symbol: str, timeframe: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data from Binance with configurable timeframe"""
    binance_symbol = f"{symbol.upper()}USDT"
    binance_timeframe = TIMEFRAME_MAPPING["binance"].get(timeframe, "5m")
    
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={binance_timeframe}&limit={limit}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0:
                candles = []
                for candle in data:
                    # Binance kline format: [Open time, Open, High, Low, Close, Volume, ...]
                    candles.append({
                        'timestamp': datetime.fromtimestamp(int(candle[0]) / 1000),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })
                return candles
            else:
                from telegram_logging_handler import app_logger
                app_logger.error(f"No historical candle data returned for {symbol}")
                return None
        else:
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error fetching historical candles for {symbol}: {response.status_code}")
            return None
    except requests.RequestException as e:
        from telegram_logging_handler import app_logger
        app_logger.error(f"Request exception during historical candle fetch: {e}")
        return None

def get_crypto_candle_historical_kucoin(symbol: str, timeframe: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Get historical candle data from KuCoin with configurable timeframe"""
    kucoin_symbol = f"{symbol.upper()}-USDT"
    kucoin_timeframe = TIMEFRAME_MAPPING["kucoin"].get(timeframe, "5min")
    
    url = f"https://api.kucoin.com/api/v1/market/candles?type={kucoin_timeframe}&symbol={kucoin_symbol}&limit={limit}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data.get("code") == "200000" and data.get("data") and len(data["data"]) > 0:
                candles = []
                for candle in data["data"]:
                    # KuCoin candle format: [timestamp, open, close, high, low, volume, turnover]
                    candles.append({
                        'timestamp': datetime.fromtimestamp(int(candle[0])),
                        'open': float(candle[1]),
                        'high': float(candle[3]),
                        'low': float(candle[4]),
                        'close': float(candle[2]),
                        'volume': float(candle[5])
                    })
                # Sort by timestamp (oldest first) for consistent processing
                candles.sort(key=lambda x: x['timestamp'])
                return candles
            else:
                from telegram_logging_handler import app_logger
                app_logger.error(f"No historical candle data returned for {symbol} from KuCoin")
                return None
        else:
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error fetching historical candles for {symbol} from KuCoin: {response.status_code}")
            return None
    except requests.RequestException as e:
        from telegram_logging_handler import app_logger
        app_logger.error(f"Request exception during KuCoin historical candle fetch: {e}")
        return None

def create_mock_historical_data(current_price: float, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    """Create mock historical data for symbols that only have current price (like GST)"""
    candles = []
    
    # Calculate time delta based on timeframe
    time_deltas = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1)
    }
    
    delta = time_deltas.get(timeframe, timedelta(minutes=5))
    current_time = datetime.now()
    
    # Create historical data with slight price variations (±2%)
    import random
    for i in range(limit):
        timestamp = current_time - (delta * (limit - i))
        
        # Add small random variations to simulate price movement
        variation = random.uniform(-0.02, 0.02)  # ±2%
        price_with_variation = current_price * (1 + variation)
        
        # Create OHLC with small variations
        high_variation = random.uniform(0, 0.01)  # 0-1% higher
        low_variation = random.uniform(-0.01, 0)  # 0-1% lower
        
        candles.append({
            'timestamp': timestamp,
            'open': price_with_variation,
            'high': price_with_variation * (1 + high_variation),
            'low': price_with_variation * (1 + low_variation),
            'close': price_with_variation,
            'volume': 0.0  # No volume data available
        })
    
    return candles

# Enhanced get_crypto_candle method to support timeframes
def get_crypto_candle_enhanced(symbol: str, timeframe: str = "5m") -> Optional[CandleData]:
    """Enhanced version of get_crypto_candle with timeframe support"""
    # For backwards compatibility, if timeframe is 5m, use existing method
    if timeframe == "5m":
        return get_crypto_candle(symbol)
    
    # For other timeframes, get the latest candle from historical data
    historical_data = get_crypto_candle_historical(symbol, timeframe, 1)
    
    if historical_data and len(historical_data) > 0:
        latest_candle = historical_data[-1]
        return CandleData(
            open=latest_candle['open'],
            high=latest_candle['high'],
            low=latest_candle['low'],
            close=latest_candle['close']
        )
    
    # Fallback to current method if historical data unavailable
    return get_crypto_candle(symbol)
```

### Phase 2: RSI Indicator Implementation (Week 2)

#### 2.1 RSI Calculation Module
```python
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from shared_code.price_check import get_crypto_candle
from dataclasses import dataclass

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
        """Calculate RSI for given price series"""
        if len(prices) < self.period + 1:
            return None
        
        df = pd.DataFrame({'price': prices})
        delta = df['price'].diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None
    
    def get_rsi_data(self, symbol: str, timeframe: str = "5m", overbought: float = 70, oversold: float = 30) -> Optional[RSIData]:
        """Get current RSI data for symbol using stored candle data"""
        try:
            # Ensure we have sufficient candle data
            required_candles = self.period + 20  # Extra buffer for calculation accuracy
            
            if not self.candle_manager.ensure_sufficient_data(symbol, timeframe, required_candles):
                from telegram_logging_handler import app_logger
                app_logger.warning(f"Could not ensure sufficient candle data for {symbol} {timeframe}")
                return None
            
            # Get closing prices from stored candle data
            prices = self.candle_manager.get_closing_prices(symbol, timeframe, required_candles)
            
            if len(prices) < self.period + 1:
                from telegram_logging_handler import app_logger
                app_logger.warning(f"Insufficient price data for RSI calculation: {len(prices)} < {self.period + 1}")
                return None
            
            current_rsi = self.calculate_rsi(prices)
            previous_rsi = self.calculate_rsi(prices[:-1]) if len(prices) > self.period + 1 else None
            
            if current_rsi is None:
                return None
            
            # Determine trend
            trend = "neutral"
            if previous_rsi:
                if current_rsi > previous_rsi + 1:
                    trend = "rising"
                elif current_rsi < previous_rsi - 1:
                    trend = "falling"
            
            return RSIData(
                value=current_rsi,
                is_overbought=current_rsi >= overbought,
                is_oversold=current_rsi <= oversold,
                previous_value=previous_rsi or 0,
                trend=trend
            )
            
        except Exception as e:
            from telegram_logging_handler import app_logger
            app_logger.error(f"Error calculating RSI for {symbol}: {e}")
            return None
```

#### 2.2 Indicator Alert Processing
```python
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from shared_code.indicators.rsi_calculator import RSICalculator
from shared_code.process_alerts import execute_triggers, send_telegram_message
from datetime import datetime
import os
from telegram_logging_handler import app_logger

async def process_indicator_alerts():
    """Process all indicator-based alerts"""
    try:
        table_storage = AlertTableStorage()
        indicator_table = table_storage.get_table_client("indicatoralerts")
        
        # Get all active indicator alerts
        filter_query = "Enabled eq true and TriggeredDate eq ''"
        alerts = list(indicator_table.query_entities(filter_query))
        
        any_alert_triggered = False
        
        for alert_entity in alerts:
            alert = IndicatorAlert.from_table_entity(alert_entity)
            
            if alert.indicator_type == "rsi":
                triggered = await process_rsi_alert(alert)
                if triggered:
                    # Update the alert as triggered
                    alert.triggered_date = datetime.now().isoformat()
                    indicator_table.update_entity(alert.to_table_entity())
                    any_alert_triggered = True
        
        if any_alert_triggered:
            app_logger.info("Indicator alerts processing completed with triggers")
        
    except Exception as e:
        app_logger.error(f"Error processing indicator alerts: {e}")

async def process_rsi_alert(alert: IndicatorAlert) -> bool:
    """Process a single RSI alert"""
    try:
        config = alert.config
        rsi_calculator = RSICalculator(period=config.get("period", 14))
        
        rsi_data = rsi_calculator.get_rsi_data(
            symbol=alert.symbol,
            timeframe=config.get("timeframe", "5m"),
            overbought=config.get("overbought_level", 70),
            oversold=config.get("oversold_level", 30)
        )
        
        if not rsi_data:
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
        elif alert.condition == "crossover_overbought" and rsi_data.value >= config.get("overbought_level", 70) and rsi_data.previous_value < config.get("overbought_level", 70):
            condition_met = True
            message += f"🔺 RSI crossed above overbought level: {rsi_data.value:.2f}\n"
        elif alert.condition == "crossover_oversold" and rsi_data.value <= config.get("oversold_level", 30) and rsi_data.previous_value > config.get("oversold_level", 30):
            condition_met = True
            message += f"🔻 RSI crossed below oversold level: {rsi_data.value:.2f}\n"
        
        if condition_met:
            message += f"Previous RSI: {rsi_data.previous_value:.2f}\n"
            message += f"Trend: {rsi_data.trend.upper()}\n"
            message += f"Description: {alert.description}"
            
            # Execute triggers if defined
            if alert.triggers:
                trigger_results = await execute_triggers(alert.__dict__, message)
                for result in trigger_results:
                    message += f"\n\n{result}"
            
            # Send notification
            telegram_enabled = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
            telegram_token = os.environ.get("TELEGRAM_TOKEN", "") if telegram_enabled else ""
            telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "") if telegram_enabled else ""
            
            await send_telegram_message(telegram_enabled, telegram_token, telegram_chat_id, message)
            app_logger.info(f"RSI alert triggered for {alert.symbol}")
            
            return True
        
        return False
        
    except Exception as e:
        app_logger.error(f"Error processing RSI alert for {alert.symbol}: {e}")
        return False
```

### Phase 3: API Endpoints Enhancement (Week 3)

#### 3.1 Create Indicator Alert Endpoint
```python
import logging
import json
from uuid import uuid4
from datetime import datetime
import azure.functions as func
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert, RSIIndicatorConfig

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Create indicator alert function processed a request.")
    
    try:
        req_body = req.get_json()
        
        # Validate required fields
        required_fields = ["symbol", "indicator_type", "condition", "description"]
        if not all(field in req_body for field in required_fields):
            return func.HttpResponse(
                f"Missing required fields: {', '.join(required_fields)}",
                status_code=400
            )
        
        symbol = req_body["symbol"].upper()
        indicator_type = req_body["indicator_type"].lower()
        condition = req_body["condition"].lower()
        description = req_body["description"]
        
        # Validate indicator type
        if indicator_type not in ["rsi"]:  # Will expand this list
            return func.HttpResponse(
                f"Unsupported indicator type: {indicator_type}",
                status_code=400
            )
        
        # Validate and process indicator-specific config
        config = {}
        if indicator_type == "rsi":
            config = _process_rsi_config(req_body.get("config", {}))
            if not _validate_rsi_condition(condition):
                return func.HttpResponse(
                    f"Invalid RSI condition: {condition}. Valid conditions: overbought, oversold, crossover_overbought, crossover_oversold",
                    status_code=400
                )
        
        # Process triggers
        triggers = req_body.get("triggers", [])
        if triggers and not isinstance(triggers, list):
            return func.HttpResponse(
                "Triggers must be a list",
                status_code=400
            )
        
        # Create the alert
        alert = IndicatorAlert(
            id=str(uuid4()),
            symbol=symbol,
            indicator_type=indicator_type,
            condition=condition,
            config=config,
            description=description,
            triggers=triggers,
            created_date=datetime.now().isoformat()
        )
        
        # Save to table storage
        table_storage = AlertTableStorage()
        table_storage.create_table_if_not_exists("indicatoralerts")
        indicator_table = table_storage.get_table_client("indicatoralerts")
        
        indicator_table.create_entity(alert.to_table_entity())
        
        return func.HttpResponse(
            json.dumps({"message": "Indicator alert created successfully", "id": alert.id}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error creating indicator alert: {str(e)}")
        return func.HttpResponse(
            f"Error creating indicator alert: {str(e)}",
            status_code=500
        )

def _process_rsi_config(config: dict) -> dict:
    """Process and validate RSI configuration"""
    rsi_config = RSIIndicatorConfig(
        period=config.get("period", 14),
        overbought_level=config.get("overbought_level", 70),
        oversold_level=config.get("oversold_level", 30),
        timeframe=config.get("timeframe", "5m")
    )
    
    # Validate values
    if not (2 <= rsi_config.period <= 50):
        raise ValueError("RSI period must be between 2 and 50")
    
    if not (50 <= rsi_config.overbought_level <= 100):
        raise ValueError("Overbought level must be between 50 and 100")
    
    if not (0 <= rsi_config.oversold_level <= 50):
        raise ValueError("Oversold level must be between 0 and 50")
    
    if rsi_config.timeframe not in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        raise ValueError("Invalid timeframe")
    
    return {
        "period": rsi_config.period,
        "overbought_level": rsi_config.overbought_level,
        "oversold_level": rsi_config.oversold_level,
        "timeframe": rsi_config.timeframe
    }

def _validate_rsi_condition(condition: str) -> bool:
    """Validate RSI condition"""
    valid_conditions = ["overbought", "oversold", "crossover_overbought", "crossover_oversold"]
    return condition in valid_conditions
```

#### 3.2 Update Main Processing Function
```python
# ...existing code...

async def process_alerts():
    """Enhanced process_alerts to handle both price and indicator alerts"""
    try:
        # Process existing price alerts
        await _process_price_alerts()
        
        # Process new indicator alerts
        from shared_code.process_indicator_alerts import process_indicator_alerts
        await process_indicator_alerts()
        
    except Exception as e:
        app_logger.error(f"Error in enhanced process_alerts: {str(e)}")

async def _process_price_alerts():
    """Original price alert processing logic"""
    # Move existing process_alerts logic here
    # ...existing code from process_alerts function...
```

### Phase 4: Extended Alert Management (Week 4)

#### 4.1 Enhanced Get All Alerts
```python
# ...existing code...

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Enhanced get_all_alerts function processed a request.')
    
    try:
        # Get price alerts from JSON (legacy)
        price_alerts = get_alerts_from_azure("alerts.json") or []
        price_alerts = [alert for alert in price_alerts if not alert.get("triggered_date")]
        
        # Get indicator alerts from Table Storage
        table_storage = AlertTableStorage()
        indicator_alerts = []
        
        try:
            indicator_table = table_storage.get_table_client("indicatoralerts")
            filter_query = "Enabled eq true and TriggeredDate eq ''"
            indicator_entities = list(indicator_table.query_entities(filter_query))
            indicator_alerts = [IndicatorAlert.from_table_entity(entity).__dict__ for entity in indicator_entities]
        except Exception as e:
            logging.warning(f"Could not fetch indicator alerts: {e}")
        
        # Format response message
        message = "📊 Current Alerts:\n\n"
        
        # Price alerts section
        if price_alerts:
            message += "💰 Price Alerts:\n"
            # ...existing price alert formatting...
        
        # Indicator alerts section
        if indicator_alerts:
            message += "\n📈 Indicator Alerts:\n"
            for alert in indicator_alerts:
                message += f"Symbol: {alert['symbol']}\n"
                message += f"Indicator: {alert['indicator_type'].upper()}\n"
                message += f"Condition: {alert['condition']}\n"
                message += f"Description: {alert['description']}\n"
                
                if alert['indicator_type'] == 'rsi':
                    config = alert['config']
                    message += f"RSI Period: {config.get('period', 14)}\n"
                    message += f"Timeframe: {config.get('timeframe', '5m')}\n"
                    message += f"Levels: {config.get('oversold_level', 30)}/{config.get('overbought_level', 70)}\n"
                
                # Display triggers
                if alert.get('triggers'):
                    message += "Triggers: "
                    for trigger in alert['triggers']:
                        if trigger['type'] == 'bybit_action':
                            message += f"Bybit {trigger['action']}, "
                    message = message.rstrip(', ') + "\n"
                
                message += "---------------\n"
        
        return func.HttpResponse(
            body=json.dumps({
                "price_alerts": price_alerts,
                "indicator_alerts": indicator_alerts,
                "message": message
            }),
            mimetype="application/json",
            status_code=200,
        )
        
    except Exception as e:
        app_logger.error(f"Error in enhanced get_all_alerts: {str(e)}")
        return func.HttpResponse(
            body=json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500,
        )
```

#### 4.2 Remove Indicator Alert Endpoint
```python
import logging
import json
import azure.functions as func
from shared_code.table_storage import AlertTableStorage

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Remove indicator alert function processed a request.")
    
    try:
        req_body = req.get_json()
        alert_id = req_body.get("id")
        
        if not alert_id:
            return func.HttpResponse("Missing alert ID", status_code=400)
        
        table_storage = AlertTableStorage()
        indicator_table = table_storage.get_table_client("indicatoralerts")
        
        # Find the alert by ID across all partitions
        filter_query = f"RowKey eq '{alert_id}'"
        entities = list(indicator_table.query_entities(filter_query))
        
        if not entities:
            return func.HttpResponse(f"Indicator alert with ID {alert_id} not found", status_code=404)
        
        # Delete the alert
        entity = entities[0]
        indicator_table.delete_entity(entity["PartitionKey"], entity["RowKey"])
        
        return func.HttpResponse(
            json.dumps({"message": "Indicator alert removed successfully"}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error removing indicator alert: {str(e)}")
        return func.HttpResponse(f"Error removing indicator alert: {str(e)}", status_code=500)
```

### Phase 5: Documentation and Testing (Week 5)

#### 5.1 Update README.md
````markdown
# ...existing content...

## New Features - Technical Indicators

### Indicator Alerts
- Monitor technical indicators like RSI, MACD, Bollinger Bands
- Configurable parameters for each indicator
- Multiple condition types (overbought, oversold, crossovers)
- Integration with existing trigger system

### Supported Indicators
#### RSI (Relative Strength Index)
- Configurable period (default: 14)
- Custom overbought/oversold levels
- Crossover detection
- Multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)

### API Endpoints - Indicator Alerts

#### Create Indicator Alert
```http
POST /api/create_indicator_alert

# RSI Threshold Monitoring Alert (NEW - No condition parameter required)
{
    "symbol": "BTC",
    "indicator_type": "rsi",
    "description": "BTC RSI threshold monitoring - all crossovers",
    "config": {
        "period": 14,
        "overbought_level": 75,
        "oversold_level": 25,
        "timeframe": "5m"
    },
    "triggers": [
        {
            "type": "bybit_action",
            "action": "close_position",
            "params": {
                "symbol": "BTCUSDT"
            }
        }
    ]
}

# ETH RSI Alert with Standard Levels
{
    "symbol": "ETH",
    "indicator_type": "rsi",
    "description": "ETH RSI threshold monitoring",
    "config": {
        "period": 21,
        "overbought_level": 70,
        "oversold_level": 30,
        "timeframe": "15m"
    }
}
```

**Important Changes:**
- `condition` parameter is **no longer required** and will be ignored if provided
- All RSI alerts now automatically monitor for **any threshold crossover**:
  - RSI crosses above overbought level
  - RSI crosses below oversold level
  - RSI exits overbought zone (crosses back below overbought)
  - RSI exits oversold zone (crosses back above oversold)
- `triggered_date` is **NOT automatically set** - manual control required for stopping monitoring

#### Remove Indicator Alert
```http
POST /api/remove_indicator_alert
{
    "id": "indicator-alert-uuid"
}
```

## Environment Variables (Updated)
- All existing variables remain the same
- No additional environment variables required for basic indicator functionality
````

#### 5.2 Testing Strategy
```python
import unittest
from unittest.mock import patch, MagicMock
from shared_code.indicators.rsi_calculator import RSICalculator, RSIData
from shared_code.alert_models import IndicatorAlert

class TestIndicatorAlerts(unittest.TestCase):
    
    def test_rsi_calculation(self):
        """Test RSI calculation with known values"""
        calculator = RSICalculator(period=14)
        # Test with sample price data
        prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.85, 46.08, 45.89, 46.03, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
        rsi = calculator.calculate_rsi(prices)
        
        # RSI should be around 70 for this data
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 60)
        self.assertLess(rsi, 80)
    
    def test_rsi_overbought_condition(self):
        """Test RSI overbought condition detection"""
        rsi_data = RSIData(
            value=75.0,
            is_overbought=True,
            is_oversold=False,
            previous_value=65.0,
            trend="rising"
        )
        
        self.assertTrue(rsi_data.is_overbought)
        self.assertFalse(rsi_data.is_oversold)
        self.assertEqual(rsi_data.trend, "rising")

if __name__ == '__main__':
    unittest.main()
```

## Implementation Timeline Summary

| Phase | Week | Key Deliverables | Risk Level |
|-------|------|------------------|------------|
| 1 | Week 1 | Foundation Setup: Azure Table Storage (3 tables), Candle data storage system, Enhanced price_check methods, Migration tools and strategy, Enhanced alert schema | Medium |
| 2 | Week 2 | RSI Implementation: RSI calculator with table storage, Candle data fetching/caching, Indicator processing logic, Data freshness management | High |
| 3 | Week 3 | API Enhancement: Create indicator alert endpoint, Enhanced alert management, Integration with existing triggers | Medium |
| 4 | Week 4 | System Integration: Enhanced get/remove endpoints, Timer function updates, Performance optimization | Low |
| 5 | Week 5 | Testing & Deployment: Unit/integration testing, Documentation updates, Production deployment | Low |

## Storage Architecture Overview

### Table Structure
1. **`pricealerts`** - Migrated price-based alerts
   - PartitionKey: `price_{symbol}`
   - RowKey: `{alert_id}`

2. **`indicatoralerts`** - New indicator-based alerts  
   - PartitionKey: `indicator_{symbol}`
   - RowKey: `{alert_id}`

3. **`candledata`** - Historical OHLCV data
   - PartitionKey: `{symbol}_{timeframe}`
   - RowKey: `{timestamp}`
   - Auto-cleanup after 30 days

### Data Flow
```
Bybit API → CandleDataManager → Azure Table Storage → RSI Calculator → Alert Processing
```

## Required File Structure

After implementing this feature, your project structure will include:

```text
shared_code/
├── alert_models.py          # IndicatorAlert, CandleData models
├── table_storage.py         # AlertTableStorage class
├── candle_data_manager.py   # CandleDataManager class
├── price_check.py           # Enhanced with timeframe support
└── indicators/
    ├── __init__.py
    └── rsi_calculator.py     # RSICalculator and RSIData
    
create_indicator_alert/      # New Azure Function
├── __init__.py
└── function.json

remove_indicator_alert/      # New Azure Function  
├── __init__.py
└── function.json
```

## Integration with Existing System

### Key Integration Points

1. **Leverage Existing Exchange Support**
   - Your current `price_check.py` already supports multiple exchanges (Binance, KuCoin, CoinMarketCap)
   - We extend these methods to support different timeframes
   - Maintains existing logic for symbol routing (KUCOIN_SYMBOLS, GST special case)

2. **Enhanced `price_check.py` Methods**
   - `get_crypto_candle_historical()` - New method for fetching historical data
   - `get_crypto_candle_enhanced()` - Enhanced version with timeframe support
   - Timeframe mapping for different exchanges
   - Backwards compatibility maintained

3. **Candle Data Storage**
   - Uses enhanced price_check methods instead of direct Bybit API
   - Supports all your existing symbols and exchanges
   - Graceful fallback to current price if historical data unavailable

4. **Migration Strategy**
   - Preserves all existing alerts during migration
   - Pre-populates candle data for symbols from existing alerts
   - Creates backup of original alerts.json

### Changes to Existing Files

#### `shared_code/price_check.py` (Enhancements)
- Add `get_crypto_candle_historical()` function
- Add `get_crypto_candle_historical_binance()` function  
- Add `get_crypto_candle_historical_kucoin()` function
- Add `get_crypto_candle_enhanced()` function
- Add `TIMEFRAME_MAPPING` dictionary
- Add `create_mock_historical_data()` for GST-like symbols

#### Timer Functions (Minimal Changes)
- Update `AlertsFunctionGrani` and `AlertsFunctionGraniNight` to also call `process_indicator_alerts()`
- No changes to existing price alert processing

#### No Changes Required
- Existing API endpoints continue working unchanged
- Telegram integration works as-is
- Bybit trigger system works as-is
- Price caching system works as-is

## Future Extension Points

1. **Additional Indicators**: MACD, Bollinger Bands, Moving Averages
2. **Multi-timeframe Analysis**: Compare indicators across different timeframes
3. **Complex Conditions**: AND/OR logic between multiple indicators
4. **Backtesting**: Historical performance analysis of indicator strategies
5. **ML Integration**: Predictive indicators using machine learning
6. **Real-time Data**: WebSocket integration for live candle updates
7. **Advanced Alerts**: Multi-condition alerts combining price and indicators

This enhanced plan maintains backward compatibility with your existing price alerts while adding a robust, extensible framework for technical indicator alerts using Azure Table Storage with efficient candle data management.