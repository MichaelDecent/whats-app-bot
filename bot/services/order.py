"""Enhanced food order service."""

from datetime import datetime
from typing import Any, Dict

from ..config import get_settings
from ..database import get_db
from ..whatsapp import send_message, send_typing_on


async def show_menu(user_id: str) -> None:
    """Send available food items to the user."""
    db = get_db()
    await send_typing_on(user_id)
    products = await db.products.find().to_list(length=None)
    if not products:
        await send_message(user_id, "No food items available right now.")
        return

    lines = ["Here is our menu:"]
    for product in products:
        lines.append(f"- {product['name']} (${product['price']})")
    lines.append("\nPlease enter your order as '<product> <quantity>'.")
    await send_message(user_id, "\n".join(lines))


async def handle(user_id: str, text: str, session: Dict[str, Any]) -> Dict[str, str]:
    """Main order flow state machine."""

    settings = get_settings()
    db = get_db()
    data = session.get("data", {})
    step = session.get("step")

    if step == "await_items":
        # This state is triggered after the menu is shown.
        try:
            name, qty_str = text.rsplit(" ", 1)
            quantity = int(qty_str)
        except Exception:
            await send_message(
                user_id,
                "Please provide the product name followed by quantity, e.g., Burger 2.",
            )
            return {"status": "awaiting"}

        if quantity <= 0:
            await send_message(user_id, "Quantity must be a positive number.")
            return {"status": "awaiting"}

        product = await db.products.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
        if not product:
            await send_message(user_id, "Sorry, that product is not available.")
            return {"status": "awaiting"}

        if product.get("stock", 0) < quantity:
            await send_message(
                user_id,
                f"\u2757 Requested quantity not available. Only {product.get('stock', 0)} unit(s) of {product['name']} in stock.",
            )
            return {"status": "awaiting"}

        data.update({
            "product": product["name"],
            "quantity": quantity,
            "unit_price": product["price"],
            "total": product["price"] * quantity,
        })

        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"data": data, "step": "await_confirm", "updated_at": datetime.utcnow()}},
        )

        summary = f"You ordered {data['quantity']} x {data['product']} for ${data['total']}.\nConfirm? (yes/no)"
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
        await send_message(user_id, "Let's try again. Which product and quantity?")
        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"step": "await_items", "updated_at": datetime.utcnow()}},
        )
        return {"status": "awaiting"}

    if step == "await_address":
        data["address"] = text
        await db.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"data": data, "step": "confirm_address", "updated_at": datetime.utcnow()}},
        )
        await send_message(user_id, f"You entered: {text}\nIs this correct? (yes/no)")
        return {"status": "awaiting"}

    if step == "confirm_address":
        if text.strip().lower().startswith("y"):
            order = {
                "user_id": user_id,
                "product": data.get("product"),
                "quantity": data.get("quantity"),
                "unit_price": data.get("unit_price"),
                "total": data.get("total"),
                "address": data.get("address"),
                "created_at": datetime.utcnow(),
            }
            await send_typing_on(user_id)
            await db.orders.insert_one(order)
            await db.products.update_one(
                {"name": data["product"]},
                {"$inc": {"stock": -data["quantity"]}},
            )
            delivery = settings.DELIVERY_PHONE_NUMBER
            if delivery:
                deliver_msg = (
                    f"New order from {user_id}:\n"
                    f"{data['quantity']} x {data['product']} (${data['total']})\n"
                    f"Address: {data['address']}"
                )
                await send_message(delivery, deliver_msg)
            await send_message(
                user_id,
                f"\u2705 Your order has been placed! {data['quantity']} x {data['product']} for ${data['total']}.",
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

