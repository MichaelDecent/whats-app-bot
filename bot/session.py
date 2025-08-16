"""Utility functions to manage chat sessions with SQLAlchemy."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import select, delete as sql_delete

from .database import get_db
from .models import UserSession


async def get(user_id: str) -> Dict[str, Any] | None:
    """Get user session by user_id."""
    async_session_maker = get_db()
    async with async_session_maker() as session:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if user_session:
            return {
                "user_id": user_session.user_id,
                "service": user_session.service,
                "step": user_session.step,
                "data": user_session.data,
                "history": user_session.history,
                "created_at": user_session.created_at,
                "updated_at": user_session.updated_at,
            }
        return None


async def create(user_id: str, step: str, service: str | None = None) -> Dict[str, Any]:
    """Create or replace user session."""
    async_session_maker = get_db()
    async with async_session_maker() as session:
        # Check if session exists
        existing_stmt = select(UserSession).where(UserSession.user_id == user_id)
        result = await session.execute(existing_stmt)
        existing_session = result.scalar_one_or_none()

        session_data = {
            "user_id": user_id,
            "service": service or "order",
            "step": step,
            "data": {},
            "history": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if existing_session:
            # Update existing session
            existing_session.service = session_data["service"]
            existing_session.step = session_data["step"]
            existing_session.data = session_data["data"]
            existing_session.history = session_data["history"]
            existing_session.updated_at = session_data["updated_at"]
        else:
            # Create new session
            new_session = UserSession(**session_data)
            session.add(new_session)

        await session.commit()
        return session_data


async def update(user_id: str, **fields: Any) -> None:
    """Update user session fields."""
    async_session_maker = get_db()
    async with async_session_maker() as session:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        result = await session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if user_session:
            fields["updated_at"] = datetime.utcnow()
            for key, value in fields.items():
                if hasattr(user_session, key):
                    setattr(user_session, key, value)
            await session.commit()


async def delete(user_id: str) -> None:
    """Delete user session."""
    async_session_maker = get_db()
    async with async_session_maker() as session:
        stmt = sql_delete(UserSession).where(UserSession.user_id == user_id)
        await session.execute(stmt)
        await session.commit()
