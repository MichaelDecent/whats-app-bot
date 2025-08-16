from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Dict, Any

from sqlalchemy import Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pydantic import BaseModel, model_validator

from .database import Base


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    delivered = "delivered"


class ServiceType(str, Enum):
    order = "order"
    nutrition = "nutrition"


# SQLAlchemy Models
class FoodProduct(Base):
    """SQLAlchemy model for food items."""

    __tablename__ = "food_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Order(Base):
    """SQLAlchemy model for orders."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=OrderStatus.pending.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationship to order items
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    """SQLAlchemy model for order items."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("food_products.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["FoodProduct"] = relationship("FoodProduct")


class UserSession(Base):
    """SQLAlchemy model for user sessions."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    service: Mapped[str] = mapped_column(String, nullable=False)
    step: Mapped[str] = mapped_column(
        String, nullable=False
    )  # Changed from 'state' to match current usage
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default={})
    history: Mapped[List[Dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=[]
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class NutritionLog(Base):
    """SQLAlchemy model for nutrition chat logs."""

    __tablename__ = "nutrition_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    messages: Mapped[List[Dict[str, str]]] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# Pydantic models for API validation (keeping these for backward compatibility)
class ChatMessage(BaseModel):
    role: str
    content: str


class OrderItemValidator(BaseModel):
    """Pydantic validator for OrderItem data."""

    product_id: int
    name: str
    quantity: int
    unit_price: float

    @model_validator(mode="after")
    def check_values(cls, model: "OrderItemValidator") -> "OrderItemValidator":
        if model.quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        if model.unit_price < 0:
            raise ValueError("unit_price must be non-negative")
        return model


class FoodProductValidator(BaseModel):
    """Pydantic validator for FoodProduct data."""

    name: str
    description: str
    price: float
    stock: int
    is_available: bool = True

    @model_validator(mode="after")
    def check_values(cls, model: "FoodProductValidator") -> "FoodProductValidator":
        if model.price < 0:
            raise ValueError("price must be non-negative")
        if model.stock < 0:
            raise ValueError("stock must be non-negative")
        return model
