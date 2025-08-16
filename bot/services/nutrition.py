from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select, delete as sql_delete

from ..ai_client import create_chat_completion
from ..config import get_settings
from ..database import get_db
from ..models import UserSession
from ..whatsapp import send_message


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    async_session_maker = get_db()
    history: List[Dict[str, str]] = session.get("history", [])
    history.append({"role": "user", "content": text})

    try:
        response = await create_chat_completion(
            model=get_settings().MODEL_MODEL, messages=history, temperature=0.7
        )
        reply = response.choices[0].message.content
    except Exception:
        reply = "Sorry, I'm having trouble fetching advice right now."

    history.append({"role": "assistant", "content": reply})

    # Update session with new history
    async with async_session_maker() as db_session:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        result = await db_session.execute(stmt)
        user_session = result.scalar_one_or_none()

        if user_session:
            user_session.history = history
            user_session.step = "nutrition"
            user_session.updated_at = datetime.utcnow()
            await db_session.commit()

    await send_message(user_id, reply)

    if text.strip().lower() in {"bye", "exit", "cancel"}:
        async with async_session_maker() as db_session:
            stmt = sql_delete(UserSession).where(UserSession.user_id == user_id)
            await db_session.execute(stmt)
            await db_session.commit()

    return {"status": "sent"}
