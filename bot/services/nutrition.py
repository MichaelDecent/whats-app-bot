from datetime import datetime
from typing import Any, Dict, List

from openai import AsyncOpenAI

from ..config import get_settings
from ..database import get_db
from ..whatsapp import send_message

_client: AsyncOpenAI | None = None


def _openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    return _client


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    db = get_db()
    history: List[Dict[str, str]] = session.get("history", [])
    history.append({"role": "user", "content": text})
    try:
        response = await _openai().chat.completions.create(
            model="gpt-4o", messages=history, temperature=0.7
        )
        reply = response.choices[0].message.content
    except Exception:
        reply = "Sorry, I'm having trouble fetching advice right now."
    history.append({"role": "assistant", "content": reply})
    await db.sessions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "history": history,
                "step": "nutrition",
                "updated_at": datetime.utcnow(),
            }
        },
    )
    await send_message(user_id, reply)
    if text.strip().lower() in {"bye", "exit", "cancel"}:
        await db.sessions.delete_one({"user_id": user_id})
    return {"status": "sent"}
