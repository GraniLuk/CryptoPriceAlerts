from shared_code.utils import get_alerts_from_azure, save_alerts_to_azure
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
from shared_code.candle_data_manager import CandleDataManager
import json
from datetime import datetime
from telegram_logging_handler import app_logger

def migrate_existing_alerts_to_table():
    """Migrate existing alerts.json to Azure Table Storage and initialize candle data"""
    try:
        # Get existing alerts from JSON
        existing_alerts = get_alerts_from_azure("alerts.json")
        if not existing_alerts:
            print("No existing alerts found to migrate")
        
        table_storage = AlertTableStorage()
        
        # Check if table storage is available
        if not table_storage.service_client:
            print("Azure Table Storage not available, skipping migration")
            return
        
        price_table = table_storage.get_table_client("pricealerts")
        
        # Initialize candle data manager for populating historical data
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
                
                if price_table:
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
        app_logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_existing_alerts_to_table()
