#!/usr/bin/env python3
"""Database migration script for new address features."""

import asyncio
import logging

from bot.database import connect, close
from bot.models import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_database() -> None:
    """Apply database migrations for new address features."""
    try:
        logger.info("Connecting to database...")
        await connect()

        logger.info("Creating new tables...")
        # The new tables will be created automatically when the engine connects
        # because we use create_all() in the database.py connect() function

        logger.info("Database migration completed successfully!")

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(migrate_database())
