import asyncio
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import mongomock_motor

from bot.services import order
from bot import database, config

class DummySettings:
    API_KEY = ""
    MODEL_MODEL = "gpt"
    WHATSAPP_ACCESS_TOKEN = ""
    WHATSAPP_PHONE_NUMBER_ID = ""
    WHATSAPP_VERIFY_TOKEN = ""
    DELIVERY_PHONE_NUMBER = None
    MONGO_URL = "mongodb://localhost"
    MONGO_DB_NAME = "testdb"
    MONGO_COLLECTION_NAME = ""
    SESSION_TTL_SECONDS = 3600

import pytest_asyncio


@pytest_asyncio.fixture
async def db(monkeypatch):
    client = mongomock_motor.AsyncMongoMockClient()
    test_db = client[DummySettings.MONGO_DB_NAME]
    monkeypatch.setattr(database, "client", client)
    monkeypatch.setattr(database, "db", test_db)
    monkeypatch.setattr(database, "get_db", lambda: test_db)
    orig_get = config.get_settings
    orig_get.cache_clear()
    monkeypatch.setattr(config, "get_settings", lambda: DummySettings())
    monkeypatch.setattr(order, "get_settings", lambda: DummySettings())
    yield test_db

@pytest.mark.asyncio
async def test_concurrent_order_on_last_item(db, monkeypatch):
    prod_id = (await db.food_products.insert_one({
        "name": "Burger",
        "price": 10.0,
        "stock": 1,
        "is_available": True,
    })).inserted_id

    item = {
        "product_id": prod_id,
        "name": "Burger",
        "quantity": 1,
        "unit_price": 10.0,
    }

    data: Dict[str, Any] = {
        "items": [item],
        "total_price": 10.0,
        "address": "somewhere",
    }

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr(order, "send_message", noop)

    session = {"step": "confirm_address", "data": data}

    async def place(uid: str):
        return await order.handle(uid, "yes", session.copy())

    res1, res2 = await asyncio.gather(place("A"), place("B"))

    orders = await db.orders.count_documents({})
    stock = (await db.food_products.find_one({"_id": prod_id}))['stock']

    assert orders == 1
    assert stock == 0
    assert [res1, res2].count({"status": "ordered"}) == 1

