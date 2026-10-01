from typing import Optional
from pydantic import BaseModel, Field


class CustomerDetailInput(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None
    location_link: Optional[str] = None
    name: Optional[str] = None


class OrderSummaryResponse(BaseModel):
    order_number: str
    product_id: str
    product_name: str
    quantity: int
    total_amount: float
    status: str
    invoice_number: Optional[str] = None
    invoice_file: Optional[str] = None