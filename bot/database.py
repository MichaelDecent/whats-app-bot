from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect() -> None:
    """Create MongoDB client and ensure indexes."""
    global client, db
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB_NAME]
    # TTL index ensures MongoDB automatically removes sessions after
    # ``SESSION_TTL_SECONDS`` since the last ``updated_at`` timestamp.
    await db.sessions.create_index(
        "updated_at", expireAfterSeconds=settings.SESSION_TTL_SECONDS
    )


def get_db() -> AsyncIOMotorDatabase:
    assert db is not None, "Database not initialized"
    return db


async def close() -> None:
    if client:
        client.close()
