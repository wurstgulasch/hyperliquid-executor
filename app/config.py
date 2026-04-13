import os
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

load_dotenv()

class Config(BaseModel):
    env: str = Field(default="TESTNET", description="Environment: TESTNET or MAINNET")
    address: str | None = Field(default=None, description="Hyperliquid master wallet address")
    secret_key: str | None = Field(default=None, description="Hyperliquid secret key")
    coin: str = Field(default="BTC", description="Trading coin")
    risk_percent: float = Field(default=0.01, ge=0.0001, le=0.1, description="Risk percentage per trade")
    sub_address: str | None = Field(default=None, description="Hyperliquid vault / sub-account address (optional, leave empty for master)")
    slippage: float = Field(default=0.015, ge=0, le=0.1, description="Slippage tolerance")
    webhook_secret: str | None = Field(default=None, description="Webhook secret for authentication")
    discord_bot_token: str | None = Field(default=None, description="Discord bot token for DM notifications")
    discord_user_id: str | None = Field(default=None, description="Discord user ID to receive DM notifications")

    @validator('env')
    def validate_env(cls, v):
        if v not in ["TESTNET", "MAINNET"]:
            raise ValueError("ENV must be TESTNET or MAINNET")
        return v

    @validator('address')
    def validate_address(cls, v):
        if not v:
            raise ValueError("HYPERLIQUID_MASTER_ADDRESS is required")
        return v

    @validator('secret_key')
    def validate_secret_key(cls, v):
        if not v:
            raise ValueError("HYPERLIQUID_SECRET_KEY is required")
        return v

    @validator('webhook_secret')
    def validate_webhook_secret(cls, v, values):
        if values.get('env') == "MAINNET" and not v:
            raise ValueError("WEBHOOK_SECRET is required for MAINNET")
        return v

# Load config
config = Config(
    env=os.getenv("ENV", "TESTNET"),
    address=os.getenv("HYPERLIQUID_MASTER_ADDRESS"),
    secret_key=os.getenv("HYPERLIQUID_SECRET_KEY"),
    coin=os.getenv("COIN", "BTC"),
    risk_percent=float(os.getenv("RISK_PERCENT", 0.01)),
    slippage=float(os.getenv("SLIPPAGE", 0.015)),
    webhook_secret=os.getenv("WEBHOOK_SECRET"),
    discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
    discord_user_id=os.getenv("DISCORD_USER_ID"),
    sub_address=os.getenv("HYPERLIQUID_SUB_ADDRESS"),
)