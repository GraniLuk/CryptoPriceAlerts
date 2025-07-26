"""
Basic tests for the CryptoPriceAlerts Azure Functions app.
"""

import os
import sys

import pytest

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_import_function_app():
    """Test that the main function app can be imported without errors."""
    try:
        import function_app

        assert function_app is not None
    except ImportError as e:
        pytest.fail(f"Failed to import function_app: {e}")


def test_import_shared_code():
    """Test that shared code modules can be imported."""
    try:
        from shared_code import bybit_integration, utils

        assert bybit_integration is not None
        assert utils is not None
    except ImportError as e:
        pytest.fail(f"Failed to import shared_code modules: {e}")


def test_bybit_client_initialization():
    """Test that BybitClient can be initialized with None values."""
    from shared_code.bybit_integration import BybitClient

    # This should not raise an error with None values
    try:
        # This will raise ValueError due to missing credentials, which is expected
        with pytest.raises(ValueError, match="Bybit API key and secret must be provided"):
            BybitClient(api_key=None, api_secret=None)
    except Exception as e:
        pytest.fail(f"Unexpected error during BybitClient initialization: {e}")


def test_execute_bybit_action_validation():
    """Test that execute_bybit_action properly validates parameters."""
    from shared_code.bybit_integration import execute_bybit_action

    # Test with missing required parameters
    result = execute_bybit_action("open_position", {})
    assert result["success"] is False
    assert "Missing required parameters" in result["message"]

    # Test with invalid action type
    result = execute_bybit_action("invalid_action", {"symbol": "BTCUSDT"})
    assert result["success"] is False
    assert "Unsupported action type" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__])
