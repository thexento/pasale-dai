from dataclasses import dataclass
from typing import Optional


class OrderStatus:
    PENDING = "pending"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    AWAITING_CUSTOMER_DETAILS = "awaiting_customer_details"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class Customer:
    id: int
    discord_user_id: str
    discord_username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location_link: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Product:
    id: str
    sku: str
    name: str
    description: str
    price: float
    currency: str
    image_path: str
    stock: int
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Order:
    id: int
    order_number: str
    customer_id: int
    product_id: Optional[str] = None
    quantity: int = 1
    total_amount: float = 0.0
    currency: str = "NPR"
    status: str = "pending"
    delivery_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_location_link: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Payment:
    id: int
    order_id: int
    transaction_id: str
    product_code: str
    amount: float
    currency: str
    status: str
    raw_response: Optional[str] = None
    verified_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Invoice:
    id: int
    order_id: int
    invoice_number: str
    file_path: str
    created_at: Optional[str] = None


@dataclass
class Conversation:
    id: int
    customer_id: int
    role: str
    message: str
    created_at: Optional[str] = None