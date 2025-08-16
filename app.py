"""FastAPI application for a scalable WhatsApp bot."""

import logging
from typing import Dict, Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

from bot import config, database, session
from bot.services import nutrition, order
from bot.services.address_validation import close_address_service
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
    await close_address_service()
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
        message_type = message.get("type", "text")
        user_id = message["from"]

        # Handle different message types
        if message_type == "text":
            text = message["text"]["body"].strip()
        elif message_type == "location":
            # Handle location messages
            location = message["location"]
            return await handle_location_message(user_id, location, background_tasks)
        else:
            # Ignore other message types for now
            return {"status": "ignored"}

    except Exception:
        return {"status": "ignored"}

    session_data = await session.get(user_id)

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
    await send_message(
        user_id, "⚠️ *Session ended.* Please start again if you need anything else!"
    )
    return {"status": "ended"}


async def handle_location_message(
    user_id: str, location: Dict[str, Any], background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Handle location messages from users."""
    from bot.services.address_validation import get_address_service

    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if not latitude or not longitude:
        background_tasks.add_task(
            send_message,
            user_id,
            "❌ Could not read location data. Please try again or enter your address manually.",
            use_queue=True,
        )
        return {"status": "error"}

    # Get current session to understand context
    session_data = await session.get(user_id)
    if not session_data:
        background_tasks.add_task(
            send_message,
            user_id,
            "🔄 Please start a new conversation by sending any message.",
            use_queue=True,
        )
        return {"status": "no_session"}

    # Check if user is in an order flow and expecting address
    service = session_data.get("service")
    step = session_data.get("step")

    if service == "order" and step in [
        "await_address_choice",
        "await_address",
        "await_location",
    ]:
        # Process location for order delivery
        address_service = get_address_service()

        # Convert location to address
        try:
            address = await address_service.reverse_geocode(latitude, longitude)
            if not address:
                background_tasks.add_task(
                    send_message,
                    user_id,
                    "❌ Could not determine address from your location. Please enter your address manually.",
                    use_queue=True,
                )
                return {"status": "geocoding_failed"}

            # Store location data in session
            data = session_data.get("data", {})
            data["location"] = {
                "latitude": latitude,
                "longitude": longitude,
                "address": address,
            }

            await session.update(user_id, data=data, step="confirm_location_address")

            # Ask user to confirm the address
            background_tasks.add_task(
                send_message,
                user_id,
                f"📍 *Location received!*\n\n"
                f"Address: _{address}_\n\n"
                f"Is this correct for delivery? Reply:\n"
                f"• *yes* to confirm\n"
                f"• *no* to enter manually",
                use_queue=True,
            )

            return {"status": "location_processed"}

        except Exception as e:
            logger.error(f"Error processing location: {e}")
            background_tasks.add_task(
                send_message,
                user_id,
                "❌ Error processing location. Please try entering your address manually.",
                use_queue=True,
            )
            return {"status": "error"}
    else:
        # Location shared outside of order context
        background_tasks.add_task(
            send_message,
            user_id,
            "📍 Thank you for sharing your location! \n\n"
            "To place an order, please start by typing '1' for food ordering.",
            use_queue=True,
        )
        return {"status": "location_noted"}
