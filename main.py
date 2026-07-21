e

        }import time
import hmac
import hashlib
import json
import requests

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


app = FastAPI()


# =====================================================
# إعدادات API
# =====================================================

API_KEY = "Bld82CzzFzxIF65j4O"
API_SECRET = "jY435wiXMgBXpeKXscGg12iFCIJn62XlUHDr"

# نفس الكلمة التي تضعها في Make:
# Bearer Medmed345678.
WEBHOOK_TOKEN = "Medmed345678."

RECV_WINDOW = "5000"

BYBIT_URL = "https://api.bybit.com"

# العملة
DEFAULT_SYMBOL = "DOGEUSDT"

# قيمة الصفقة بالدولار
TRADE_AMOUNT_USDT = 6.0


# =====================================================
# البيانات القادمة من Make
# =====================================================

class TradeRequest(BaseModel):

    action: str

    symbol: str = DEFAULT_SYMBOL

    amount_usdt: float = TRADE_AMOUNT_USDT


# =====================================================
# الصفحة الرئيسية
# =====================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "service": "Trading API",
        "symbol": DEFAULT_SYMBOL
    }


# =====================================================
# جلب سعر العملة
# =====================================================

def get_current_price(symbol):

    response = requests.get(
        BYBIT_URL + "/v5/market/tickers",
        params={
            "category": "linear",
            "symbol": symbol
        },
        timeout=10
    )

    data = response.json()

    if data.get("retCode") != 0:

        raise Exception(
            "Failed to get market price: "
            + str(data)
        )

    result = data["result"]["list"]

    if not result:

        raise Exception(
            "Symbol not found: "
            + symbol
        )

    return float(result[0]["lastPrice"])


# =====================================================
# جلب معلومات العملة
# لمعرفة الحد الأدنى وحجم الخطوة
# =====================================================

def get_instrument_info(symbol):

    response = requests.get(
        BYBIT_URL + "/v5/market/instruments-info",
        params={
            "category": "linear",
            "symbol": symbol
        },
        timeout=10
    )

    data = response.json()

    if data.get("retCode") != 0:

        raise Exception(
            "Failed to get instrument info: "
            + str(data)
        )

    result = data["result"]["list"]

    if not result:

        raise Exception(
            "Instrument not found: "
            + symbol
        )

    return result[0]


# =====================================================
# تقريب الكمية حسب قواعد Bybit
# =====================================================

def calculate_quantity(symbol, amount_usdt, price):

    instrument = get_instrument_info(symbol)

    lot_size = instrument["lotSizeFilter"]

    qty_step = float(
        lot_size["qtyStep"]
    )

    min_qty = float(
        lot_size["minOrderQty"]
    )

    # قيمة USDT ÷ السعر = كمية العملة
    raw_qty = amount_usdt / price

    # تقريب الكمية إلى الأسفل حسب qtyStep
    qty = int(raw_qty / qty_step) * qty_step

    # معرفة عدد الخانات العشرية
    step_string = str(qty_step)

    if "." in step_string:

        decimals = len(
            step_string.split(".")[1]
        )

        qty = round(
            qty,
            decimals
        )

    else:

        qty = int(qty)

    if qty < min_qty:

        raise Exception(
            f"Calculated quantity {qty} "
            f"is below minimum quantity {min_qty}"
        )

    return str(qty)


# =====================================================
# إنشاء توقيع HMAC-SHA256
# =====================================================

def create_signature(
    timestamp,
    body_string
):

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

    return signature


# =====================================================
# تنفيذ الصفقة
# =====================================================

@app.post("/trade")
def trade(

    data: TradeRequest,

    authorization: str | None = Header(
        default=None
    )
):

    # -------------------------------------------------
    # التحقق من Bearer Token
    # -------------------------------------------------

    expected_token = (

        "Bearer "
        + WEBHOOK_TOKEN
    )

    if authorization != expected_token:

        raise HTTPException(

            status_code=401,

            detail="Unauthorized"
        )


    # -------------------------------------------------
    # التحقق من BUY / SELL
    # -------------------------------------------------

    action = data.action.upper()


    if action not in [

        "BUY",

        "SELL"

    ]:

        raise HTTPException(

            status_code=400,

            detail="Only BUY or SELL allowed"
        )


    # -------------------------------------------------
    # تحديد الاتجاه
    # -------------------------------------------------

    side = (

        "Buy"

        if action == "BUY"

        else "Sell"
    )


    symbol = data.symbol.upper()


    # -------------------------------------------------
    # جلب السعر الحالي
    # -------------------------------------------------

    try:

        current_price = get_current_price(

            symbol
        )

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


    # -------------------------------------------------
    # حساب كمية العملة التي تساوي 6 USDT
    # -------------------------------------------------

    try:

        qty = calculate_quantity(

            symbol,

            data.amount_usdt,

            current_price
        )

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


    # -------------------------------------------------
    # جسم أمر التداول
    # -------------------------------------------------

    body = {

        "category": "linear",

        "symbol": symbol,

        "side": side,

        "orderType": "Market",

        "qty": qty

    }


    # تحويل JSON إلى نص مضغوط
    body_string = json.dumps(

        body,

        separators=(",", ":")

    )


    # -------------------------------------------------
    # Timestamp
    # -------------------------------------------------

    timestamp = str(

        int(

            time.time()

            * 1000

        )

    )


    # -------------------------------------------------
    # HMAC-SHA256
    # -------------------------------------------------

    signature = create_signature(

        timestamp,

        body_string

    )


    # -------------------------------------------------
    # Headers الخاصة بـ Bybit
    # -------------------------------------------------

    headers = {

        "Content-Type":

        "application/json",

        "X-BAPI-API-KEY":

        API_KEY,

        "X-BAPI-TIMESTAMP":

        timestamp,

        "X-BAPI-RECV-WINDOW":

        RECV_WINDOW,

        "X-BAPI-SIGN":

        signature

    }


    # -------------------------------------------------
    # إرسال أمر التداول
    # -------------------------------------------------

    response = requests.post(

        BYBIT_URL

        + "/v5/order/create",

        headers=headers,

        data=body_string,

        timeout=10

    )


    # -------------------------------------------------
    # إرجاع النتيجة إلى Make
    # -------------------------------------------------

    try:

        bybit_response = response.json()

    except Exception:

        bybit_response = {

            "raw_response":

            response.text

        }


    return {

        "success":

        bybit_response.get(

            "retCode"

        ) == 0,

        "action":

        action,

        "symbol":

        symbol,

        "price":

        current_price,

        "amount_usdt":

        data.amount_usdt,

        "quantity":

        qty,

        "bybit_response":

        bybit_response

    }
