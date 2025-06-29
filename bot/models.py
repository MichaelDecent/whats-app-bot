from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from pydantic import BaseModel, Field, ConfigDict


class FoodProduct(BaseModel):
    """Representation of a food item."""

    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    description: str
    price: float
    stock: int
    image_url: Optional[str] = None
    is_available: bool = True

    model_config = ConfigDict(populate_by_name=True)


class OrderItem(BaseModel):
    """Embedded item within an order."""

    product_id: str
    name: str
    quantity: int
    unit_price: float


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    delivered = "delivered"


class Order(BaseModel):
    """Customer order model."""

    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    items: List[OrderItem]
    total_price: float
    delivery_address: str
    status: OrderStatus = OrderStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(populate_by_name=True)


class ServiceType(str, Enum):
    order = "order"
    nutrition = "nutrition"


class UserSession(BaseModel):
    """Active user session."""

    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    service: ServiceType
    state: str
    context: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class ChatMessage(BaseModel):
    role: str
    content: str


class NutritionLog(BaseModel):
    """Conversation history for nutrition chats."""

    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    messages: List[ChatMessage]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(populate_by_name=True)
