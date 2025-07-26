"""
Test script for the updated remove alert API (using table storage only)
"""
import asyncio
import json
import sys
import os
import uuid
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from remove_alert_grani import main as remove_alert_main
from create_indicator_alert import main as create_alert_main
from shared_code.table_storage import AlertTableStorage
from shared_code.alert_models import IndicatorAlert
import azure.functions as func

def create_mock_request(method="POST", body=None):
    """Create a mock HTTP request for testing"""
    if body:
        body_bytes = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
    else:
        body_bytes = b""
    
    # Create a proper HttpRequest instance
    return func.HttpRequest(
        method=method,
        url="http://localhost:7071/api/test",
        body=body_bytes,
        headers={"Content-Type": "application/json"}
    )

async def create_test_indicator_alert():
    """Create a test indicator alert for removal testing"""
    print("📝 Creating test indicator alert...")
    
    create_request = create_mock_request("POST", {
        "symbol": "BTCUSDT",
        "indicator_type": "rsi",
        "condition": "overbought",
        "config": {
            "period": 14,
            "overbought_level": 75,
            "oversold_level": 25,
            "timeframe": "5m"
        },
        "description": "Test alert for removal"
    })
    
    try:
        response = await create_alert_main(create_request)
        if response.status_code == 201:
            response_data = json.loads(response.get_body().decode())
            alert_id = response_data["alert"]["id"]
            print(f"✅ Created test indicator alert with ID: {alert_id}")
            return alert_id
        else:
            print(f"❌ Failed to create test alert: {response.status_code}")
            if hasattr(response, 'get_body'):
                body = response.get_body().decode()
                print(f"   Response: {body}")
            return None
    except Exception as e:
        print(f"❌ Exception creating test alert: {e}")
        return None

async def create_test_price_alert():
    """Create a test price alert directly in table storage"""
    print("📝 Creating test price alert in table storage...")
    
    try:
        table_storage = AlertTableStorage()
        if not table_storage.service_client:
            print("⚠️ Table storage not available")
            return None
        
        price_table = table_storage.get_table_client("pricealerts")
        if not price_table:
            print("⚠️ Price alerts table not available")
            return None
        
        # Create a test price alert entity
        alert_id = str(uuid.uuid4())
        entity = {
            "PartitionKey": "price_BTC",
            "RowKey": alert_id,
            "Symbol": "BTC",
            "TargetPrice": 50000.0,
            "IsAbove": True,
            "Nickname": "Test price alert for removal",
            "UserId": "test_user",
            "CreatedDate": datetime.now().isoformat(),
            "Enabled": True
        }
        
        price_table.upsert_entity(entity)
        print(f"✅ Created test price alert with ID: {alert_id}")
        return alert_id
        
    except Exception as e:
        print(f"❌ Exception creating test price alert: {e}")
        return None

async def test_remove_alerts():
    """Test removing both types of alerts"""
    print("\n🧪 Testing remove alert functionality...")
    
    # Create test alerts
    indicator_alert_id = await create_test_indicator_alert()
    price_alert_id = await create_test_price_alert()
    
    if not indicator_alert_id or not price_alert_id:
        print("❌ Failed to create test alerts")
        return
    
    # Test removing indicator alert
    print(f"\n🗑️ Testing removal of indicator alert: {indicator_alert_id}")
    remove_request = create_mock_request("POST", {
        "id": indicator_alert_id,
        "type": "indicator"
    })
    
    try:
        response = remove_alert_main(remove_request)
        response_data = json.loads(response.get_body().decode())
        
        if response.status_code == 200:
            print(f"✅ Successfully removed indicator alert")
            print(f"   Message: {response_data.get('message')}")
            print(f"   Removed from: {response_data.get('removed_from')}")
        else:
            print(f"❌ Failed to remove indicator alert: {response_data.get('error')}")
    except Exception as e:
        print(f"❌ Exception removing indicator alert: {e}")
    
    # Test removing price alert
    print(f"\n🗑️ Testing removal of price alert: {price_alert_id}")
    remove_request = create_mock_request("POST", {
        "id": price_alert_id,
        "type": "price"
    })
    
    try:
        response = remove_alert_main(remove_request)
        response_data = json.loads(response.get_body().decode())
        
        if response.status_code == 200:
            print(f"✅ Successfully removed price alert")
            print(f"   Message: {response_data.get('message')}")
            print(f"   Removed from: {response_data.get('removed_from')}")
        else:
            print(f"❌ Failed to remove price alert: {response_data.get('error')}")
    except Exception as e:
        print(f"❌ Exception removing price alert: {e}")
    
    # Test removing non-existent alert
    print(f"\n🗑️ Testing removal of non-existent alert")
    remove_request = create_mock_request("POST", {
        "id": "non-existent-id"
    })
    
    try:
        response = remove_alert_main(remove_request)
        response_data = json.loads(response.get_body().decode())
        
        if response.status_code == 404:
            print(f"✅ Correctly handled non-existent alert")
            print(f"   Error: {response_data.get('error')}")
        else:
            print(f"⚠️ Unexpected response for non-existent alert: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception testing non-existent alert: {e}")

async def test_validation():
    """Test request validation"""
    print("\n🔍 Testing request validation...")
    
    # Test missing alert ID
    remove_request = create_mock_request("POST", {})
    
    try:
        response = remove_alert_main(remove_request)
        response_data = json.loads(response.get_body().decode())
        
        if response.status_code == 400:
            print(f"✅ Correctly rejected missing alert ID")
            print(f"   Error: {response_data.get('error')}")
        else:
            print(f"⚠️ Unexpected response for missing ID: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception testing validation: {e}")

def main():
    """Run all tests"""
    print("🚀 Testing Remove Alert API (Table Storage Only)")
    print("=" * 60)
    
    try:
        # Run async tests
        asyncio.run(test_remove_alerts())
        asyncio.run(test_validation())
        
        print("\n" + "=" * 60)
        print("✅ Remove alert tests completed!")
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n📝 Summary of changes:")
    print("• Removed dependency on alerts.json file")
    print("• Now uses pricealerts table for price alerts")
    print("• Unified table storage approach for both alert types")
    print("• Improved error handling and JSON responses")
    print("• Better logging with app_logger")

if __name__ == "__main__":
    main()
