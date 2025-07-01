"""FastAPI application for a scalable WhatsApp bot."""

from typing import Dict

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import PlainTextResponse

from bot import config, database, session
from bot.services import nutrition, order
from bot.whatsapp import close as whatsapp_close
from bot.whatsapp import send_message, start_worker
from seed import seed_food_products

app = FastAPI()
settings = config.get_settings()


@app.on_event("startup")
async def startup() -> None:
    await database.connect()
    await seed_food_products()
    start_worker()


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
async def whatsapp_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    data = await request.json()
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        text = message["text"]["body"].strip()
        user_id = message["from"]
    except Exception:
        return {"status": "ignored"}

    session_data = await session.get(user_id)
        # ...existing code...
    
        if not session_data:
            await session.create(user_id, step="await_choice")
            welcome = (
                "👋 *Welcome!*\n"
                "Please choose a service:\n"
                "1️⃣ *Order a Healthy Meal*\n"
                "2️⃣ *Chat with AI Nutritionist*"
            )
            background_tasks.add_task(send_message, user_id, welcome, use_queue=True)
            return {"status": "new"}
    
        if session_data.get("step") == "await_choice":
            if text.startswith("1"):
                await session.update(user_id, service="order", step="await_items", data={})
                await order.show_menu(user_id)
                return {"status": "awaiting"}
            if text.startswith("2"):
                history = [
                    {
                        "role": "system",
                        "content": "You are a certified, friendly nutritionist. Give concise advice.",
                    }
                ]
                await session.update(
                    user_id, service="nutrition", step="nutrition", history=history
                )
                background_tasks.add_task(
                    send_message,
                    user_id,
                    "🤖 *Great!* Tell me about your _dietary goals_ or _preferences_.",
                    use_queue=True,
                )
                return {"status": "awaiting"}
            background_tasks.add_task(
                send_message, user_id, "❓ *Please reply with* 1️⃣ *or* 2️⃣.", use_queue=True
            )
            return {"status": "awaiting"}
    
        if session_data.get("service") == "order":
            return await order.handle(user_id, text, session_data)
    
        if session_data.get("service") == "nutrition":
            return await nutrition.handle(user_id, text, session_data)
    
        await session.delete(user_id)
        await send_message(user_id, "⚠️ *Session ended.* Please start again if you need anything else!")
        return {"status": "ended"}