import hashlib
import hmac
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from telegram_logging_handler import app_logger


class BybitClient:
    def __init__(
        self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False
    ):
        """
        Initialize Bybit client with API credentials

        Parameters:
        -----------
        api_key : str
            Bybit API key (defaults to BYBIT_API_KEY env var)
        api_secret : str
            Bybit API secret (defaults to BYBIT_API_SECRET env var)
        testnet : bool
            Whether to use testnet (default: False)
        """
        self.api_key = api_key or os.environ.get("BYBIT_API_KEY")
        self.api_secret = api_secret or os.environ.get("BYBIT_API_SECRET")

        if not self.api_key or not self.api_secret:
            app_logger.error("Bybit API credentials not provided")
            raise ValueError("Bybit API key and secret must be provided")

        # Set the base URL based on testnet flag
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        )
        self.recvWindow = 5000

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for API request"""
        if not self.api_secret:
            raise ValueError("API secret is required for signature generation")
        
        ordered_params = sorted(params.items())
        query_string = urlencode(ordered_params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send request to Bybit API"""
        url = f"{self.base_url}{endpoint}"

        timestamp = int(time.time() * 1000)
        params = params or {}
        params.update(
            {
                "api_key": self.api_key,
                "timestamp": str(timestamp),
                "recv_window": str(self.recvWindow),
            }
        )

        # Generate signature
        signature = self._generate_signature(params)
        params["sign"] = signature

        try:
            if method == "GET":
                response = requests.get(url, params=params)
            elif method == "POST":
                response = requests.post(url, data=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            data = response.json()

            if response.status_code != 200 or data.get("ret_code") != 0:
                error_msg = f"Bybit API error: {data.get('ret_msg', 'Unknown error')}"
                app_logger.error(error_msg)
                return {"success": False, "message": error_msg, "data": data}

            return {
                "success": True,
                "data": data["result"] if "result" in data else data,
            }

        except Exception as e:
            error_msg = f"Error in Bybit API request: {str(e)}"
            app_logger.error(error_msg)
            return {"success": False, "message": error_msg}

    def open_position(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None,
        time_in_force: str = "GoodTillCancel",
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        reduce_only: bool = False,
        leverage: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Open a new position on Bybit

        Parameters:
        -----------
        symbol : str
            Trading pair symbol (e.g., 'BTCUSDT')
        side : str
            Order side ('Buy' or 'Sell')
        order_type : str
            Order type ('Market', 'Limit')
        qty : float
            Order quantity
        price : float, optional
            Order price (required for Limit orders)
        time_in_force : str
            Time in force ('GoodTillCancel', 'ImmediateOrCancel', 'FillOrKill')
        take_profit : float, optional
            Take profit price
        stop_loss : float, optional
            Stop loss price
        reduce_only : bool
            Whether the order should only reduce position
        leverage : int, optional
            Set leverage for the position

        Returns:
        --------
        dict
            Response from Bybit API
        """
        # Set leverage if provided
        if leverage is not None:
            self.set_leverage(symbol, leverage)

        # Prepare parameters
        params = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": str(qty),
            "time_in_force": time_in_force,
            "reduce_only": str(reduce_only).lower(),
        }

        # Add optional parameters
        if price is not None and order_type == "Limit":
            params["price"] = str(price)

        if take_profit is not None:
            params["take_profit"] = str(take_profit)

        if stop_loss is not None:
            params["stop_loss"] = str(stop_loss)

        # Send the request
        endpoint = "/v2/private/order/create"
        return self._make_request("POST", endpoint, params)

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an open position for a symbol

        Parameters:
        -----------
        symbol : str
            Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
        --------
        dict
            Response from Bybit API
        """
        params = {"symbol": symbol}

        endpoint = "/v2/private/position/close"
        return self._make_request("POST", endpoint, params)

    def set_take_profit_stop_loss(
        self,
        symbol: str,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Set take profit and stop loss for an open position

        Parameters:
        -----------
        symbol : str
            Trading pair symbol (e.g., 'BTCUSDT')
        take_profit : float, optional
            Take profit price
        stop_loss : float, optional
            Stop loss price

        Returns:
        --------
        dict
            Response from Bybit API
        """
        params = {"symbol": symbol}

        if take_profit is not None:
            params["take_profit"] = str(take_profit)

        if stop_loss is not None:
            params["stop_loss"] = str(stop_loss)

        endpoint = "/v2/private/position/trading-stop"
        return self._make_request("POST", endpoint, params)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a symbol

        Parameters:
        -----------
        symbol : str
            Trading pair symbol (e.g., 'BTCUSDT')
        leverage : int
            Leverage value (1-100)

        Returns:
        --------
        dict
            Response from Bybit API
        """
        params = {"symbol": symbol, "leverage": str(leverage)}

        endpoint = "/v2/private/position/leverage/save"
        return self._make_request("POST", endpoint, params)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """
        Get position information for a symbol

        Parameters:
        -----------
        symbol : str
            Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
        --------
        dict
            Response from Bybit API
        """
        params = {"symbol": symbol}

        endpoint = "/v2/private/position/list"
        return self._make_request("GET", endpoint, params)


def execute_bybit_action(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a Bybit action based on the type and parameters

    Parameters:
    -----------
    action_type : str
        Type of action to execute ('open_position', 'close_position', 'set_tp_sl')
    params : dict
        Parameters for the action

    Returns:
    --------
    dict
        Result of the action
    """
    try:
        client = BybitClient(
            testnet=os.environ.get("BYBIT_TESTNET", "false").lower() == "true"
        )

        if action_type == "open_position":
            # Validate required parameters
            symbol = params.get("symbol")
            side = params.get("side")
            qty = params.get("qty")
            
            if not symbol or not side or qty is None:
                error_msg = "Missing required parameters for open_position: symbol, side, qty"
                app_logger.error(error_msg)
                return {"success": False, "message": error_msg}
            
            return client.open_position(
                symbol=symbol,
                side=side,
                order_type=params.get("order_type", "Market"),
                qty=float(qty),
                price=params.get("price"),
                take_profit=params.get("take_profit"),
                stop_loss=params.get("stop_loss"),
                leverage=params.get("leverage"),
            )
        elif action_type == "close_position":
            symbol = params.get("symbol")
            if not symbol:
                error_msg = "Missing required parameter for close_position: symbol"
                app_logger.error(error_msg)
                return {"success": False, "message": error_msg}
            return client.close_position(symbol=symbol)
        elif action_type == "set_tp_sl":
            symbol = params.get("symbol")
            if not symbol:
                error_msg = "Missing required parameter for set_tp_sl: symbol"
                app_logger.error(error_msg)
                return {"success": False, "message": error_msg}
            return client.set_take_profit_stop_loss(
                symbol=symbol,
                take_profit=params.get("take_profit"),
                stop_loss=params.get("stop_loss"),
            )
        else:
            error_msg = f"Unsupported action type: {action_type}"
            app_logger.error(error_msg)
            return {"success": False, "message": error_msg}

    except Exception as e:
        error_msg = f"Error executing Bybit action: {str(e)}"
        app_logger.error(error_msg)
        return {"success": False, "message": error_msg}
