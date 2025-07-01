# WhatsApp Bot

This project provides a small demo WhatsApp bot. Users can place food orders or chat with an AI powered nutritionist.

## Configuration

Settings are loaded from environment variables defined in `.env`. Important variables include:

- `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` – credentials for sending messages.
- `MONGO_URL` and related Mongo variables – database configuration.
- `ORDER_ETA_MESSAGE` – text sent after an order is confirmed. Set this to provide an ETA or tracking link for deliveries.

## Behavior

When a user places an order, the bot confirms the items and asks for the delivery address. After the address is confirmed and the order is saved, the bot sends:

1. "Your order has been placed!" along with the total amount.
2. A second message using the `ORDER_ETA_MESSAGE` template which can contain an estimated delivery time or tracking URL.

Run `uvicorn app:app` to start the API.
