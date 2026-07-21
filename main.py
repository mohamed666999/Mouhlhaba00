from fastapi import FastAPI, Request
import requests
import time
import hashlib
import hmac
import json

app = FastAPI()

# تم وضع المفاتيح مباشرة داخل الكود كما طلبت
API_KEY = "Bld82CzzFzxIF65j4O"
API_SECRET = "jY435wiXMgBXpeKXscGg12iFCIJn62XlUHDr"
BASE_URL = "https://api.bybit.com"

@app.post("/trade")
async def trade(request: Request):
    try:
        data = await request.json()
        symbol = data.get("symbol", "DOGEUSDT")
        side = data.get("side", "Buy")
        amount_usdt = float(data.get("amount_usdt", 3))

        # 1. جلب السعر الحالي للعملة من Bybit
        ticker_url = f"{BASE_URL}/v5/market/tickers?category=spot&symbol={symbol}"
        ticker_response = requests.get(ticker_url)
        
        if ticker_response.status_code != 200:
            return {"error": "فشل في جلب السعر", "details": ticker_response.text}
            
        ticker_data = ticker_response.json()
        last_price = float(ticker_data["result"]["list"][0]["lastPrice"])
        
        # 2. حساب الكمية المطلوبة (DOGE) بناءً على المبلغ
        qty = amount_usdt / last_price
        qty_str = str(round(qty, 1))

        # 3. تجهيز بيانات الطلب لفتحه على Bybit
        endpoint = "/v5/order/create"
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        
        payload = {
            "category": "spot",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": qty_str
        }
        
        payload_str = json.dumps(payload)
        param_str = timestamp + API_KEY + recv_window + payload_str
        
        # إنشاء التوقيع الأمني HMAC-SHA256
        hash_mac = hmac.new(bytes(API_SECRET, "utf-8"), param_str.encode("utf-8"), hashlib.sha256)
        signature = hash_mac.hexdigest()
        
        # 4. إرسال الطلب النهائي الموثق إلى Bybit
        headers = {
            "X-BAPI-API-KEY": API_KEY,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }
        
        order_url = BASE_URL + endpoint
        order_response = requests.post(order_url, headers=headers, data=payload_str)
        
        return {
            "message": "تم إرسال الطلب بنجاح",
            "price_used": last_price,
            "qty_calculated": qty_str,
            "bybit_response": order_response.json()
        }
        
    except Exception as e:
        return {"error": "حدث خطأ برمجي", "message": str(e)}
