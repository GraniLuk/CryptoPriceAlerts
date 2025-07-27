# Bitcoin Price Alerts

🚨 Real-time cryptocurrency price monitoring and alert system built with Azure Functions and Telegram integration.

A serverless application that tracks cryptocurrency prices and sends customizable alerts through Telegram. Support for both single-coin price monitoring, trading pair ratio alerts, and technical indicator monitoring with automated actions via customizable triggers.

## 🔑 Key Features

- 📈 Real-time price monitoring
- 🔄 Ratio-based trading pair alerts
- 📊 **NEW: Technical Indicator Alerts** - Automatic RSI threshold monitoring
- 🎯 **Smart RSI Monitoring** - Triggers on any threshold crossover automatically
- 🔧 **Manual Control** - You decide when to stop monitoring each symbol
- 💬 Telegram notifications
- ⚡ Serverless Azure Functions
- 🔐 Secure storage with Azure Table Storage
- 🤖 Customizable action triggers (Bybit trading support included)
- ⏱️ Multi-timeframe analysis (1m, 5m, 15m, 1h, 4h, 1d)

## Features

### Price Monitoring

- Monitors cryptocurrency prices using CoinGecko or CoinMarketCap API
- Supports two types of price alerts:
  1. Single Symbol Alerts: Monitor individual cryptocurrency prices
  2. Ratio Alerts: Monitor price ratios between two cryptocurrencies
- Each alert can have multiple triggers for automated actions

### Alert Types

#### Single Symbol Alerts

- Track price movements for individual cryptocurrencies
- Configurable price thresholds with operators (>, <, =)
- Example: Alert when BTC price goes above $50,000
- Can include triggers for automated actions

#### Ratio Alerts

- Monitor price relationships between two cryptocurrencies
- Useful for trading pairs and market analysis
- Example: Alert when BTC/ETH ratio exceeds 15
- Can include triggers for automated actions

#### 📊 Technical Indicator Alerts (NEW)

- Monitor technical indicators like RSI, MACD, Bollinger Bands
- Configurable parameters for each indicator
- **Automatic comprehensive monitoring** - no need to specify specific conditions
- Integration with existing trigger system

##### Supported Indicators

**RSI (Relative Strength Index)**

- Configurable period (default: 14)
- Custom overbought/oversold levels (default: 70/30)
- **Automatic threshold crossover monitoring** - monitors all RSI movements
- Multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)
- **Triggers on any significant RSI movement:**
  - RSI crosses above overbought level
  - RSI crosses below oversold level
  - RSI exits overbought zone (crosses back below overbought)
  - RSI exits oversold zone (crosses back above oversold)

**How RSI Alerts Work Now:**

1. **Simplified Setup**: Just specify symbol, timeframe, and threshold levels
2. **Comprehensive Monitoring**: Automatically detects all important RSI movements
3. **Continuous Alerts**: Get notified of every significant RSI change
4. **Manual Control**: Set `triggered_date` manually when you want to stop monitoring
5. **No Missed Signals**: Never miss important entry/exit opportunities

**Coming Soon:** MACD, Bollinger Bands, Moving Averages

### Trigger System

- Flexible trigger system to execute actions when price conditions are met
- Each alert can have multiple triggers of different types
- Currently supported trigger types:
  - **Bybit Trading Actions**: Execute trades on Bybit exchange
    - Open positions (market or limit orders)
    - Close positions
    - Set take profit and stop loss levels
- Designed to be extensible for future trigger types

### Alert Management

- Create new alerts via HTTP endpoint
- Remove existing alerts
- View all current active alerts
- Automatic cleanup of triggered alerts

### Notifications

- Real-time alerts via Telegram
- Formatted messages with alert details
- Configurable notification settings
- Action trigger result notifications

## Setup

### Prerequisites

- Azure Functions account
- Telegram Bot Token
- CoinGecko API Key
- Azure Storage Account
- Bybit API Key and Secret (for trading features)

### Environment Variables

Required environment variables:

- TELEGRAM_ENABLED: true/false
- TELEGRAM_TOKEN: Telegram bot token
- TELEGRAM_CHAT_ID: Telegram chat IDs
- COINGECKO_API_KEY: CoinGecko API key
- AZURE_STORAGE_SHARE_NAME: Azure file share name
- AZURE_STORAGE_STORAGE_ACCOUNT: Storage account name
- AZURE_STORAGE_STORAGE_ACCOUNT_KEY: Storage account key
- BYBIT_API_KEY: Bybit API key
- BYBIT_API_SECRET: Bybit API secret
- BYBIT_TESTNET: true/false (whether to use Bybit testnet)
- COINMARKETCAP_API_KEY: CoinMarketCap API key (optional)
- APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Application Insights connection string (optional)

### Local Development

1. Clone the repository
2. Copy `.env.example` to `.env`
3. Fill in your environment variables
4. Install dependencies: `pip install -r requirements.txt`
5. Run the function locally using Azure Functions Core Tools

## API Endpoints

### Create Price Alert

```http
POST /api/insert_new_alert_grani

# Single Symbol Alert with Bybit Trigger
{
    "type": "single",
    "symbol": "BTC",
    "price": 50000,
    "operator": "<",
    "description": "BTC below 50k",
    "triggers": [
        {
            "type": "bybit_action",
            "action": "open_position",
            "params": {
                "side": "Buy",
                "order_type": "Market",
                "qty": 0.1,
                "leverage": 5,
                "take_profit": 55000,
                "stop_loss": 48000
            }
        }
    ]
}

# Ratio Alert with Bybit Trigger
{
    "type": "ratio",
    "symbol1": "BTC",
    "symbol2": "ETH",
    "price": 15,
    "operator": ">",
    "description": "BTC/ETH ratio above 15",
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

# Alert with Multiple Triggers
{
    "type": "single",
    "symbol": "ETH",
    "price": 3000,
    "operator": ">",
    "description": "ETH above 3000",
    "triggers": [
        {
            "type": "bybit_action",
            "action": "open_position",
            "params": {
                "symbol": "ETHUSDT",
                "side": "Buy",
                "qty": 1.0
            }
        },
        {
            "type": "bybit_action",
            "action": "set_tp_sl",
            "params": {
                "symbol": "ETHUSDT",
                "take_profit": 3500,
                "stop_loss": 2800
            }
        }
    ]
}
```

### 📊 Create Technical Indicator Alert (NEW)

```http
POST /api/create_indicator_alert

# RSI Threshold Monitoring Alert (Automatic - No condition parameter needed)
{
    "symbol": "BTC",
    "indicator_type": "rsi",
    "description": "BTC RSI threshold monitoring - all crossovers",
    "config": {
        "period": 14,
        "overbought_level": 75,
        "oversold_level": 25,
        "timeframe": "5m"
    }
}

# ETH RSI Alert with Standard Levels
{
    "symbol": "ETH",
    "indicator_type": "rsi",
    "description": "ETH RSI monitoring for entry/exit signals",
    "config": {
        "period": 21,
        "overbought_level": 70,
        "oversold_level": 30,
        "timeframe": "15m"
    }
}

# SOL RSI Alert with Bybit Trading Action
{
    "symbol": "SOL",
    "indicator_type": "rsi",
    "description": "SOL RSI monitoring with automated actions",
    "config": {
        "period": 14,
        "overbought_level": 80,
        "oversold_level": 20,
        "timeframe": "1h"
    },
    "triggers": [
        {
            "type": "bybit_action",
            "action": "close_position",
            "params": {
                "symbol": "SOLUSDT"
            }
        }
    ]
}
```

**Important Notes:**

- **No `condition` parameter required** - all RSI alerts automatically monitor threshold crossovers
- **Comprehensive monitoring** - triggers on any significant RSI movement (entering/exiting overbought/oversold zones)
- **Manual control** - `triggered_date` is not automatically set, giving you control over when to stop monitoring
- **Flexible thresholds** - customize overbought/oversold levels per your trading strategy

### Remove Alert

```http
POST /api/remove_alert_grani
{
    "id": "alert-uuid"
}
```

### Get All Alerts

```http
GET /api/get_all_alerts

# Get all alerts
GET /api/get_all_alerts

# Filter by alert type
GET /api/get_all_alerts?type=price
GET /api/get_all_alerts?type=indicator

# Filter by symbol
GET /api/get_all_alerts?symbol=BTC

# Filter by enabled status
GET /api/get_all_alerts?enabled=true

# Combine filters
GET /api/get_all_alerts?type=indicator&symbol=ETH&enabled=true
```

**Response includes:**

- Comprehensive alert data for both price and indicator alerts
- Summary statistics (total alerts, price alerts count, indicator alerts count)
- Applied filters information
- Formatted message for backward compatibility

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT](https://choosealicense.com/licenses/mit/)