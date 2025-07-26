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
