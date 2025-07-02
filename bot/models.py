from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, model_validator


class FoodProduct(BaseModel):
    """Representation of a food item."""

    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    description: str
    price: float
    stock: int
    is_available: bool = True

    model_config = ConfigDict(populate_by_name=True)


class OrderItem(BaseModel):
    """Embedded item within an order."""

    product_id: str
    name: str
    quantity: int
    unit_price: float

    @model_validator(mode="after")
    def check_values(cls, model: "OrderItem") -> "OrderItem":
        if model.quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        if model.unit_price < 0:
            raise ValueError("unit_price must be non-negative")
        return model


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    delivered = "delivered"


class Order(BaseModel):
    """Customer order model."""

    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
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
