"""
Test script for Phase 3: API Endpoints Enhancement
Tests the HTTP API endpoints for creating, listing, and removing indicator alerts
"""

import requests
import json
import asyncio
import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_code.table_storage import AlertTableStorage

# Configuration for local development
BASE_URL = "http://localhost:7071/api"  # Default Azure Functions local URL
HEADERS = {"Content-Type": "application/json"}

def test_api_create_indicator_alert():
    """Test creating a new indicator alert via API"""
    print("\n🚀 Testing Create Indicator Alert API...")
    
    try:
        # Test data for creating RSI alerts
        test_alerts = [
            {
                "symbol": "BTC",
                "indicator_type": "rsi",
                "condition": "overbought",
                "config": {
                    "period": 14,
                    "overbought_level": 75,
                    "oversold_level": 25,
                    "timeframe": "5m"
                },
                "description": "BTC RSI overbought alert (API test)",
                "triggers": [
                    {"type": "telegram", "message": "🔔 BTC RSI is overbought!"}
                ]
            },
            {
                "symbol": "ETH",
                "indicator_type": "rsi",
                "condition": "oversold",
                "config": {
                    "period": 21,
                    "overbought_level": 80,
                    "oversold_level": 20,
                    "timeframe": "15m"
                },
                "description": "ETH RSI oversold alert (API test)"
            }
        ]
        
        created_alerts = []
        
        for i, alert_data in enumerate(test_alerts):
            print(f"Creating alert {i+1}: {alert_data['symbol']} {alert_data['condition']}")
            
            response = requests.post(
                f"{BASE_URL}/indicator-alerts",
                headers=HEADERS,
                json=alert_data,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                print(f"✓ Alert created successfully: {result['alert']['id']}")
                print(f"  Symbol: {result['alert']['symbol']}")
                print(f"  Condition: {result['alert']['condition']}")
                print(f"  Timeframe: {result['alert']['config']['timeframe']}")
                created_alerts.append(result['alert'])
            else:
                print(f"✗ Failed to create alert: {response.status_code}")
                print(f"  Response: {response.text}")
                return False, []
        
        print(f"✅ Created {len(created_alerts)} alerts successfully!")
        return True, created_alerts
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Azure Functions. Make sure the function app is running locally.")
        print("   Run: func host start")
        return False, []
    except Exception as e:
        print(f"❌ Error testing create alert API: {e}")
        return False, []

def test_api_list_indicator_alerts():
    """Test listing indicator alerts via API"""
    print("\n📋 Testing List Indicator Alerts API...")
    
    try:
        # Test listing all alerts
        print("Listing all indicator alerts...")
        response = requests.get(f"{BASE_URL}/indicator-alerts/list", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Retrieved {result['count']} alerts")
            
            for alert in result['alerts'][:3]:  # Show first 3 alerts
                print(f"  - {alert['symbol']} {alert['indicator_type']} {alert['condition']}")
                print(f"    ID: {alert['id']}")
                print(f"    Created: {alert['created_date']}")
            
            if result['count'] > 3:
                print(f"  ... and {result['count'] - 3} more alerts")
        else:
            print(f"✗ Failed to list alerts: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # Test filtering by symbol
        print("\nTesting symbol filter (BTC)...")
        response = requests.get(f"{BASE_URL}/indicator-alerts/list?symbol=BTC", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['count']} BTC alerts")
            
            # Verify all results are for BTC
            btc_alerts = [alert for alert in result['alerts'] if alert['symbol'] == 'BTC']
            if len(btc_alerts) == result['count']:
                print("✓ Symbol filter working correctly")
            else:
                print("✗ Symbol filter not working properly")
                return False
        else:
            print(f"✗ Failed to filter by symbol: {response.status_code}")
            return False
        
        # Test filtering by enabled status
        print("\nTesting enabled filter (true)...")
        response = requests.get(f"{BASE_URL}/indicator-alerts/list?enabled=true", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['count']} enabled alerts")
        else:
            print(f"✗ Failed to filter by enabled status: {response.status_code}")
            return False
        
        print("✅ List indicator alerts API test passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Azure Functions. Make sure the function app is running locally.")
        return False
    except Exception as e:
        print(f"❌ Error testing list alerts API: {e}")
        return False

def test_api_remove_indicator_alert(created_alerts):
    """Test removing indicator alerts via API"""
    print("\n🗑️ Testing Remove Indicator Alert API...")
    
    try:
        if not created_alerts:
            print("⚠️  No alerts available for removal test")
            return True
        
        # Remove the first created alert
        alert_to_remove = created_alerts[0]
        alert_id = alert_to_remove['id']
        
        print(f"Removing alert: {alert_id}")
        print(f"  Symbol: {alert_to_remove['symbol']}")
        print(f"  Condition: {alert_to_remove['condition']}")
        
        response = requests.delete(f"{BASE_URL}/indicator-alerts/{alert_id}", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Alert removed successfully")
            print(f"  Removed: {result['removed_alert']['symbol']} {result['removed_alert']['condition']}")
        else:
            print(f"✗ Failed to remove alert: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # Verify the alert is gone by trying to list it
        print("Verifying alert removal...")
        list_response = requests.get(f"{BASE_URL}/indicator-alerts/list", timeout=30)
        
        if list_response.status_code == 200:
            list_result = list_response.json()
            remaining_alert_ids = [alert['id'] for alert in list_result['alerts']]
            
            if alert_id not in remaining_alert_ids:
                print("✓ Alert successfully removed from storage")
            else:
                print("✗ Alert still exists in storage")
                return False
        else:
            print("⚠️  Could not verify removal")
        
        # Test removing non-existent alert
        print("\nTesting removal of non-existent alert...")
        fake_id = "non-existent-alert-id"
        response = requests.delete(f"{BASE_URL}/indicator-alerts/{fake_id}", timeout=30)
        
        if response.status_code == 404:
            print("✓ Correctly returned 404 for non-existent alert")
        else:
            print(f"✗ Expected 404, got {response.status_code}")
            return False
        
        print("✅ Remove indicator alert API test passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Azure Functions. Make sure the function app is running locally.")
        return False
    except Exception as e:
        print(f"❌ Error testing remove alert API: {e}")
        return False

def test_api_validation():
    """Test API input validation"""
    print("\n🔍 Testing API Input Validation...")
    
    try:
        # Test missing required fields
        print("Testing missing required fields...")
        invalid_data = {"symbol": "BTC"}  # Missing indicator_type, condition, config
        
        response = requests.post(
            f"{BASE_URL}/indicator-alerts",
            headers=HEADERS,
            json=invalid_data,
            timeout=30
        )
        
        if response.status_code == 400:
            print("✓ Correctly rejected request with missing fields")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
            return False
        
        # Test invalid indicator type
        print("Testing invalid indicator type...")
        invalid_data = {
            "symbol": "BTC",
            "indicator_type": "invalid_indicator",
            "condition": "overbought",
            "config": {"period": 14}
        }
        
        response = requests.post(
            f"{BASE_URL}/indicator-alerts",
            headers=HEADERS,
            json=invalid_data,
            timeout=30
        )
        
        if response.status_code == 400:
            print("✓ Correctly rejected invalid indicator type")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
            return False
        
        # Test invalid RSI condition
        print("Testing invalid RSI condition...")
        invalid_data = {
            "symbol": "BTC",
            "indicator_type": "rsi",
            "condition": "invalid_condition",
            "config": {"period": 14}
        }
        
        response = requests.post(
            f"{BASE_URL}/indicator-alerts",
            headers=HEADERS,
            json=invalid_data,
            timeout=30
        )
        
        if response.status_code == 400:
            print("✓ Correctly rejected invalid RSI condition")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
            return False
        
        # Test invalid config values
        print("Testing invalid config values...")
        invalid_data = {
            "symbol": "BTC",
            "indicator_type": "rsi",
            "condition": "overbought",
            "config": {
                "period": 1,  # Too small
                "overbought_level": 150,  # Too high
                "oversold_level": -10  # Too low
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/indicator-alerts",
            headers=HEADERS,
            json=invalid_data,
            timeout=30
        )
        
        if response.status_code == 400:
            print("✓ Correctly rejected invalid config values")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
            return False
        
        print("✅ API validation test passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Azure Functions. Make sure the function app is running locally.")
        return False
    except Exception as e:
        print(f"❌ Error testing API validation: {e}")
        return False

async def test_table_storage_integration():
    """Test that APIs integrate properly with table storage"""
    print("\n🗄️ Testing Table Storage Integration...")
    
    try:
        # Check if table storage is available
        table_storage = AlertTableStorage()
        if not table_storage.service_client:
            print("⚠️  Table storage not available, skipping integration test")
            return True
        
        indicator_table = table_storage.get_table_client("indicatoralerts")
        if not indicator_table:
            print("⚠️  Indicator alerts table not available")
            return True
        
        # Count alerts before API test
        alerts_before = list(indicator_table.list_entities())
        count_before = len(alerts_before)
        print(f"Alerts in storage before test: {count_before}")
        
        # Create an alert via API
        test_alert = {
            "symbol": "TEST",
            "indicator_type": "rsi",
            "condition": "overbought",
            "config": {"period": 14, "overbought_level": 70, "oversold_level": 30, "timeframe": "5m"},
            "description": "Integration test alert"
        }
        
        response = requests.post(
            f"{BASE_URL}/indicator-alerts",
            headers=HEADERS,
            json=test_alert,
            timeout=30
        )
        
        if response.status_code == 201:
            result = response.json()
            alert_id = result['alert']['id']
            print(f"✓ Created test alert via API: {alert_id}")
            
            # Check if it appears in table storage
            alerts_after = list(indicator_table.list_entities())
            count_after = len(alerts_after)
            
            if count_after == count_before + 1:
                print("✓ Alert correctly added to table storage")
                
                # Find the created alert in storage
                created_alert = None
                for entity in alerts_after:
                    if entity.get("RowKey") == alert_id:
                        created_alert = entity
                        break
                
                if created_alert:
                    print("✓ Alert found in table storage with correct ID")
                    
                    # Clean up - remove the test alert
                    try:
                        response = requests.delete(f"{BASE_URL}/indicator-alerts/{alert_id}", timeout=30)
                        if response.status_code == 200:
                            print("✓ Test alert cleaned up successfully")
                        else:
                            print("⚠️  Could not clean up test alert")
                    except:
                        print("⚠️  Could not clean up test alert")
                        
                else:
                    print("✗ Alert not found in table storage")
                    return False
            else:
                print(f"✗ Expected {count_before + 1} alerts, found {count_after}")
                return False
        else:
            print(f"✗ Failed to create test alert: {response.status_code}")
            return False
        
        print("✅ Table storage integration test passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Azure Functions. Make sure the function app is running locally.")
        return False
    except Exception as e:
        print(f"❌ Error testing table storage integration: {e}")
        return False

def check_function_app_status():
    """Check if the Azure Functions app is running"""
    print("🔍 Checking Azure Functions app status...")
    
    try:
        # Try to reach the admin endpoint
        response = requests.get("http://localhost:7071/admin/host/status", timeout=10)
        if response.status_code == 200:
            print("✅ Azure Functions app is running")
            return True
        else:
            print(f"⚠️  Azure Functions app responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Azure Functions app is not running")
        print("   Please start it with: func host start")
        return False
    except Exception as e:
        print(f"⚠️  Could not check Azure Functions status: {e}")
        return False

async def main():
    """Run all Phase 3 API tests"""
    print("🧪 Running Phase 3 API Endpoints Tests")
    print("=" * 50)
    
    # Check if function app is running
    if not check_function_app_status():
        print("\n❌ Azure Functions app is not running. Please start it first:")
        print("   cd c:\\Users\\5028lukgr\\source\\repos\\CryptoPriceAlerts")
        print("   func host start")
        return False
    
    tests = []
    
    # Test API endpoints
    create_success, created_alerts = test_api_create_indicator_alert()
    tests.append(("Create Indicator Alert API", create_success))
    
    list_success = test_api_list_indicator_alerts()
    tests.append(("List Indicator Alerts API", list_success))
    
    remove_success = test_api_remove_indicator_alert(created_alerts)
    tests.append(("Remove Indicator Alert API", remove_success))
    
    validation_success = test_api_validation()
    tests.append(("API Input Validation", validation_success))
    
    integration_success = await test_table_storage_integration()
    tests.append(("Table Storage Integration", integration_success))
    
    # Calculate results
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    # Show detailed results
    print("\n📋 Detailed Results:")
    for test_name, success in tests:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    if passed == total:
        print("\n🎉 All Phase 3 API tests passed!")
        print("\n📋 Next Steps:")
        print("1. Review the API endpoints implementation")
        print("2. Test with your frontend/client applications")
        print("3. Deploy to Azure for production testing")
        print("4. Consider adding authentication/authorization")
        print("5. Monitor API usage and performance")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
