import types
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.services import order as order_service
from bot import ai_client


class DummySettings:
    MODEL_MODEL = "test"

class FakeCursor:
    def __init__(self, items):
        self._items = items

    async def to_list(self, length=None):
        return self._items

class FakeDB:
    def __init__(self, products):
        self.food_products = types.SimpleNamespace(find=lambda q: FakeCursor(products))

@pytest.mark.asyncio
async def test_parse_items_api_success(monkeypatch):
    db = FakeDB([{"name": "Cheeseburger", "is_available": True}])
    monkeypatch.setattr(order_service, "get_db", lambda: db)
    monkeypatch.setattr(order_service, "get_settings", lambda: DummySettings())

    class FakeClient:
        def __init__(self, content):
            self.content = content
            self.chat = types.SimpleNamespace(completions=self)

        async def create(self, *a, **k):
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=self.content))]
            )

    monkeypatch.setattr(ai_client, "get_openai_client", lambda: FakeClient('{"items": [{"product": "Cheeseburger", "quantity": 2}]}'))

    items = await order_service._parse_items("2x burger")
    assert items == [{"product": "Cheeseburger", "quantity": 2}]

@pytest.mark.asyncio
async def test_parse_items_regex_fallback(monkeypatch):
    products = [
        {"name": "Cheeseburger", "is_available": True},
        {"name": "Margherita Pizza", "is_available": True},
    ]
    db = FakeDB(products)
    monkeypatch.setattr(order_service, "get_db", lambda: db)
    monkeypatch.setattr(order_service, "get_settings", lambda: DummySettings())

    class FakeClient:
        def __init__(self):
            self.chat = types.SimpleNamespace(completions=self)

        async def create(self, *a, **k):
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="not json"))]
            )

    monkeypatch.setattr(ai_client, "get_openai_client", lambda: FakeClient())
    items = await order_service._parse_items("2x pizza")
    assert items == [{"product": "Margherita Pizza", "quantity": 2}]
