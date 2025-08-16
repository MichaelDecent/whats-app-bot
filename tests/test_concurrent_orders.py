import asyncio
import os
import sys
from typing import Any, Dict
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from bot.services import order
from bot import database, config
from bot.models import FoodProduct, Order, OrderItem, Base


class DummySettings:
    API_KEY = ""
    MODEL_MODEL = "gpt"
    WHATSAPP_ACCESS_TOKEN = ""
    WHATSAPP_PHONE_NUMBER_ID = ""
    WHATSAPP_VERIFY_TOKEN = ""
    DELIVERY_PHONE_NUMBER = None
    DATABASE_URL = ""  # Will be set in fixture
    SESSION_TTL_SECONDS = 3600


@pytest_asyncio.fixture
async def test_db_session(monkeypatch):
    # Create a temporary in-memory SQLite database for testing
    with tempfile.NamedTemporaryFile() as tmp:
        database_url = f"sqlite+aiosqlite:///{tmp.name}"

        # Create test engine and session
        test_engine = create_async_engine(database_url, echo=False)
        test_session_maker = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Mock database functions
        monkeypatch.setattr(database, "engine", test_engine)
        monkeypatch.setattr(database, "async_session_maker", test_session_maker)
        monkeypatch.setattr(database, "get_db", lambda: test_session_maker)

        # Mock settings
        dummy_settings = DummySettings()
        dummy_settings.DATABASE_URL = database_url
        orig_get = config.get_settings
        orig_get.cache_clear() if hasattr(orig_get, "cache_clear") else None
        monkeypatch.setattr(config, "get_settings", lambda: dummy_settings)
        monkeypatch.setattr(order, "get_settings", lambda: dummy_settings)

        yield test_session_maker

        # Cleanup
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_order_on_last_item(test_db_session, monkeypatch):
    # Add a product with only 1 stock
    async with test_db_session() as session:
        product = FoodProduct(
            name="Burger",
            description="Test burger",
            price=10.0,
            stock=1,
            is_available=True,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        prod_id = product.id

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

    session_data = {"step": "confirm_address", "data": data}

    async def place(uid: str):
        return await order.handle(uid, "yes", session_data.copy())

    # Run concurrent orders
    res1, res2 = await asyncio.gather(place("A"), place("B"), return_exceptions=True)

    # Check results
    async with test_db_session() as session:
        # Count orders
        from sqlalchemy import select, func

        orders_count = await session.execute(select(func.count(Order.id)))
        orders = orders_count.scalar()

        # Check stock
        product_stmt = select(FoodProduct).where(FoodProduct.id == prod_id)
        product_result = await session.execute(product_stmt)
        product = product_result.scalar_one()
        stock = product.stock

    # Only one order should succeed
    assert orders == 1
    assert stock == 0

    # One should succeed, one should fail/await
    success_count = sum(
        1 for r in [res1, res2] if isinstance(r, dict) and r.get("status") == "ordered"
    )
    assert success_count == 1
