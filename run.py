import os
import sys
import hmac
import hashlib
import base64
import asyncio
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv

from app.bot.discord_bot import bot

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

ESEWA_PRODUCT_CODE = os.getenv("ESEWA_PRODUCT_CODE", "EPAYTEST")
ESEWA_SECRET_KEY = os.getenv("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
ESEWA_PAYMENT_URL = os.getenv("ESEWA_PAYMENT_URL", "https://rc-epay.esewa.com.np/api/epay/main/v2/form")
ESEWA_VERIFY_URL = os.getenv("ESEWA_VERIFY_URL", "https://rc-epay.esewa.com.np/api/epay/transaction/status/")

def generate_signature(total_amount: str, transaction_uuid: str, product_code: str) -> str:
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    signature = hmac.new(
        ESEWA_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode("utf-8")

@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(bot.start(DISCORD_BOT_TOKEN))
    yield
    await bot.close()
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def index():
    return {"status": "ok"}

@app.get("/checkout", response_class=HTMLResponse)
def esewa_checkout(amount: float, txn_id: str):
    str_amount = str(amount)
    signature = generate_signature(str_amount, txn_id, ESEWA_PRODUCT_CODE)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><title>eSewa Checkout</title></head>
    <body onload="document.forms['esewa_form'].submit()">
        <form name="esewa_form" action="{ESEWA_PAYMENT_URL}" method="POST">
            <input type="hidden" name="amount" value="{str_amount}" />
            <input type="hidden" name="tax_amount" value="0" />
            <input type="hidden" name="total_amount" value="{str_amount}" />
            <input type="hidden" name="transaction_uuid" value="{txn_id}" />
            <input type="hidden" name="product_code" value="{ESEWA_PRODUCT_CODE}" />
            <input type="hidden" name="product_service_charge" value="0" />
            <input type="hidden" name="product_delivery_charge" value="0" />
            <input type="hidden" name="success_url" value="{BASE_URL}/payment/success" />
            <input type="hidden" name="failure_url" value="{BASE_URL}/payment/failure" />
            <input type="hidden" name="signed_field_names" value="total_amount,transaction_uuid,product_code" />
            <input type="hidden" name="signature" value="{signature}" />
            <noscript><input type="submit" value="Pay Now" /></noscript>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/payment/success")
async def payment_success(request: Request):
    encoded_data = request.query_params.get("data")
    if encoded_data:
        decoded_bytes = base64.b64decode(encoded_data)
        return {"status": "success", "data": decoded_bytes.decode("utf-8")}
    return {"status": "success"}

@app.get("/payment/failure")
def payment_failure():
    return {"status": "failed"}

if __name__ == "__main__":
    uvicorn.run("run.py:app", host="0.0.0.0", port=8000, reload=False)