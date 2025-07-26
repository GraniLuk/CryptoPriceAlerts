"""
Test script for timer function integration with both price and indicator alerts
"""
import asyncio
import logging
import sys
import os
import uuid
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert, RSIIndicatorConfig
from shared_code.process_alerts import process_alerts
from shared_code.process_indicator_alerts import process_indicator_alerts

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def cleanup_test_data(table_storage):
    """Clean up test data from tables"""
    if not table_storage.service_client:
        return
        
    # Clean up indicator alerts
    indicator_table = table_storage.get_table_client("indicatoralerts")
    if indicator_table:
        try:
            test_entities = indicator_table.query_entities("PartitionKey eq 'indicator_TESTTIMER'")
            for entity in test_entities:
                indicator_table.delete_entity(entity["PartitionKey"], entity["RowKey"])
            logger.info("Cleaned up test indicator alerts")
        except Exception as e:
            logger.warning(f"Could not clean up indicator alerts: {e}")

async def test_timer_integration():
    """Test that both price and indicator alerts can be processed by timer functions"""
    
    table_storage = AlertTableStorage()
    
    try:
        # Clean up any existing test data
        await cleanup_test_data(table_storage)
        logger.info("Cleaned up existing test data")
        
        # Only test with indicator alerts since we have that infrastructure
        if table_storage.service_client:
            # Create test indicator alert
            test_alert = IndicatorAlert(
                id=str(uuid.uuid4()),
                symbol="TESTTIMER",
                indicator_type="rsi",
                condition="overbought",
                config={
                    "period": 14,
                    "overbought_level": 70,
                    "oversold_level": 30,
                    "timeframe": "5m"
                },
                description="Test timer integration alert",
                triggers=[{"type": "telegram", "message": "Timer test alert"}],
                created_date=datetime.now().isoformat(),
                triggered_date="",
                enabled=True
            )
            
            # Insert test alert
            indicator_table = table_storage.get_table_client("indicatoralerts")
            if indicator_table:
                entity = test_alert.to_table_entity()
                indicator_table.upsert_entity(entity)
                logger.info(f"Created test indicator alert: {test_alert.id}")
        
        # Test processing price alerts (should handle gracefully even if no alerts)
        logger.info("Testing price alert processing...")
        await process_alerts()
        
        # Test processing indicator alerts
        logger.info("Testing indicator alert processing...")
        await process_indicator_alerts()
        
        # Test both processing functions together (simulating timer function)
        logger.info("Testing combined processing (simulating timer function)...")
        await process_alerts()
        await process_indicator_alerts()
        
        logger.info("Timer integration test completed successfully!")
        
    except Exception as e:
        logger.error(f"Timer integration test failed: {e}")
        raise
    finally:
        # Clean up
        await cleanup_test_data(table_storage)
        logger.info("Cleaned up test data")

async def test_timer_function_imports():
    """Test that timer functions can import required modules"""
    
    try:
        # Test day timer imports
        from AlertsFunctionGrani import main as day_main
        logger.info("Day timer function imports successfully")
        
        # Test night timer imports
        from AlertsFunctionGraniNight import main as night_main
        logger.info("Night timer function imports successfully")
        
        logger.info("Timer function import test completed successfully!")
        
    except Exception as e:
        logger.error(f"Timer function import test failed: {e}")
        raise

def main():
    """Run all timer integration tests"""
    logger.info("Starting timer integration tests...")
    
    # Run import tests first
    asyncio.run(test_timer_function_imports())
    
    # Run integration tests
    asyncio.run(test_timer_integration())
    
    logger.info("All timer integration tests passed!")

if __name__ == "__main__":
    main()
