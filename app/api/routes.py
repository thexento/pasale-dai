import html
import json
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from app.config import settings
from app.database.database import get_db_connection
from app.database.models import OrderStatus, PaymentStatus
from app.database.repositories import (
    ProductRepository,
    OrderRepository,
    PaymentRepository
)
from app.payments.esewa import EsewaPaymentGateway

logger = logging.getLogger("pasale.api")
router = APIRouter()
gateway = EsewaPaymentGateway()


@router.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    return {"name": f"{settings.STORE_NAME} API", "status": "online"}


@router.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    db_ok = False
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": db_ok,
        "ai_configured": bool(settings.GEMINI_API_KEY)
    }


@router.get("/products", tags=["Catalog"])
async def list_products():
    with get_db_connection() as conn:
        repo = ProductRepository(conn)
        products = repo.get_all_active()
        return [p.__dict__ for p in products]


@router.get("/products/{product_id}", tags=["Catalog"])
async def get_product(product_id: str):
    with get_db_connection() as conn:
        repo = ProductRepository(conn)
        product = repo.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product.__dict__


@router.get("/orders/{order_number}", tags=["Orders"])
async def get_order(order_number: str):
    with get_db_connection() as conn:
        repo = OrderRepository(conn)
        order = repo.get_by_number(order_number)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order.__dict__


@router.get("/checkout/{order_number}", response_class=HTMLResponse, tags=["Payments"])
async def checkout_redirect(order_number: str):
    """
    Renders an auto-submitting POST form to eSewa v2.
    Solves the 405 Method Not Allowed error by transforming the browser's GET request
    from Discord into an authoritative HTTP POST with valid HMAC-SHA256 signature.
    """
    with get_db_connection() as conn:
        ord_repo = OrderRepository(conn)
        order = ord_repo.get_by_number(order_number)
        if not order:
            return HTMLResponse("<h3>Order not found.</h3>", status_code=404)

        if order.status in [OrderStatus.PAID, OrderStatus.CONFIRMED]:
            return HTMLResponse("<h3>This order has already been paid for.</h3>", status_code=200)

        # Build signed eSewa payment form data
        payment_payload = gateway.create_payment_payload(order.order_number, order.total_amount)

    form_fields = "\n".join([
        f'<input type="hidden" name="{k}" value="{html.escape(str(v))}">'
        for k, v in payment_payload.model_dump().items()
    ])

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting to eSewa - {html.escape(settings.STORE_NAME)}</title>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: #f1f5f9;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 440px;
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #16a34a;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            button {{
                background: #16a34a;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 16px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                margin-top: 15px;
            }}
            button:hover {{ background: #15803d; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Redirecting to eSewa</h2>
            <div class="spinner"></div>
            <p>Connecting to secure eSewa test gateway for order <strong>{html.escape(order_number)}</strong> (Rs. {order.total_amount:.2f})...</p>
            
            <form id="esewaForm" method="POST" action="{settings.ESEWA_PAYMENT_URL}">
                {form_fields}
                <button type="submit">Click here if not redirected automatically</button>
            </form>
        </div>

        <script>
            // Automatically submit POST form to eSewa on load
            window.addEventListener('load', function() {{
                document.getElementById('esewaForm').submit();
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/payment/success", response_class=HTMLResponse, tags=["Payments"])
async def esewa_payment_success(data: Optional[str] = Query(None)):
    """Handles eSewa v2 success redirect, decodes query payload, and verifies against eSewa API."""
    if not data:
        return HTMLResponse("<h3>Invalid payment response: Missing data payload.</h3>", status_code=400)

    decoded = gateway.decode_callback_data(data)
    transaction_uuid = decoded.get("transaction_uuid")
    total_amount_str = decoded.get("total_amount")

    if not transaction_uuid or not total_amount_str:
        return HTMLResponse("<h3>Corrupt transaction payload received.</h3>", status_code=400)

    try:
        total_amount = float(str(total_amount_str).replace(",", ""))
    except ValueError:
        return HTMLResponse("<h3>Invalid total_amount format.</h3>", status_code=400)

    # Authoritatively verify with eSewa servers
    verify_result = await gateway.verify_transaction(transaction_uuid, total_amount)
    if not verify_result.is_valid:
        logger.warning(f"eSewa verification rejected for UUID: {transaction_uuid}")
        return HTMLResponse(
            f"<h3>Payment Verification Failed</h3><p>{html.escape(verify_result.message)}</p>",
            status_code=400
        )

    # Update database inside a transaction
    with get_db_connection() as conn:
        pay_repo = PaymentRepository(conn)
        ord_repo = OrderRepository(conn)

        payment = pay_repo.get_by_transaction_id(transaction_uuid)
        if not payment:
            return HTMLResponse("<h3>Transaction record not found in system.</h3>", status_code=404)

        # Idempotency check: avoid double-processing
        if payment.status != PaymentStatus.SUCCESS:
            pay_repo.mark_success(payment.id, json.dumps(verify_result.raw_response))
            ord_repo.update_status(payment.order_id, OrderStatus.PAID)
            logger.info(f"Payment marked SUCCESS for Order ID {payment.order_id}")

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful - {html.escape(settings.STORE_NAME)}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); max-width: 480px; text-align: center; }}
            h2 {{ color: #16a34a; margin-top: 0; }}
            p {{ color: #475569; font-size: 16px; line-height: 1.5; }}
            .highlight {{ background: #f1f5f9; padding: 10px; border-radius: 6px; font-weight: bold; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Payment Successful!</h2>
            <p>Your payment for transaction <span class="highlight">{html.escape(transaction_uuid)}</span> has been securely verified.</p>
            <p><strong>Next Step:</strong> Please return to your <strong>Discord chat</strong> and provide your mobile phone number and delivery address so we can finalize delivery and send your invoice!</p>
        </div>
    </body>
    </html>
    """)


@router.get("/payment/failure", response_class=HTMLResponse, tags=["Payments"])
async def esewa_payment_failure():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #fef2f2;">
        <h2 style="color: #dc2626;">Payment Cancelled or Failed</h2>
        <p>The transaction was not completed. You can return to Discord to retry or select another item.</p>
    </body>
    </html>
    """)