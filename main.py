import time
import hmac
import hashlib
import json
import requests
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

API_KEY = "Bld82CzzFzxIF65j4O"
API_SECRET = "jY435wiXMgBXpeKXscGg12iFCIJn62XlUHDr"

RECV_WINDOW = "5000"
BYBIT_URL = "https://api.bybit.com"


class TradeRequest(BaseModel):
    action: str
    symbol: str = "DOGEUSDT"
    amount_usdt: float = 6


@app.get("/")
def home():
    return {"status": "online"}


@app.post("/trade")
def trade(
    data: TradeRequest,
    authorization: str | None = Header(default=None)
):

    # التحقق من التوكن
    if authorization != "Bearer Medmed345678.":
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    action = data.action.upper()

    if action not in ["BUY", "SELL"]:
        raise HTTPException(
            status_code=400,
            detail="Only BUY or SELL allowed"
        )

    side = "Buy" if action == "BUY" else "Sell"

    timestamp = str(int(time.time() * 1000))

    # جلب سعر DOGE الحالي
    ticker_response = requests.get(
        BYBIT_URL + "/v5/market/tickers",
        params={
            "category": "linear",
            "symbol": data.symbol
        },
        timeout=10
    )

    ticker_data = ticker_response.json()

    price = float(
        ticker_data["result"]["list"][0]["lastPrice"]
    )

    # تحويل 6 USDT إلى كمية DOGE
    qty = data.amount_usdt / price

    # تقريب الكمية
    qty = round(qty, 0)

    body = {
        "category": "linear",
        "symbol": data.symbol,
        "side": side,
        "orderType": "Market",
        "qty": str(qty)
    }

    body_string = json.dumps(
        body,
        separators=(",", ":")
    )

    sign_payload = (
        timestamp
        + API_KEY
        + RECV_WINDOW
        + body_string
    )

    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": signature
    }

    response = requests.post(
        BYBIT_URL + "/v5/order/create",
        headers=headers,
        data=body_string,
        timeout=10
    )

    return {
        "action": action,
        "symbol": data.symbol,
        "price": price,
        "qty": qty,
        "bybit_response": response.json()
    }
