"""Enhanced food order service with AI-powered parsing."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Template
from sqlalchemy import select

from ..ai_client import create_chat_completion
from ..config import get_settings
from ..database import get_db
from ..models import (
    Order,
    OrderItem,
    FoodProduct,
    AddressCollectionMethod,
    AddressValidationStatus,
)
from ..whatsapp import send_message
from .. import session as session_utils
from .address_validation import get_address_service

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
    async_session_maker = get_db()
    async with async_session_maker() as db_session:
        stmt = select(FoodProduct).where(FoodProduct.is_available.is_(True))
        result = await db_session.execute(stmt)
        products = result.scalars().all()

        if not products:
            await send_message(user_id, "😔 No food items available right now.")
            return

        lines = ["🍽️ *Here is our menu:*"]
        for idx, product in enumerate(products, start=1):
            lines.append(f"{idx}. _{product.name}_ – ₦{product.price}")
        lines.append(
            "\n📝 *Type the item numbers and quantities.*\n\n"
            "\nType `cancel` anytime to cancel. During confirmation, reply `edit` to modify items."
        )
        await send_message(user_id, "\n".join(lines))


def _extract_items_regex(
    text: str, products: List[FoodProduct]
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
                name in p.name.lower()
                or name == p.name.split()[-1].lower()
                or name == str(idx + 1)
            ):
                matched = p.name
                break
        if matched:
            items.append({"product": matched, "quantity": qty})
    return items


async def _parse_items(text: str) -> List[Dict[str, Any]]:
    """Use OpenAI to parse free-text order into structured items."""
    async_session_maker = get_db()
    async with async_session_maker() as db_session:
        stmt = select(FoodProduct).where(FoodProduct.is_available.is_(True))
        result = await db_session.execute(stmt)
        products = result.scalars().all()

        names = ", ".join(p.name for p in products)
        codes = ", ".join(f"{idx + 1}={p.name}" for idx, p in enumerate(products))
        synonyms = ", ".join(f"{p.name.split()[-1].lower()}={p.name}" for p in products)
    prompt = (
        f"Available items: {names}\n"
        f"Codes: {codes}\n"
        f"Synonyms: {synonyms}\n"
        "Extract food items and their quantities from this message. "
        "Respond only with valid JSON in the form {'items': [{'product': '', 'quantity': 1}]}.\n"
        "Example: 'I'd like 2x pizza and one burger' -> "
        "{'items': [{'product': 'Margherita Pizza', 'quantity': 2}, "
        "{'product': 'Cheeseburger', 'quantity': 1}]}\n"
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
    async_session_maker = get_db()
    data = session.get("data", {})
    step = session.get("step")

    command = text.strip().lower()
    if command == "cancel":
        await session_utils.delete(user_id)
        await send_message(user_id, "❌ *Order cancelled.*")
        return {"status": "cancelled"}
    if step == "await_confirm" and command == "edit":
        await session_utils.update(user_id, step="await_items")
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

        async with async_session_maker() as db_session:
            for item in parsed:
                name = item.get("product")
                qty = int(item.get("quantity", 0))
                if not name or qty <= 0:
                    continue

                # Case-insensitive search for product by name
                stmt = select(FoodProduct).where(FoodProduct.name.ilike(f"{name}"))
                result = await db_session.execute(stmt)
                product = result.scalar_one_or_none()

                if not product:
                    await send_message(user_id, f"❌ Sorry, *{name}* is not available.")
                    return {"status": "awaiting"}

                if product.stock < qty:
                    await send_message(
                        user_id,
                        f"⚠️ Requested quantity not available. "
                        f"Only {product.stock} unit(s) of *{product.name}* in stock.",
                    )
                    return {"status": "awaiting"}

                order_items.append(
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "quantity": qty,
                        "unit_price": product.price,
                    }
                )
                total += product.price * qty

        if not order_items:
            await send_message(
                user_id,
                "⚠️ I couldn't find any valid items in your order. Please try again.",
            )
            return {"status": "awaiting"}

        data.update({"items": order_items, "total_price": total})
        await session_utils.update(user_id, data=data, step="await_confirm")

        summary = CONFIRM_TEMPLATE.render(items=order_items, total=total)
        await send_message(user_id, summary)
        return {"status": "awaiting"}

    if step == "await_confirm":
        response = text.strip().lower()
        if response in YES_WORDS:
            # Offer address collection options
            await session_utils.update(user_id, step="await_address_choice")

            if settings.ENABLE_LOCATION_SHARING:
                await send_message(
                    user_id,
                    "📍 *How would you like to provide your delivery address?*\n\n"
                    "1️⃣ Share your location 📱\n"
                    "2️⃣ Type your address ✍️\n\n"
                    "Reply with *1* or *2*",
                )
            else:
                await send_message(
                    user_id, "🏠 Please provide your *delivery address*."
                )
                await session_utils.update(user_id, step="await_address")

            return {"status": "awaiting"}
        if response in NO_WORDS or response in CHANGE_WORDS:
            await send_message(user_id, "✏️ Okay, please retype your order message.")
            await session_utils.update(user_id, step="await_items")
            return {"status": "awaiting"}
        await send_message(
            user_id, "❓ Please reply with *yes* or *no*, or type 'change'."
        )
        return {"status": "awaiting"}

    if step == "await_address_choice":
        response = text.strip().lower()
        if response == "1":
            await session_utils.update(user_id, step="await_location")
            await send_message(
                user_id,
                "📍 *Please share your location*\n\n"
                "1. Tap the 📎 (attachment) button\n"
                "2. Select 'Location'\n"
                "3. Choose 'Current Location' or select on map\n"
                "4. Tap 'Send'\n\n"
                "Or type *back* to enter address manually.",
            )
            return {"status": "awaiting"}
        elif response == "2":
            await session_utils.update(user_id, step="await_address")
            await send_message(user_id, "🏠 Please type your *delivery address*:")
            return {"status": "awaiting"}
        else:
            await send_message(
                user_id,
                "❓ Please reply with *1* (share location) or *2* (type address).",
            )
            return {"status": "awaiting"}

    if step == "await_location":
        # Handle text responses while waiting for location
        if command == "back":
            await session_utils.update(user_id, step="await_address")
            await send_message(user_id, "🏠 Please type your *delivery address*:")
            return {"status": "awaiting"}
        else:
            await send_message(
                user_id,
                "📍 I'm waiting for your location. "
                "Please use the location sharing feature\n\n"
                "Or type *back* to enter your address manually.",
            )
            return {"status": "awaiting"}

    if step == "await_address":
        # Validate address if validation is enabled
        address_service = get_address_service()
        validation_result = await address_service.validate_address(
            text, settings.DEFAULT_COUNTRY_CODE
        )

        data["address"] = text
        data["address_collection_method"] = AddressCollectionMethod.text.value
        data["address_validation"] = {
            "is_valid": validation_result.is_valid,
            "formatted_address": validation_result.formatted_address,
            "confidence_score": validation_result.confidence_score,
        }

        await session_utils.update(user_id, data=data, step="confirm_address")

        # Show validation results to user
        if validation_result.is_valid and validation_result.formatted_address != text:
            await send_message(
                user_id,
                f"📍 *Address verified and formatted:*\n\n"
                f"_{validation_result.formatted_address}_\n\n"
                f"Is this correct? Reply *yes* to confirm or *no* to try again.",
            )
        else:
            await send_message(
                user_id,
                f"📍 You entered: _{text}_\n\n"
                f"Is this correct? Reply *yes* to confirm or *no* to try again.",
            )

        return {"status": "awaiting"}

    if step == "confirm_location_address":
        # Handle location address confirmation
        response = text.strip().lower()
        if response in YES_WORDS:
            # Use the location-based address
            location_data = data.get("location", {})
            data["address"] = location_data.get("address", "")
            data["latitude"] = location_data.get("latitude")
            data["longitude"] = location_data.get("longitude")
            data["address_collection_method"] = AddressCollectionMethod.location.value
            data["address_validation"] = {
                "is_valid": True,
                "formatted_address": location_data.get("address", ""),
                "confidence_score": 0.9,  # High confidence for GPS location
            }

            await session_utils.update(user_id, data=data, step="confirm_address")
            await send_message(
                user_id,
                f"✅ *Using your location for delivery*\n\n"
                f"📍 {location_data.get('address', '')}\n\n"
                f"Final confirmation - is this correct? "
                f"Reply *yes* to place order or *no* to change.",
            )
            return {"status": "awaiting"}
        elif response in NO_WORDS:
            await session_utils.update(user_id, step="await_address")
            await send_message(user_id, "🏠 Please type your *delivery address*:")
            return {"status": "awaiting"}
        else:
            await send_message(user_id, "❓ Please reply with *yes* or *no*.")
            return {"status": "awaiting"}

    if step == "confirm_address":
        response = text.strip().lower()
        if response in YES_WORDS:
            try:
                raw_items = data.get("items", [])
                # Create the order and order items in the database
                async with async_session_maker() as db_session:
                    # Create the order first
                    # Get address validation data
                    address_validation = data.get("address_validation", {})

                    order = Order(
                        user_id=user_id,
                        total_price=data.get("total_price"),
                        delivery_address=data.get("address"),
                        latitude=data.get("latitude"),
                        longitude=data.get("longitude"),
                        address_collection_method=data.get(
                            "address_collection_method",
                            AddressCollectionMethod.text.value,
                        ),
                        address_validation_status=(
                            AddressValidationStatus.valid.value
                            if address_validation.get("is_valid")
                            else AddressValidationStatus.not_validated.value
                        ),
                        validated_address=address_validation.get("formatted_address"),
                        address_validation_metadata=address_validation,
                        created_at=datetime.utcnow(),
                    )
                    db_session.add(order)
                    await db_session.flush()  # Get the order.id

                    # Validate items and check stock
                    updated_items = []
                    for item_data in raw_items:
                        product_id = item_data["product_id"]
                        quantity = item_data["quantity"]

                        # Check and update stock
                        product_stmt = select(FoodProduct).where(
                            FoodProduct.id == product_id
                        )
                        product_result = await db_session.execute(product_stmt)
                        product = product_result.scalar_one_or_none()

                        if not product or product.stock < quantity:
                            # Rollback any changes
                            await db_session.rollback()
                            if not product:
                                await send_message(
                                    user_id,
                                    "\u274c Product not found. Please start again.",
                                )
                            else:
                                await send_message(
                                    user_id,
                                    f"\u2757 Insufficient stock for {product.name}. Only {product.stock} available.",
                                )
                            return {"status": "awaiting"}

                        # Update stock
                        product.stock -= quantity

                        # Create order item
                        order_item = OrderItem(
                            order_id=order.id,
                            product_id=product_id,
                            name=item_data["name"],
                            quantity=quantity,
                            unit_price=item_data["unit_price"],
                        )
                        db_session.add(order_item)
                        updated_items.append(order_item)

                    await db_session.commit()

            except Exception as e:
                logging.exception(f"Error creating order: {e}")
                await send_message(
                    user_id, "\u274c Error creating order. Please try again."
                )
                await session_utils.delete(user_id)
                return {"status": "error"}

            # Send notifications
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
            await session_utils.delete(user_id)
            return {"status": "ordered"}
        if response in NO_WORDS:
            await session_utils.update(user_id, step="await_address")
            await send_message(user_id, "✏️ Please re-enter your *delivery address*.")
            return {"status": "awaiting"}
        await send_message(user_id, "❓ Please reply with *yes* or *no*.")
        return {"status": "awaiting"}

    await session_utils.delete(user_id)
    await send_message(user_id, "⚠️ Session ended due to an error. Please start again.")
    return {"status": "error"}
