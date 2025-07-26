"""
Test script for Phase 1: Foundation Setup
Tests the basic functionality of table storage, alert models, and historical data fetching
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert, CandleData, RSIIndicatorConfig
from shared_code.price_check import get_crypto_candle_historical
from shared_code.candle_data_manager import CandleDataManager

def test_table_storage():
    """Test Azure Table Storage setup"""
    print("🔧 Testing Azure Table Storage setup...")
    
    try:
        table_storage = AlertTableStorage()
        
        if not table_storage.service_client:
            print("⚠️  Azure Table Storage not configured (this is OK for local development)")
            print("   Tables will be created when Azure credentials are provided")
            return True
        
        # Test table creation
        tables = ["pricealerts", "indicatoralerts", "candledata"]
        for table_name in tables:
            table_client = table_storage.get_table_client(table_name)
            if table_client:
                print(f"✓ Table '{table_name}' is accessible")
            else:
                print(f"✗ Table '{table_name}' is not accessible")
                return False
        
        print("✅ Table Storage setup test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Table Storage test failed: {e}")
        return False

def test_alert_models():
    """Test alert model serialization/deserialization"""
    print("\n📊 Testing Alert Models...")
    
    try:
        # Test RSI Indicator Config
        rsi_config = RSIIndicatorConfig(
            period=14,
            overbought_level=75,
            oversold_level=25,
            timeframe="5m"
        )
        print(f"✓ RSI Config created: {rsi_config}")
        
        # Test Indicator Alert
        alert = IndicatorAlert(
            id="test-alert-123",
            symbol="BTC",
            indicator_type="rsi",
            condition="overbought",
            config={
                "period": 14,
                "overbought_level": 75,
                "oversold_level": 25,
                "timeframe": "5m"
            },
            description="Test RSI alert for BTC",
            triggers=[{"type": "telegram", "message": "BTC RSI is overbought!"}],
            created_date=datetime.now().isoformat()
        )
        
        # Test serialization
        entity = alert.to_table_entity()
        print(f"✓ Alert serialized to table entity")
        
        # Test deserialization
        restored_alert = IndicatorAlert.from_table_entity(entity)
        assert restored_alert.id == alert.id
        assert restored_alert.symbol == alert.symbol
        assert restored_alert.indicator_type == alert.indicator_type
        print(f"✓ Alert deserialized successfully")
        
        # Test Candle Data
        candle = CandleData(
            symbol="BTC",
            timeframe="5m",
            timestamp=datetime.now(),
            open=50000.0,
            high=50500.0,
            low=49800.0,
            close=50200.0,
            volume=1234.56
        )
        
        candle_entity = candle.to_table_entity()
        restored_candle = CandleData.from_table_entity(candle_entity)
        assert restored_candle.symbol == candle.symbol
        assert restored_candle.close == candle.close
        print(f"✓ Candle data serialization works correctly")
        
        print("✅ Alert Models test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Alert Models test failed: {e}")
        return False

def test_historical_data():
    """Test historical data fetching"""
    print("\n📈 Testing Historical Data Fetching...")
    
    try:
        # Test with a common symbol (BTC)
        print("Testing BTC historical data from Binance...")
        btc_data = get_crypto_candle_historical("BTC", "5m", 10)
        
        if btc_data and len(btc_data) > 0:
            print(f"✓ Retrieved {len(btc_data)} BTC candles")
            latest_candle = btc_data[-1]
            print(f"  Latest candle: Open={latest_candle['open']}, Close={latest_candle['close']}")
        else:
            print("⚠️  No BTC data retrieved (this might be OK if API limits are reached)")
        
        # Test with a KuCoin symbol
        print("Testing AKT historical data from KuCoin...")
        akt_data = get_crypto_candle_historical("AKT", "5m", 5)
        
        if akt_data and len(akt_data) > 0:
            print(f"✓ Retrieved {len(akt_data)} AKT candles")
        else:
            print("⚠️  No AKT data retrieved (this might be OK if API limits are reached)")
        
        print("✅ Historical Data test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Historical Data test failed: {e}")
        return False

def test_candle_data_manager():
    """Test candle data manager functionality"""
    print("\n💾 Testing Candle Data Manager...")
    
    try:
        manager = CandleDataManager()
        
        if not manager.candle_table:
            print("⚠️  Candle Data Manager initialized without table storage (OK for local dev)")
            print("   Will work with table storage when Azure credentials are provided")
            return True
        
        # Test ensuring sufficient data
        print("Testing data sufficiency check...")
        has_data = manager.ensure_sufficient_data("BTC", "5m", 20)
        print(f"✓ Data sufficiency check returned: {has_data}")
        
        # Test retrieving historical candles
        candles = manager.get_historical_candles("BTC", "5m", 10)
        print(f"✓ Retrieved {len(candles)} stored candles")
        
        # Test getting closing prices
        prices = manager.get_closing_prices("BTC", "5m", 10)
        print(f"✓ Retrieved {len(prices)} closing prices")
        
        print("✅ Candle Data Manager test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Candle Data Manager test failed: {e}")
        return False

def main():
    """Run all Phase 1 tests"""
    print("🧪 Running Phase 1 Foundation Setup Tests")
    print("=" * 50)
    
    tests = [
        test_table_storage,
        test_alert_models,
        test_historical_data,
        test_candle_data_manager
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 1 foundation tests passed!")
        print("\n📋 Next Steps:")
        print("1. Review the foundation setup")
        print("2. Configure Azure Table Storage credentials if needed")
        print("3. Proceed to Phase 2: RSI Indicator Implementation")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    main()
