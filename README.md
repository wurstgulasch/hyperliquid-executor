# Hyperliquid Executioner

A FastAPI-based webhook bot for executing trades on Hyperliquid based on signals from TradingView. This bot allows you to automate trading by receiving webhook alerts and placing market orders with percentage-based risk management.

## Features

- **Webhook Integration**: Receives trading signals from TradingView via webhooks.
- **Percentage Risk Management**: Calculates position sizes based on a percentage of your account equity.
- **Testnet/Mainnet Support**: Configurable for testing on testnet or live trading on mainnet.
- **Secure Authentication**: Optional webhook secret for validating incoming requests.
- **Discord Notifications**: Optional DM alerts when an order is successfully placed.
- **Docker Support**: Easy deployment using Docker Compose.
- **Real-time Logging**: Comprehensive logging for monitoring trades and errors.

## Installation

### Prerequisites

- Python 3.8+
- Docker and Docker Compose (optional, for containerized deployment)
- Hyperliquid account with API access

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/wurstgulasch/hyperliquid-executioner.git
   cd hyperliquid-executioner
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your configuration (see Configuration section).

4. Run the application:
   ```bash
   python -m app.main
   ```

### Docker Deployment

1. Clone the repository and navigate to the directory.

2. Create a `.env` file with your configuration (see Configuration section).

3. Ensure the `logs` directory exists (created automatically).

4. Build and run with Docker Compose:
   ```bash
   docker compose up --build
   ```

### Configuration

Create a `.env` file with the following variables:

- `ENV`: TESTNET or MAINNET (default: TESTNET)
- `HYPERLIQUID_ADDRESS`: Your Hyperliquid wallet address (required)
- `HYPERLIQUID_SECRET_KEY`: Your Hyperliquid secret key (required)
- `COIN`: Trading coin (default: BTC)
- `RISK_PERCENT`: Risk percentage per trade (default: 0.01, max 0.1)
- `SLIPPAGE`: Slippage tolerance (default: 0.015)
- `WEBHOOK_SECRET`: Secret for webhook authentication (required for MAINNET)
- `DISCORD_BOT_TOKEN`: Discord bot token for DM notifications
- `DISCORD_USER_ID`: Discord user ID that should receive the DM notifications

### Features

- **Resilient API Calls**: Automatic retries with exponential backoff for network issues.
- **Rate Limiting**: 10 requests per minute per IP to prevent abuse.
- **Persistent Logging**: Logs to file with rotation for monitoring.
- **Configuration Validation**: Pydantic-based validation at startup.
- **Resource Limits**: Docker container optimized for low-resource environments.
   ```

The bot will be available at `http://localhost:9001`.

## Configuration

Create a `.env` file in the root directory with the following variables:

```env
# Environment: TESTNET or MAINNET
ENV=TESTNET

# Your Hyperliquid wallet address
HYPERLIQUID_ADDRESS=your_wallet_address_here

# Your Hyperliquid secret key
HYPERLIQUID_SECRET_KEY=your_secret_key_here

# Trading pair (e.g., BTC, ETH)
COIN=BTC

# Default risk percentage per trade (0.01 = 1%)
RISK_PERCENT=0.01

# Slippage tolerance (0.015 = 1.5%)
SLIPPAGE=0.015

# Optional: Webhook secret for authentication
WEBHOOK_SECRET=your_webhook_secret

# Optional: Discord DM notifications for successful orders
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_USER_ID=123456789012345678
```

To use Discord notifications, create a Discord application with a bot, invite the bot to a server you control, and allow direct messages from the bot account. The bot sends a DM only after Hyperliquid confirms that the order was accepted.

**Security Note**: Never commit your `.env` file to version control. Add it to `.gitignore`.

## Usage

### TradingView Setup

1. In TradingView, create an alert with the following JSON payload:
   ```json
   {
     "action": "buy",
     "risk_percent": 0.02
   }
   ```
   - `action`: "buy" or "sell"
   - `risk_percent` (optional): Overrides the default risk percentage from `.env`

2. Set the webhook URL to your bot's endpoint: `http://your-server:9001/webhook`

3. Optionally, set the `X-Webhook-Secret` header to your `WEBHOOK_SECRET` for authentication.

### API Endpoints

- `POST /webhook`: Receives trading signals and executes orders.
- `GET /health`: Health check endpoint.

### Example Webhook Payload

```json
{
  "action": "buy",
  "risk_percent": 0.015,
  "size": 0.1  // Ignored, size is calculated based on risk
}
```

### Response Format

Successful order:
```json
{
  "status": "success",
  "direction": "LONG",
  "size_btc": 0.001234,
  "risk_percent": 1.0,
  "equity": 10000.0,
  "price": 50000.0,
  "result": { ... }
}
```

Error response:
```json
{
  "status": "error",
  "message": "Error description"
}
```

## Risk Management

The bot calculates position sizes based on your account equity and the specified risk percentage:

1. Fetches current account value from Hyperliquid.
2. Retrieves the current price of the trading pair.
3. Calculates the notional value: `equity * risk_percent`.
4. Determines position size: `notional / price`.

This ensures consistent risk per trade regardless of account size.

## Security Considerations

- Use HTTPS in production to encrypt webhook data.
- Implement the `WEBHOOK_SECRET` to verify incoming requests.
- Store sensitive keys securely and never expose them in logs or code.
- Test thoroughly on testnet before using on mainnet.
- Monitor logs for unauthorized access attempts.

## Logging

The bot logs all activities to the console. Key events include:
- Bot startup with configuration summary.
- Incoming webhooks and validation results.
- Order placements and their outcomes.
- Errors and exceptions.

## Troubleshooting

- **Invalid JSON**: Ensure your TradingView alert sends valid JSON.
- **Unauthorized**: Check that the `X-Webhook-Secret` header matches your `WEBHOOK_SECRET`.
- **Order failures**: Verify your account has sufficient funds and API permissions.
- **Discord DM not sent**: Check the bot token, user ID, bot permissions, and whether the target user can receive DMs from the bot.
- **Price retrieval errors**: Check network connectivity and API status.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Disclaimer

This software is for educational and informational purposes only. Trading cryptocurrencies involves significant risk and may result in loss of funds. Use at your own risk and always test on testnet first.
