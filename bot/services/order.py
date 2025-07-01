"""Enhanced food order service with AI-powered parsing."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Template
from ..ai_client import get_openai_client
from ..config import get_settings
from ..database import get_db
from ..whatsapp import send_message

CONFIRM_TEMPLATE = Template(
    "✅ Got your order:\n"
    "{% for item in items %}- {{item.quantity}}x {{item.name}} @ ₦{{item.unit_price}}\n{% endfor %}"
    "Total: ₦{{total}}\n"
    "Please confirm (yes/no)"
)


# accepted yes/no variants
YES_WORDS = {"y", "yes", "sure", "ok"}
NO_WORDS = {"n", "no", "nah"}


async def show_menu(user_id: str) -> None:
    """Send available food items to the user."""
    db = get_db()
    products = await db.food_products.find({"is_available": True}).to_list(length=None)
    if not products:
        await send_message(user_id, "No food items available right now.")
        return

    lines = ["Here is our menu:"]
    for idx, product in enumerate(products, start=1):
        lines.append(f"{idx}. {product['name']} – ₦{product['price']}")
    lines.append(
        "\nType the item numbers and quantities, or type `cancel` anytime."
    )
    await send_message(user_id, "\n".join(lines))


async def _parse_items(text: str) -> List[Dict[str, Any]]:
    """Use OpenAI to parse free-text order into structured items."""
    db = get_db()
    products = await db.food_products.find({"is_available": True}).to_list(length=None)

    # try to parse numeric codes first, e.g. "1x2 3"
    numeric_items: List[Dict[str, Any]] = []
    for code, qty in re.findall(r"(\d+)(?:\s*[xX]\s*(\d+))?", text):
        idx = int(code) - 1
        if 0 <= idx < len(products):
            quantity = int(qty) if qty else 1
            if quantity > 0:
                numeric_items.append({"product": products[idx]["name"], "quantity": quantity})

    if numeric_items:
        return numeric_items

    names = ", ".join(p.get("name") for p in products)
    prompt = (
        f"Available items: {names}\n"
        "Extract food items and their quantities from this message. "
        "Respond only with valid JSON in the form {'items': [{'product': '', 'quantity': 1}]}.\n"
        f"Message: {text}"
    )
    try:
        response = await get_openai_client().chat.completions.create(
            model=get_settings().MODEL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            return json.loads(content).get("items", [])
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON from OpenAI: {content}")

            json_match = re.search(r"\{.*?\}", content, re.DOTALL)
            if json_match:
                try:
                    json_content = json_match.group(0)
                    parsed = json.loads(json_content)
                    return parsed.get("items", [])
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse JSON from OpenAI: {json_content}")
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
            product = await db.food_products.find_one(
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
        response = text.strip().lower()
        if response in YES_WORDS:
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
            )
            await send_message(user_id, "Please provide your delivery address.")
            return {"status": "awaiting"}
        if response in NO_WORDS:
            await send_message(user_id, "Okay, please retype your order message.")
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_items", "updated_at": datetime.utcnow()}},
            )
            return {"status": "awaiting"}
        await send_message(user_id, "Please reply with yes or no.")
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
        response = text.strip().lower()
        if response in YES_WORDS:
            order = {
                "user_id": user_id,
                "items": data.get("items"),
                "total_price": data.get("total_price"),
                "address": data.get("address"),
                "created_at": datetime.utcnow(),
            }
            await db.orders.insert_one(order)
            for item in data.get("items", []):
                await db.food_products.update_one(
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

        if response in NO_WORDS:
            await db.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"step": "await_address", "updated_at": datetime.utcnow()}},
            )
            await send_message(user_id, "Please re-enter your delivery address.")
            return {"status": "awaiting"}
        await send_message(user_id, "Please reply with yes or no.")
        return {"status": "awaiting"}

    await db.sessions.delete_one({"user_id": user_id})
    return {"status": "error"}
