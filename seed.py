"""Seed script to populate database with initial data."""

import logging
from typing import List

from bot.database import get_db

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
    db = get_db()

    existing_count = await db.food_products.count_documents({})

    if existing_count > 0:
        logger.info(f"Found {existing_count} existing food products. Skipping seed.")
        return

    result = await db.food_products.insert_many(DUMMY_PRODUCTS)
    logger.info(f"Seeded {len(result.inserted_ids)} food products to database")
