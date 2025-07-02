"""Enhanced food order service with AI-powered parsing."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from jinja2 import Template

from ..ai_client import create_chat_completion
from ..config import get_settings
from ..database import get_db
from ..models import Order, OrderItem
from ..whatsapp import send_message

CONFIRM_TEMPLATE = Template(
    "✅ *Order Summary:*\n"
    "{% for item in items %}🍽️ *{{item.quantity}}x* _{{item.name}}_ @ ₦{{item.unit_price}}\n{% endfor %}"
    "-----------------------------\n"
    "💰 *Total:* ₦{{total}}\n"
    "Please confirm (`yes`/`no`) or type `edit` to change."
)


# accepted yes/no variants
YES_WORDS = {"y", "yes", "sure", "ok"}
NO_WORDS = {"n", "no", "nah"}
# words indicating the user wants to change the order
CHANGE_WORDS = {"change", "edit"}


async def show_menu(user_id: str) -> None:
    """Send available food items to the user."""
    db = get_db()
    products = await db.food_products.find({"is_available": True}).to_list(length=None)
    if not products:
        await send_message(user_id, "😔 No food items available right now.")
        return

    lines = ["🍽️ *Here is our menu:*"]
    for idx, product in enumerate(products, start=1):
        lines.append(f"{idx}. _{product['name']}_ – ₦{product['price']}")
    lines.append(
        "\n📝 *Type the item numbers and quantities.*\n\n"
        "\nType `cancel` anytime to cancel. During confirmation, reply `edit` to modify items."
    )
    await send_message(user_id, "\n".join(lines))


def _extract_items_regex(
    text: str, products: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Simple regex based parser as a fallback."""

    pattern = re.compile(r"(\d+)x?\s*([A-Za-z ]+)", re.IGNORECASE)
    items: List[Dict[str, Any]] = []
    for qty, name in pattern.findall(text):
        qty = int(qty)
        name = name.strip().lower()
        matched = None
        for idx, p in enumerate(products):
            if (
                name in p["name"].lower()
                or name == p["name"].split()[-1].lower()
                or name == str(idx + 1)
            ):
                matched = p["name"]
                break
        if matched:
            items.append({"product": matched, "quantity": qty})
    return items


async def _parse_items(text: str) -> List[Dict[str, Any]]:
    """Use OpenAI to parse free-text order into structured items."""
    db = get_db()
    products = await db.food_products.find({"is_available": True}).to_list(length=None)

    names = ", ".join(p.get("name") for p in products)
    codes = ", ".join(f"{idx + 1}={p['name']}" for idx, p in enumerate(products))
    synonyms = ", ".join(
        f"{p['name'].split()[-1].lower()}={p['name']}" for p in products
    )
    prompt = (
        f"Available items: {names}\n"
        f"Codes: {codes}\n"
        f"Synonyms: {synonyms}\n"
        "Extract food items and their quantities from this message. "
        "Respond only with valid JSON in the form {'items': [{'product': '', 'quantity': 1}]}.\n"
        "Example: 'I'd like 2x pizza and one burger' -> {'items': [{'product': 'Margherita Pizza', 'quantity': 2}, {'product': 'Cheeseburger', 'quantity': 1}]}\n"
        "Example: '1 smoothie' -> {'items': [{'product': 'Fruit Smoothie', 'quantity': 1}]}\n"
        f"Message: {text}"
    )
    try:
        response = await create_chat_completion(
            model=get_settings().MODEL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            items = json.loads(content).get("items", [])
            if items:
                return items
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON from OpenAI: {content}")

        import re

        json_match = re.search(r"\{.*?\}", content, re.DOTALL)
        if json_match:
            try:
                json_content = json_match.group(0)
                parsed = json.loads(json_content)
                if parsed.get("items"):
                    return parsed["items"]
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON from OpenAI: {json_content}")

        # regex fallback on user text when OpenAI output unusable
        regex_items = _extract_items_regex(text, products)
        if regex_items:
            return regex_items
        logging.error(f"Could not parse order from text: {text}")
        return []

    except Exception as e:
        logging.exception(f"Failed to parse order items: {e}")
        return []


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    """Main order flow state machine."""

    settings = get_settings()
    db = get_db()
    data = session.get("data", {})
    step = session.get("step")

    command = text.strip().lower()
    if command == "cancel":
        await db.sessions.delete_one({"user_id": user_id})
        await send_message(user_id, "❌ *Order cancelled.*")
        return {"status": "cancelled"}
    if step == "await_confirm" and command == "edit":
        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"step": "await_items", "updated_at": datetime.utcnow()}},
        )
        await send_message(user_id, "✏️ Okay, please retype your order message.")
        return {"status": "awaiting"}

    if step == "await_items":
        parsed = await _parse_items(text)
        if not parsed:
            await send_message(
                user_id, "⚠️ Sorry, I couldn't understand your order. Please try again."
            )
            return {"status": "awaiting"}

        order_items: List[Dict[str, Any]] = []
        total = 0.0
        for item in parsed:
            name = item.get("product")
            qty = int(item.get("quantity", 0))
            if not name or qty <= 0:
                continue
            product = await db.food_products.find_one(
                {"name": {"$regex": f"^{name}$", "$options": "i"}}
            )
            if not product:
                await send_message(user_id, f"❌ Sorry, *{name}* is not available.")
                return {"status": "awaiting"}
            if product.get("stock", 0) < qty:
                await send_message(
                    user_id,
                    f"⚠️ Requested quantity not available. Only {product.get('stock', 0)} unit(s) of *{product['name']}* in stock.",
                )
                return {"status": "awaiting"}

            order_items.append(
                {
                    "product_id": str(product.get("_id")),
                    "name": product["name"],
                    "quantity": qty,
                    "unit_price": product["price"],
                }
            )
            total += product["price"] * qty

        if not order_items:
            await send_message(
                user_id,
                "⚠️ I couldn't find any valid items in your order. Please try again.",
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
        response = text.strip().lower()
        if response in YES_WORDS:
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
            )
            await send_message(user_id, "🏠 Please provide your *delivery address*.")
            return {"status": "awaiting"}
        if response in NO_WORDS or response in CHANGE_WORDS:
            await send_message(user_id, "✏️ Okay, please retype your order message.")
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_items", "updated_at": datetime.utcnow()}},
            )
            return {"status": "awaiting"}
        await send_message(
            user_id, "❓ Please reply with *yes* or *no*, or type 'change'."
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
        await send_message(
            user_id,
            f"📍 You entered: _{text}_\nIs this correct? (`yes`/`no`) or type `edit` to change.",
        )
        return {"status": "awaiting"}

    if step == "confirm_address":
        response = text.strip().lower()
        if response in YES_WORDS:
            try:
                raw_items = data.get("items", [])
                for i in raw_items:
                    if isinstance(i.get("product_id"), ObjectId):
                        i["product_id"] = str(i["product_id"])
                items = [OrderItem.model_validate(i) for i in raw_items]
                order_data = {
                    "user_id": user_id,
                    "items": items,
                    "total_price": data.get("total_price"),
                    "delivery_address": data.get("address"),
                    "created_at": datetime.utcnow(),
                }
                order_model = Order.model_validate(order_data)
            except Exception:
                await send_message(
                    user_id, "\u274c Invalid order data. Please start again."
                )
                await db.sessions.delete_one({"user_id": user_id})
                return {"status": "error"}

            updated: List[OrderItem] = []
            for item in items:
                result = await db.food_products.update_one(
                    {
                        "_id": ObjectId(item.product_id),
                        "stock": {"$gte": item.quantity},
                    },
                    {"$inc": {"stock": -item.quantity}},
                )
                if result.matched_count == 0:
                    for u in updated:
                        await db.food_products.update_one(
                            {"_id": ObjectId(u.product_id)},
                            {"$inc": {"stock": u.quantity}},
                        )
                    await send_message(
                        user_id,
                        f"\u2757 Requested quantity not available. Only insufficient stock for {item.name}",
                    )
                    return {"status": "awaiting"}
                updated.append(item)

            await db.orders.insert_one(order_model.model_dump(by_alias=True))
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
                f"✅ *Your order has been placed!*\n💰 *Total:* ₦{data['total_price']}",
            )
            eta_message = getattr(settings, "ORDER_ETA_MESSAGE", None)
            if eta_message:
                await send_message(user_id, f"⏳ {eta_message}")
            await db.sessions.delete_one({"user_id": user_id})
            return {"status": "ordered"}
        if response in NO_WORDS:
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
            )
            await send_message(user_id, "✏️ Please re-enter your *delivery address*.")
            return {"status": "awaiting"}
        await send_message(user_id, "❓ Please reply with *yes* or *no*.")
        return {"status": "awaiting"}

    await db.sessions.delete_one({"user_id": user_id})
    await send_message(user_id, "⚠️ Session ended due to an error. Please start again.")
    return {"status": "error"}
