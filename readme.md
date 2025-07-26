# Bitcoin Price Alerts

🚨 Real-time cryptocurrency price monitoring and alert system built with Azure Functions and Telegram integration.

A serverless application that tracks cryptocurrency prices and sends customizable alerts through Telegram. Support for both single-coin price monitoring, trading pair ratio alerts, and technical indicator monitoring with automated actions via customizable triggers.

## 🔑 Key Features

- 📈 Real-time price monitoring
- 🔄 Ratio-based trading pair alerts
- 📊 **NEW: Technical Indicator Alerts (RSI, MACD, Bollinger Bands)**
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
- Multiple condition types (overbought, oversold, crossovers)
- Integration with existing trigger system

##### Supported Indicators

**RSI (Relative Strength Index)**

- Configurable period (default: 14)
- Custom overbought/oversold levels (default: 70/30)
- Crossover detection (entry/exit signals)
- Multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)
- Conditions: `overbought`, `oversold`, `crossover_overbought`, `crossover_oversold`

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

# RSI Overbought Alert
{
    "symbol": "BTC",
    "indicator_type": "rsi",
    "condition": "overbought",
    "description": "BTC RSI overbought alert",
    "config": {
        "period": 14,
        "overbought_level": 75,
        "oversold_level": 25,
        "timeframe": "5m"
    }
}

# RSI Crossover Alert with Bybit Trigger
{
    "symbol": "ETH",
    "indicator_type": "rsi",
    "condition": "crossover_oversold",
    "description": "ETH RSI crossed below oversold - Buy Signal",
    "config": {
        "period": 21,
        "overbought_level": 70,
        "oversold_level": 20,
        "timeframe": "15m"
    }
}

# RSI Alert with Trading Action
{
    "symbol": "SOL",
    "indicator_type": "rsi",
    "condition": "overbought",
    "description": "SOL RSI overbought - Take profit",
    "config": {
        "period": 14,
        "overbought_level": 80,
        "oversold_level": 20,
        "timeframe": "1h"
    }
}
```

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