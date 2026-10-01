from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class EsewaPaymentRequestData(BaseModel):
    amount: str
    tax_amount: str = "0"
    total_amount: str
    transaction_uuid: str
    product_code: str
    product_service_charge: str = "0"
    product_delivery_charge: str = "0"
    success_url: str
    failure_url: str
    signed_field_names: str
    signature: str


class EsewaCallbackData(BaseModel):
    transaction_code: Optional[str] = None
    status: Optional[str] = None
    total_amount: Optional[Any] = None
    transaction_uuid: Optional[str] = None
    product_code: Optional[str] = None
    signed_field_names: Optional[str] = None
    signature: Optional[str] = None


class EsewaVerificationResult(BaseModel):
    is_valid: bool
    status: str
    transaction_uuid: str
    total_amount: float
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    message: str = ""