import os
import sys

import pytest
from pydantic import ValidationError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.models import OrderItemValidator, FoodProductValidator


def test_order_item_invalid_quantity():
    with pytest.raises(ValidationError):
        OrderItemValidator.model_validate(
            {
                "product_id": 1,
                "name": "Burger",
                "quantity": 0,
                "unit_price": 5.0,
            }
        )


def test_order_item_negative_price():
    with pytest.raises(ValidationError):
        OrderItemValidator.model_validate(
            {
                "product_id": 1,
                "name": "Burger",
                "quantity": 1,
                "unit_price": -2.0,
            }
        )


def test_food_product_negative_price():
    with pytest.raises(ValidationError):
        FoodProductValidator.model_validate(
            {
                "name": "Pizza",
                "description": "Delicious pizza",
                "price": -10.0,
                "stock": 5,
                "is_available": True,
            }
        )


def test_food_product_negative_stock():
    with pytest.raises(ValidationError):
        FoodProductValidator.model_validate(
            {
                "name": "Pizza",
                "description": "Delicious pizza",
                "price": 10.0,
                "stock": -5,
                "is_available": True,
            }
        )


def test_food_product_valid():
    product = FoodProductValidator.model_validate(
        {
            "name": "Pizza",
            "description": "Delicious pizza",
            "price": 15.99,
            "stock": 10,
            "is_available": True,
        }
    )
    assert product.name == "Pizza"
    assert product.price == 15.99
    assert product.stock == 10
