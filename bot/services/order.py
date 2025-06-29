from datetime import datetime
from typing import Any, Dict

from ..config import get_settings
from ..database import get_db
from ..whatsapp import send_message


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    settings = get_settings()
    db = get_db()
    data = session.get("data", {})
    step = session.get("step")

    if step == "await_items":
        data["items"] = text
        await db.sessions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "step": "await_address",
                    "data": data,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        await send_message(user_id, "Please provide your delivery address.")
        return {"status": "awaiting"}

    if step == "await_address":
        data["address"] = text
        await db.sessions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "step": "await_confirm",
                    "data": data,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        summary = f"You ordered: {data['items']}\nDeliver to: {data['address']}\nReply YES to confirm or NO to cancel."
        await send_message(user_id, summary)
        return {"status": "awaiting"}

    if step == "await_confirm":
        if text.strip().lower().startswith("y"):
            order = {
                "user_id": user_id,
                "items": data.get("items"),
                "address": data.get("address"),
                "created_at": datetime.utcnow(),
            }
            await db.orders.insert_one(order)
            await send_message(user_id, "Thank you! Your order has been placed.")
            delivery = settings.DELIVERY_PHONE_NUMBER
            if delivery:
                deliver_msg = f"New order from {user_id}:\nItems: {data['items']}\nAddress: {data['address']}"
                await send_message(delivery, deliver_msg)
            await db.sessions.delete_one({"user_id": user_id})
            return {"status": "ordered"}
        await send_message(user_id, "Order cancelled.")
        await db.sessions.delete_one({"user_id": user_id})
        return {"status": "cancelled"}

    await db.sessions.delete_one({"user_id": user_id})
    return {"status": "error"}
