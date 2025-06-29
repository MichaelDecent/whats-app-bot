"""Enhanced food order service with AI-powered parsing."""

import json
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Template
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


CONFIRM_TEMPLATE = Template(
    "\u2705 Got your order:\n"
    "{% for item in items %}- {{item.quantity}}x {{item.name}} @ \u20a6{{item.unit_price}}\n{% endfor %}"
    "Total: \u20a6{{total}}\n"
    "Please confirm (yes/no)"
)


async def show_menu(user_id: str) -> None:
    """Send available food items to the user."""
    db = get_db()
    products = await db.food_products.find().to_list(length=None)
    if not products:
        await send_message(user_id, "No food items available right now.")
        return

    lines = ["Here is our menu:"]
    for product in products:
        lines.append(f"- {product['name']} (${product['price']})")
    lines.append(
        "\nPlease type your order, e.g. 'I want 2 beef burgers and a bottle of water'."
    )
    await send_message(user_id, "\n".join(lines))


async def _parse_items(text: str) -> List[Dict[str, Any]]:
    """Use OpenAI to parse free-text order into structured items."""
    prompt = (
        "Extract food items and their quantities from this message. "
        "Respond only with valid JSON in the form {'items': [{'product': '', 'quantity': 1}]}.\n"
        f"Message: {text}"
    )
    try:
        response = await _openai().chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except Exception:
        return []


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    """Main order flow state machine."""

    settings = get_settings()
    db = get_db()
    data = session.get("data", {})
    step = session.get("step")

    if step == "await_items":
        parsed = await _parse_items(text)
        if not parsed:
            await send_message(
                user_id, "Sorry, I couldn't understand your order. Please try again."
            )
            return {"status": "awaiting"}

        order_items: List[Dict[str, Any]] = []
        total = 0.0
        for item in parsed:
            name = item.get("product")
            qty = int(item.get("quantity", 0))
            if not name or qty <= 0:
                continue
            product = await db.products.find_one(
                {"name": {"$regex": f"^{name}$", "$options": "i"}}
            )
            if not product:
                await send_message(user_id, f"Sorry, {name} is not available.")
                return {"status": "awaiting"}
            if product.get("stock", 0) < qty:
                await send_message(
                    user_id,
                    f"\u2757 Requested quantity not available. Only {product.get('stock', 0)} unit(s) of {product['name']} in stock.",
                )
                return {"status": "awaiting"}

            order_items.append(
                {
                    "product_id": product.get("_id"),
                    "name": product["name"],
                    "quantity": qty,
                    "unit_price": product["price"],
                }
            )
            total += product["price"] * qty

        if not order_items:
            await send_message(
                user_id,
                "I couldn't find any valid items in your order. Please try again.",
            )
            return {"status": "awaiting"}

        data.update({"items": order_items, "total_price": total})

        await db.sessions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "data": data,
                    "step": "await_confirm",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        summary = CONFIRM_TEMPLATE.render(items=order_items, total=total)
        await send_message(user_id, summary)
        return {"status": "awaiting"}

    if step == "await_confirm":
        if text.strip().lower().startswith("y"):
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
            )
            await send_message(user_id, "Please provide your delivery address.")
            return {"status": "awaiting"}
        await send_message(user_id, "Okay, please retype your order message.")
        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"step": "await_items", "updated_at": datetime.utcnow()}},
        )
        return {"status": "awaiting"}

    if step == "await_address":
        data["address"] = text
        await db.sessions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "data": data,
                    "step": "confirm_address",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        await send_message(user_id, f"You entered: {text}\nIs this correct? (yes/no)")
        return {"status": "awaiting"}

    if step == "confirm_address":
        if text.strip().lower().startswith("y"):
            order = {
                "user_id": user_id,
                "items": data.get("items"),
                "total_price": data.get("total_price"),
                "address": data.get("address"),
                "created_at": datetime.utcnow(),
            }
            await db.orders.insert_one(order)
            for item in data.get("items", []):
                await db.products.update_one(
                    {"_id": item["product_id"]},
                    {"$inc": {"stock": -item["quantity"]}},
                )
            delivery = settings.DELIVERY_PHONE_NUMBER
            if delivery:
                lines = [f"New order from {user_id}:"]
                for i in data.get("items", []):
                    lines.append(
                        f"{i['quantity']} x {i['name']} (@ \u20a6{i['unit_price']})"
                    )
                lines.append(f"Address: {data['address']}")
                await send_message(delivery, "\n".join(lines))
            await send_message(
                user_id,
                f"\u2705 Your order has been placed! Total: \u20a6{data['total_price']}",
            )
            await db.sessions.delete_one({"user_id": user_id})
            return {"status": "ordered"}

        # user said no -> re-enter address
        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
        )
        await send_message(user_id, "Please re-enter your delivery address.")
        return {"status": "awaiting"}

    await db.sessions.delete_one({"user_id": user_id})
    return {"status": "error"}
