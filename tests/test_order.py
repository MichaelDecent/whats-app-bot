import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.services import order

class DummyCursor:
    def __init__(self, items):
        self.items = items
    async def to_list(self, length=None):
        return self.items

class DummyCollection:
    def __init__(self, items):
        self._items = items
    def find(self, query):
        return DummyCursor(self._items)

class DummyDB:
    def __init__(self, items):
        self.food_products = DummyCollection(items)

@pytest.mark.asyncio
async def test_show_menu_enumerates(monkeypatch):
    products = [
        {"name": "Margherita Pizza", "price": 12.99},
        {"name": "Cheeseburger", "price": 8.5},
    ]
    fake_db = DummyDB(products)
    monkeypatch.setattr(order, "get_db", lambda: fake_db)
    sent = {}
    async def fake_send(user_id, text):
        sent['text'] = text
    monkeypatch.setattr(order, "send_message", fake_send)

    await order.show_menu("user")
    assert "1. Margherita Pizza – ₦12.99" in sent['text']
    assert "2. Cheeseburger – ₦8.5" in sent['text']
    assert sent['text'].strip().endswith("Type the item numbers and quantities, or type `cancel` anytime.")

class DummyAI:
    class Chat:
        class Completions:
            async def create(self, *a, **kw):
                raise AssertionError("OpenAI should not be called")
        completions = Completions()
    chat = Chat()

def dummy_ai_client():
    return DummyAI()

@pytest.mark.asyncio
async def test_parse_items_numeric(monkeypatch):
    products = [
        {"name": "Margherita Pizza", "price": 12.99},
        {"name": "Cheeseburger", "price": 8.5},
        {"name": "Salad", "price": 9.0},
    ]
    fake_db = DummyDB(products)
    monkeypatch.setattr(order, "get_db", lambda: fake_db)
    monkeypatch.setattr(order, "get_openai_client", dummy_ai_client)

    result = await order._parse_items("1x2 3")
    assert result == [
        {"product": "Margherita Pizza", "quantity": 2},
        {"product": "Salad", "quantity": 1},
    ]

