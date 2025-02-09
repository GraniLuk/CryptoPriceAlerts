# Bitcoin Price Alerts

A serverless Azure Functions application that monitors cryptocurrency prices and sends alerts via Telegram when specific price conditions are met.

## Features

### Price Monitoring
- Monitors cryptocurrency prices using CoinGecko API
- Supports two types of price alerts:
  1. Single Symbol Alerts: Monitor individual cryptocurrency prices
  2. Ratio Alerts: Monitor price ratios between two cryptocurrencies

### Alert Types
#### Single Symbol Alerts
- Track price movements for individual cryptocurrencies
- Configurable price thresholds with operators (>, <, =)
- Example: Alert when BTC price goes above $50,000

#### Ratio Alerts
- Monitor price relationships between two cryptocurrencies
- Useful for trading pairs and market analysis
- Example: Alert when BTC/ETH ratio exceeds 15

### Alert Management
- Create new alerts via HTTP endpoint
- Remove existing alerts
- View all current active alerts
- Automatic cleanup of triggered alerts

### Notifications
- Real-time alerts via Telegram
- Formatted messages with alert details
- Configurable notification settings

## Setup

### Prerequisites
- Azure Functions account
- Telegram Bot Token
- CoinGecko API Key
- Azure Storage Account

### Environment Variables

Required environment variables:
- TELEGRAM_ENABLED: true/false
- TELEGRAM_TOKEN: Telegram bot token
- TELEGRAM_CHAT_ID: Telegram chat IDs
- COINGECKO_API_KEY: CoinGecko API key
- AZURE_STORAGE_SHARE_NAME: Azure file share name
- AZURE_STORAGE_STORAGE_ACCOUNT: Storage account name
- AZURE_STORAGE_STORAGE_ACCOUNT_KEY: Storage account key

### Local Development
1. Clone the repository
2. Copy `.env.example` to `.env`
3. Fill in your environment variables
4. Install dependencies: `pip install -r requirements.txt`
5. Run the function locally using Azure Functions Core Tools

## API Endpoints

### Create Alert
```http
POST /api/insert_new_alert_grani

# Single Symbol Alert
{
    "type": "single",
    "symbol": "BTC",
    "price": 50000,
    "operator": ">",
    "description": "BTC above 50k"
}

# Ratio Alert
{
    "type": "ratio",
    "symbol1": "BTC",
    "symbol2": "ETH",
    "price": 15,
    "operator": ">",
    "description": "BTC/ETH ratio above 15"
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
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License
[MIT](https://choosealicense.com/licenses/mit/)