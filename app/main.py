import asyncio
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from eth_account import Account
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from urllib import error as urllib_error
from urllib import request as urllib_request

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

from config import config

app = FastAPI(title="Hyperliquid TradingView Webhook Bot – Percent Risk")

# Logging setup
logger = logging.getLogger("hyperliquid-bot")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("/app/logs/bot.log", maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter

# Exception handler wrapper to match FastAPI's ExceptionHandler type signature
def rate_limit_exception_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, RateLimitExceeded):
        return _rate_limit_exceeded_handler(request, exc)
    raise exc

app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(SlowAPIMiddleware)

# API setup
API_URL = constants.TESTNET_API_URL if config.env == "TESTNET" else constants.MAINNET_API_URL

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_info():
    return Info(API_URL)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_exchange():
    return Exchange(
        wallet=Account.from_key(config.secret_key),
        account_address=config.address,
        vault_address=config.sub_address,   # ← NEU: Sub-Account-Unterstützung
        base_url=API_URL,
    )

info = get_info()
exchange = get_exchange()


def send_discord_dm(message: str) -> None:
    if not config.discord_bot_token or not config.discord_user_id:
        return

    headers = {
        "Authorization": f"Bot {config.discord_bot_token}",
        "Content-Type": "application/json",
        "User-Agent": "hyperliquid-executioner/1.0",
    }

    create_dm_request = urllib_request.Request(
        "https://discord.com/api/v10/users/@me/channels",
        data=json.dumps({"recipient_id": config.discord_user_id}).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib_request.urlopen(create_dm_request, timeout=10) as response:
            channel_id = json.loads(response.read().decode("utf-8"))["id"]
    except (urllib_error.HTTPError, urllib_error.URLError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to create Discord DM channel: {exc}") from exc

    send_message_request = urllib_request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=json.dumps({"content": message}).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib_request.urlopen(send_message_request, timeout=10) as response:
            response.read()
    except (urllib_error.HTTPError, urllib_error.URLError) as exc:
        raise RuntimeError(f"Failed to send Discord DM: {exc}") from exc


async def notify_order_executed(*, direction: str, size: float, risk: float, equity: float, price: float, order_result: dict) -> None:
    if not config.discord_bot_token or not config.discord_user_id:
        return

    order_summary = order_result.get("order", order_result)
    message = (
        "Hyperliquid order executed\n"
        f"Symbol: {config.coin}\n"
        f"Direction: {direction}\n"
        f"Size: {size:.6f} {config.coin}\n"
        f"Risk: {risk * 100:.2f}%\n"
        f"Equity: ${equity:,.2f}\n"
        f"Price: ${price:,.2f}\n"
        f"Result: {order_summary}"
    )

    await asyncio.to_thread(send_discord_dm, message)

logger.info(f"🚀 Bot started – {config.env} – Risk: {config.risk_percent*100:.2f}% per Trade – Coin: {config.coin}")

class WebhookPayload(BaseModel):
    action: str                    # "buy" or "sell"
    risk_percent: float | None = None   # Optional: Overrides config
    size: float | None = None      # Ignored (we only use percent)

@app.post("/webhook")
@limiter.limit("10/minute")
async def webhook(request: Request):
    if config.webhook_secret:
        if request.headers.get("X-Webhook-Secret") != config.webhook_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = await request.json()
        payload = WebhookPayload.model_validate(data)
    except Exception as e:
        logger.error(f"❌ Invalid JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = payload.action.lower()
    if action not in ["buy", "sell"]:
        return {"status": "error", "message": "Unknown action"}

    is_buy = action == "buy"
    direction = "LONG" if is_buy else "SHORT"

    # === Prozentuale Größenberechnung ===
    try:
        # 1. Aktuellen Account Value holen
        if config.address is None:
            raise ValueError("config.address is not set")
        user_state = info.user_state(config.address)
        equity = float(user_state["marginSummary"]["accountValue"])

        # 2. Aktuellen Preis holen
        mids = info.all_mids()
        price = float(mids.get(config.coin))
        if price <= 0:
            raise ValueError("Could not retrieve price")

        # 3. Risk-Prozent bestimmen (Alert > config)
        risk = payload.risk_percent if payload.risk_percent is not None else config.risk_percent
        if risk <= 0 or risk > 1:
            risk = config.risk_percent  # Sicherheits-Capping

        # 4. Size berechnen
        notional = equity * risk
        sz = notional / price

        logger.info(f"📊 Equity: ${equity:,.2f} | Price: ${price:,.2f} | Risk: {risk*100:.2f}% → Size: {sz:.6f} {config.coin}")

    except Exception as e:
        logger.error(f"❌ Error in size calculation: {e}")
        return {"status": "error", "message": str(e)}

    logger.info(f"📈 Signal: {direction} {sz:.6f} {config.coin} ({risk*100:.2f}% of Equity)")

    try:
        order_result = exchange.market_open(
            name=config.coin,
            is_buy=is_buy,
            sz=sz,
            px=None,
            slippage=config.slippage
        )

        if order_result.get("status") == "ok":
            try:
                await notify_order_executed(
                    direction=direction,
                    size=sz,
                    risk=risk,
                    equity=equity,
                    price=price,
                    order_result=order_result,
                )
            except Exception as exc:
                logger.warning(f"⚠️ Discord notification failed: {exc}")

            logger.info("✅ Order placed successfully")
            return {
                "status": "success",
                "direction": direction,
                "size": round(sz, 6),
                "risk_percent": risk * 100,
                "equity": equity,
                "price": price,
                "result": order_result
            }
        else:
            logger.error(f"❌ Order failed: {order_result}")
            return {"status": "error", "result": order_result}

    except Exception as e:
        logger.exception("💥 Exception during order placement")
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    # Simple stats
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "env": config.env,
        "coin": config.coin,
        "risk_percent": config.risk_percent * 100
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)