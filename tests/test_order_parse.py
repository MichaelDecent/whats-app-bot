import types
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.services import order as order_service
from bot import ai_client
from bot.models import FoodProduct


class DummySettings:
    MODEL_MODEL = "test"


class MockResult:
    def __init__(self, products):
        self._products = products

    def scalars(self):
        return MockScalars(self._products)


class MockScalars:
    def __init__(self, products):
        self._products = products

    def all(self):
        return [MockProduct(p) for p in self._products]


class MockProduct:
    def __init__(self, data):
        self.name = data["name"]
        self.is_available = data["is_available"]


class MockSession:
    def __init__(self, products):
        self._products = products

    async def execute(self, stmt):
        return MockResult(self._products)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSessionMaker:
    def __init__(self, products):
        self._products = products

    def __call__(self):
        return MockSession(self._products)


@pytest.mark.asyncio
async def test_parse_items_api_success(monkeypatch):
    products = [{"name": "Cheeseburger", "is_available": True}]
    session_maker = MockSessionMaker(products)
    monkeypatch.setattr(order_service, "get_db", lambda: session_maker)
    monkeypatch.setattr(order_service, "get_settings", lambda: DummySettings())

    class FakeClient:
        def __init__(self, content):
            self.content = content

        async def create(self, *a, **k):
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content=self.content)
                    )
                ]
            )

    monkeypatch.setattr(
        order_service,
        "create_chat_completion",
        lambda *a, **k: FakeClient(
            '{"items": [{"product": "Cheeseburger", "quantity": 2}]}'
        ).create(),
    )

    items = await order_service._parse_items("2x burger")
    assert items == [{"product": "Cheeseburger", "quantity": 2}]


@pytest.mark.asyncio
async def test_parse_items_regex_fallback(monkeypatch):
    products = [
        {"name": "Cheeseburger", "is_available": True},
        {"name": "Margherita Pizza", "is_available": True},
    ]
    session_maker = MockSessionMaker(products)
    monkeypatch.setattr(order_service, "get_db", lambda: session_maker)
    monkeypatch.setattr(order_service, "get_settings", lambda: DummySettings())

    class FakeClient:
        def __init__(self):
            pass

        async def create(self, *a, **k):
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content="not json")
                    )
                ]
            )

    monkeypatch.setattr(
        order_service, "create_chat_completion", lambda *a, **k: FakeClient().create()
    )
    items = await order_service._parse_items("2x pizza")
    assert items == [{"product": "Margherita Pizza", "quantity": 2}]
