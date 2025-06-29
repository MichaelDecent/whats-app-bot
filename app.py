"""FastAPI application for a scalable WhatsApp bot."""

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from bot import config, database, session
from bot.services import nutrition, order
from bot.whatsapp import close as whatsapp_close, send_message

app = FastAPI()
settings = config.get_settings()


@app.on_event("startup")
async def startup() -> None:
    await database.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    await whatsapp_close()
    await database.close()


@app.get("/")
async def read_root() -> Dict[str, str]:
    return {"message": "WhatsApp Bot running"}


@app.get("/whatsapp")
async def verify_webhook(request: Request) -> PlainTextResponse:
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> Dict[str, str]:
    data = await request.json()
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        text = message["text"]["body"].strip()
        user_id = message["from"]
    except Exception:
        return {"status": "ignored"}

    session_data = await session.get(user_id)
    if not session_data:
        await session.create(user_id, step="await_choice")
        welcome = (
            "Welcome! Please choose a service:\n"
            "1️⃣ Place a food order\n"
            "2️⃣ Chat with AI Nutritionist"
        )
        await send_message(user_id, welcome)
        return {"status": "new"}

    if session_data.get("step") == "await_choice":
        if text.startswith("1"):
            await session.update(user_id, service="order", step="await_items", data={})
            await send_message(
                user_id,
                "Please list the food items you'd like to order (e.g., Burger 2, Salad 1).",
            )
            return {"status": "awaiting"}
        if text.startswith("2"):
            history = [
                {
                    "role": "system",
                    "content": "You are a certified, friendly nutritionist. Give concise advice.",
                }
            ]
            await session.update(user_id, service="nutrition", step="nutrition", history=history)
            await send_message(user_id, "Great! Tell me about your dietary goals or preferences.")
            return {"status": "awaiting"}
        await send_message(user_id, "Please reply with 1 or 2.")
        return {"status": "awaiting"}

    if session_data.get("service") == "order":
        return await order.handle(user_id, text, session_data)

    if session_data.get("service") == "nutrition":
        return await nutrition.handle(user_id, text, session_data)

    await session.delete(user_id)
    return {"status": "ended"}
