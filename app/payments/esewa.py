import base64
import hashlib
import hmac
import json
import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from app.payments.schemas import EsewaPaymentRequestData, EsewaVerificationResult

logger = logging.getLogger("pasale.payments")


class EsewaPaymentGateway:
    def __init__(self):
        self.product_code = settings.ESEWA_PRODUCT_CODE
        self.secret_key = settings.ESEWA_SECRET_KEY
        self.payment_url = settings.ESEWA_PAYMENT_URL
        self.verify_url = settings.ESEWA_VERIFY_URL

    def generate_signature(self, message: str) -> str:
        """Generates HMAC-SHA256 base64-encoded signature for eSewa v2."""
        key = self.secret_key.encode("utf-8")
        msg = message.encode("utf-8")
        h = hmac.new(key, msg, hashlib.sha256)
        return base64.b64encode(h.digest()).decode("utf-8")

    def create_payment_payload(
        self,
        order_number: str,
        total_amount: float
    ) -> EsewaPaymentRequestData:
        """Constructs validated ePay v2 form payload signed with HMAC-SHA256."""
        # eSewa requires integer or exact two-decimal string format
        formatted_amount = f"{total_amount:.2f}".rstrip("0").rstrip(".") if total_amount.is_integer() else f"{total_amount:.2f}"
        transaction_uuid = f"{order_number}-{int(hashlib.md5(order_number.encode()).hexdigest()[:8], 16)}"

        signed_fields = f"total_amount={formatted_amount},transaction_uuid={transaction_uuid},product_code={self.product_code}"
        signature = self.generate_signature(signed_fields)

        success_url = f"{settings.BASE_URL.rstrip('/')}/payment/success"
        failure_url = f"{settings.BASE_URL.rstrip('/')}/payment/failure"

        return EsewaPaymentRequestData(
            amount=formatted_amount,
            tax_amount="0",
            total_amount=formatted_amount,
            transaction_uuid=transaction_uuid,
            product_code=self.product_code,
            product_service_charge="0",
            product_delivery_charge="0",
            success_url=success_url,
            failure_url=failure_url,
            signed_field_names="total_amount,transaction_uuid,product_code",
            signature=signature
        )

    def decode_callback_data(self, encoded_data: str) -> Dict[str, Any]:
        """Decodes the base64 URL query parameter 'data' supplied by eSewa upon redirect."""
        try:
            # Fix URL-safe padding if required
            missing_padding = len(encoded_data) % 4
            if missing_padding:
                encoded_data += "=" * (4 - missing_padding)
            decoded_bytes = base64.b64decode(encoded_data)
            return json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to decode eSewa callback payload: {e}")
            return {}

    async def verify_transaction(
        self,
        transaction_uuid: str,
        total_amount: float
    ) -> EsewaVerificationResult:
        """Authoritatively verifies the payment with eSewa servers via their verification API."""
        formatted_amount = f"{total_amount:.2f}".rstrip("0").rstrip(".") if total_amount.is_integer() else f"{total_amount:.2f}"
        params = {
            "product_code": self.product_code,
            "total_amount": formatted_amount,
            "transaction_uuid": transaction_uuid
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.verify_url, params=params)

                if response.status_code != 200:
                    logger.error(f"eSewa verification failed status: {response.status_code}, body: {response.text}")
                    return EsewaVerificationResult(
                        is_valid=False,
                        status="FAILED",
                        transaction_uuid=transaction_uuid,
                        total_amount=total_amount,
                        message=f"HTTP verification failed with status {response.status_code}"
                    )

                result_data = response.json()
                status = result_data.get("status", "").upper()

                if status == "COMPLETE":
                    return EsewaVerificationResult(
                        is_valid=True,
                        status="COMPLETE",
                        transaction_uuid=transaction_uuid,
                        total_amount=total_amount,
                        raw_response=result_data,
                        message="Payment successfully verified by eSewa."
                    )
                else:
                    return EsewaVerificationResult(
                        is_valid=False,
                        status=status,
                        transaction_uuid=transaction_uuid,
                        total_amount=total_amount,
                        raw_response=result_data,
                        message=f"Payment status is {status}"
                    )
        except Exception as exc:
            logger.exception(f"Exception during eSewa verification: {exc}")
            return EsewaVerificationResult(
                is_valid=False,
                status="ERROR",
                transaction_uuid=transaction_uuid,
                total_amount=total_amount,
                message=str(exc)
            )