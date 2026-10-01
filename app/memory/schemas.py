from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class OrderContext(BaseModel):
    order_number: Optional[str] = None
    product_id: Optional[str] = None
    quantity: Optional[int] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    payment_verified: bool = False
    details_collected: bool = False


class UserMemoryState(BaseModel):
    user_id: str
    username: str = ""
    summary: str = ""
    recent_messages: List[ChatMessage] = Field(default_factory=list)
    customer_preferences: Dict[str, Any] = Field(default_factory=dict)
    current_order_context: OrderContext = Field(default_factory=OrderContext)