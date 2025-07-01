import os
import sys

import pytest
from pydantic import ValidationError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.models import OrderItem


def test_order_item_invalid_quantity():
    with pytest.raises(ValidationError):
        OrderItem.model_validate({
            'product_id': '1',
            'name': 'Burger',
            'quantity': 0,
            'unit_price': 5.0,
        })


def test_order_item_negative_price():
    with pytest.raises(ValidationError):
        OrderItem.model_validate({
            'product_id': '1',
            'name': 'Burger',
            'quantity': 1,
            'unit_price': -2.0,
        })


