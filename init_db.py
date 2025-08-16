#!/usr/bin/env python3
"""Database initialization script for the WhatsApp bot."""

import asyncio
import logging

from bot.database import connect, close
from seed import seed_food_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database() -> None:
    """Initialize database with tables and seed data."""
    try:
        logger.info("Connecting to database...")
        await connect()

        logger.info("Seeding food products...")
        await seed_food_products()

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(init_database())
