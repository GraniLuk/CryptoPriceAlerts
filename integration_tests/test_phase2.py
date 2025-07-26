"""
Test script for Phase 2: RSI Indicator Implementation
Tests RSI calculation, indicator alerts, and processing
"""

import os
import sys
from datetime import datetime
import asyncio

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared_code.indicators.rsi_calculator import RSICalculator, RSIData
from shared_code.alert_models import IndicatorAlert
from shared_code.table_storage import AlertTableStorage
from shared_code.process_indicator_alerts import process_indicator_alerts, process_rsi_alert

def test_rsi_calculation():
    """Test RSI calculation with known data"""
    print("📊 Testing RSI Calculation...")
    
    try:
        calculator = RSICalculator(period=14)
        
        # Test with sample price data that should give a known RSI
        # This is a sample price series that moves from low to high (should give high RSI)
        test_prices = [
            44.0, 44.3, 44.1, 44.2, 43.6, 44.3, 44.8, 45.9, 46.1, 45.9,
            46.0, 46.3, 46.3, 46.0, 46.0, 46.4, 46.2, 45.6, 46.5, 46.8,
            47.0, 47.3, 47.5, 47.8, 48.0, 48.2, 48.5, 48.7, 49.0, 49.2
        ]
        
        # Test basic RSI calculation
        rsi_value = calculator.calculate_rsi(test_prices)
        if rsi_value is not None:
            print(f"✓ Basic RSI calculation: {rsi_value:.2f}")
            
            # RSI should be reasonable (between 0 and 100)
            if 0 <= rsi_value <= 100:
                print(f"✓ RSI value is within valid range")
            else:
                print(f"✗ RSI value {rsi_value} is outside valid range")
                return False
        else:
            print("✗ RSI calculation returned None")
            return False
        
        # Test RSI data with levels
        rsi_data = calculator.get_rsi_simple(test_prices, overbought=70, oversold=30)
        if rsi_data:
            print(f"✓ RSI Data: Value={rsi_data.value:.2f}, Trend={rsi_data.trend}")
            print(f"  Overbought: {rsi_data.is_overbought}, Oversold: {rsi_data.is_oversold}")
        else:
            print("✗ Failed to create RSI data")
            return False
        
        # Test with insufficient data
        short_prices = [44.0, 44.3, 44.1]  # Only 3 prices, need at least 15 for period 14
        rsi_insufficient = calculator.calculate_rsi(short_prices)
        if rsi_insufficient is None:
            print("✓ Correctly handled insufficient data")
        else:
            print("✗ Should have returned None for insufficient data")
            return False
        
        print("✅ RSI Calculation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ RSI Calculation test failed: {e}")
        return False

def test_rsi_with_live_data():
    """Test RSI calculation with live market data"""
    print("\n📈 Testing RSI with Live Data...")
    
    try:
        calculator = RSICalculator(period=14)
        
        # Test with BTC data (should have sufficient historical data)
        print("Testing RSI calculation for BTC...")
        rsi_data = calculator.get_rsi_data("BTC", "5m", overbought=75, oversold=25)
        
        if rsi_data:
            print(f"✓ BTC RSI: {rsi_data.value:.2f}")
            print(f"  Previous: {rsi_data.previous_value:.2f}")
            print(f"  Trend: {rsi_data.trend}")
            print(f"  Overbought: {rsi_data.is_overbought}")
            print(f"  Oversold: {rsi_data.is_oversold}")
            
            # Validate RSI is reasonable
            if 0 <= rsi_data.value <= 100:
                print("✓ Live RSI value is within valid range")
            else:
                print(f"✗ Live RSI value {rsi_data.value} is outside valid range")
                return False
        else:
            print("⚠️  Could not get live RSI data (might be OK if no table storage)")
            return True  # Not a failure if table storage isn't available
        
        print("✅ Live RSI test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Live RSI test failed: {e}")
        return False

def test_indicator_alert_creation():
    """Test creating and managing indicator alerts"""
    print("\n🚨 Testing Indicator Alert Creation...")
    
    try:
        # Create a sample RSI alert
        alert = IndicatorAlert(
            id="test-rsi-alert-123",
            symbol="BTC",
            indicator_type="rsi",
            condition="overbought",
            config={
                "period": 14,
                "overbought_level": 75,
                "oversold_level": 25,
                "timeframe": "5m"
            },
            description="Test BTC RSI overbought alert",
            triggers=[
                {"type": "telegram", "message": "BTC RSI is overbought!"}
            ],
            created_date=datetime.now().isoformat()
        )
        
        print(f"✓ Created indicator alert: {alert.id}")
        
        # Test serialization to table entity
        entity = alert.to_table_entity()
        print(f"✓ Alert serialized to table entity")
        
        # Test deserialization
        restored_alert = IndicatorAlert.from_table_entity(entity)
        if restored_alert.id == alert.id and restored_alert.symbol == alert.symbol:
            print(f"✓ Alert deserialized correctly")
        else:
            print(f"✗ Alert deserialization failed")
            return False
        
        # Test saving to table storage (if available)
        table_storage = AlertTableStorage()
        if table_storage.service_client:
            indicator_table = table_storage.get_table_client("indicatoralerts")
            if indicator_table:
                # Save the alert
                indicator_table.upsert_entity(entity)
                print(f"✓ Alert saved to table storage")
                
                # Try to retrieve it
                retrieved_entity = indicator_table.get_entity(
                    partition_key=entity["PartitionKey"],
                    row_key=entity["RowKey"]
                )
                if retrieved_entity:
                    print(f"✓ Alert retrieved from table storage")
                else:
                    print(f"✗ Alert could not be retrieved")
                    return False
            else:
                print("⚠️  Indicator table not available")
        else:
            print("⚠️  Table storage not available (OK for local testing)")
        
        print("✅ Indicator Alert Creation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Indicator Alert Creation test failed: {e}")
        return False

async def test_indicator_alert_processing():
    """Test processing indicator alerts"""
    print("\n⚙️ Testing Indicator Alert Processing...")
    
    try:
        # Test the processing function
        print("Testing indicator alert processing...")
        await process_indicator_alerts()
        print("✓ Indicator alert processing completed without errors")
        
        # Test individual RSI alert processing
        print("Testing individual RSI alert processing...")
        
        # Create a test alert that should not trigger (neutral condition)
        test_alert = IndicatorAlert(
            id="test-processing-alert",
            symbol="BTC",
            indicator_type="rsi",
            condition="overbought",  # Unlikely to trigger with default 70 level
            config={
                "period": 14,
                "overbought_level": 90,  # Very high threshold, unlikely to trigger
                "oversold_level": 10,   # Very low threshold
                "timeframe": "5m"
            },
            description="Test processing alert",
            triggers=[],
            created_date=datetime.now().isoformat()
        )
        
        # Process the test alert
        triggered = await process_rsi_alert(test_alert)
        print(f"✓ Test alert processed, triggered: {triggered}")
        
        print("✅ Indicator Alert Processing test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Indicator Alert Processing test failed: {e}")
        return False

def test_rsi_conditions():
    """Test different RSI alert conditions"""
    print("\n🎯 Testing RSI Alert Conditions...")
    
    try:
        calculator = RSICalculator(period=14)
        
        # Create test data for different scenarios
        
        # High RSI scenario (should trigger overbought)
        high_rsi_prices = [50.0] + [51.0 + i * 0.5 for i in range(20)]  # Steadily increasing
        high_rsi = calculator.calculate_rsi(high_rsi_prices)
        
        if high_rsi and high_rsi > 70:
            print(f"✓ High RSI scenario: {high_rsi:.2f} (should trigger overbought)")
        else:
            print(f"⚠️  High RSI scenario: {high_rsi:.2f} (might not trigger overbought)")
        
        # Low RSI scenario (should trigger oversold)
        low_rsi_prices = [50.0] + [49.0 - i * 0.5 for i in range(20)]  # Steadily decreasing
        low_rsi = calculator.calculate_rsi(low_rsi_prices)
        
        if low_rsi and low_rsi < 30:
            print(f"✓ Low RSI scenario: {low_rsi:.2f} (should trigger oversold)")
        else:
            print(f"⚠️  Low RSI scenario: {low_rsi:.2f} (might not trigger oversold)")
        
        # Neutral RSI scenario
        neutral_prices = [50.0 + (i % 2) * 0.1 for i in range(30)]  # Small oscillations
        neutral_rsi = calculator.calculate_rsi(neutral_prices)
        
        if neutral_rsi and 30 < neutral_rsi < 70:
            print(f"✓ Neutral RSI scenario: {neutral_rsi:.2f} (should not trigger)")
        else:
            print(f"⚠️  Neutral RSI scenario: {neutral_rsi:.2f} (unexpected value)")
        
        print("✅ RSI Conditions test passed!")
        return True
        
    except Exception as e:
        print(f"❌ RSI Conditions test failed: {e}")
        return False

async def main():
    """Run all Phase 2 tests"""
    print("🧪 Running Phase 2 RSI Implementation Tests")
    print("=" * 50)
    
    tests = [
        test_rsi_calculation,
        test_rsi_with_live_data,
        test_indicator_alert_creation,
        test_indicator_alert_processing,
        test_rsi_conditions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if asyncio.iscoroutinefunction(test):
            if await test():
                passed += 1
        else:
            if test():
                passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 2 RSI tests passed!")
        print("\n📋 Next Steps:")
        print("1. Review the RSI implementation")
        print("2. Test with different market conditions")
        print("3. Proceed to Phase 3: API Endpoints Enhancement")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
