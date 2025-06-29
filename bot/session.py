"""Utility functions to manage chat sessions in MongoDB."""

from datetime import datetime
from typing import Any, Dict

from .database import get_db


async def get(user_id: str) -> Dict[str, Any] | None:
    return await get_db().sessions.find_one({"user_id": user_id})


async def create(user_id: str, step: str, service: str | None = None) -> Dict[str, Any]:
    session = {
        "user_id": user_id,
        "service": service,
        "step": step,
        "data": {},
        "history": [],
        "updated_at": datetime.utcnow(),
    }
    await get_db().sessions.replace_one({"user_id": user_id}, session, upsert=True)
    return session


async def update(user_id: str, **fields: Any) -> None:
    fields["updated_at"] = datetime.utcnow()
    await get_db().sessions.update_one({"user_id": user_id}, {"$set": fields})


async def delete(user_id: str) -> None:
    await get_db().sessions.delete_one({"user_id": user_id})
