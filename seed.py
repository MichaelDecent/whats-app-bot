"""Seed script to populate database with initial data."""

import logging
from typing import List

from sqlalchemy import select

from bot.database import get_db
from bot.models import FoodProduct, FoodProductValidator

logger = logging.getLogger(__name__)

DUMMY_PRODUCTS: List[dict] = [
    {
        "name": "Margherita Pizza",
        "description": "Classic pizza with tomato sauce, mozzarella, and basil",
        "price": 12.99,
        "stock": 50,
        "is_available": True,
    },
    {
        "name": "Chicken Caesar Salad",
        "description": "Fresh romaine lettuce with grilled chicken, croutons, and Caesar dressing",
        "price": 9.99,
        "stock": 30,
        "is_available": True,
    },
    {
        "name": "Cheeseburger",
        "description": "Beef patty with cheddar cheese, lettuce, tomato, and special sauce",
        "price": 8.50,
        "stock": 40,
        "is_available": True,
    },
    {
        "name": "Vegetable Stir Fry",
        "description": "Fresh seasonal vegetables stir-fried in soy ginger sauce",
        "price": 11.25,
        "stock": 25,
        "is_available": True,
    },
    {
        "name": "Chocolate Brownie",
        "description": "Rich chocolate brownie with vanilla ice cream",
        "price": 5.99,
        "stock": 35,
        "is_available": True,
    },
    {
        "name": "Grilled Salmon",
        "description": "Fresh salmon fillet with lemon herb butter and steamed vegetables",
        "price": 16.50,
        "stock": 20,
        "is_available": True,
    },
    {
        "name": "Pasta Carbonara",
        "description": "Spaghetti with creamy sauce, pancetta, and parmesan cheese",
        "price": 13.75,
        "stock": 30,
        "is_available": True,
    },
    {
        "name": "Chicken Wings",
        "description": "Spicy buffalo wings with blue cheese dip",
        "price": 10.99,
        "stock": 45,
        "is_available": True,
    },
    {
        "name": "Greek Salad",
        "description": "Mixed greens with feta, olives, cucumber, and Greek dressing",
        "price": 8.25,
        "stock": 30,
        "is_available": True,
    },
    {
        "name": "Fruit Smoothie",
        "description": "Blended seasonal fruits with yogurt and honey",
        "price": 6.50,
        "stock": 40,
        "is_available": True,
    },
]


async def seed_food_products() -> None:
    """Seed the database with dummy food products if none exist."""
    async_session_maker = get_db()

    async with async_session_maker() as session:
        # Check if products already exist
        stmt = select(FoodProduct)
        result = await session.execute(stmt)
        existing_products = result.scalars().all()

        if existing_products:
            logger.info(
                f"Found {len(existing_products)} existing food products. Skipping seed."
            )
            return

        # Validate and create products
        products_to_add = []
        for product_data in DUMMY_PRODUCTS:
            try:
                # Validate with Pydantic
                validated_data = FoodProductValidator.model_validate(product_data)
                # Create SQLAlchemy model instance
                product = FoodProduct(**validated_data.model_dump())
                products_to_add.append(product)
            except Exception as e:
                logger.error(
                    f"Error validating product {product_data.get('name', 'Unknown')}: {e}"
                )
                continue

        # Add all products to the session
        session.add_all(products_to_add)
        await session.commit()

        logger.info(f"Seeded {len(products_to_add)} food products to database")
