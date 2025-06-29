import httpx

from .config import get_settings

_client = httpx.AsyncClient(timeout=10)


async def close() -> None:
    await _client.aclose()


async def send_message(to: str, text: str) -> None:
    settings = get_settings()
    url = (
        f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    resp = await _client.post(url, json=payload, headers=headers)
    resp.raise_for_status()


async def send_typing_on(to: str) -> None:
    """Send typing indicator to a WhatsApp user."""
    settings = get_settings()
    url = (
        f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "typing_indicator": {"type": "text"},
        "status": "read",
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    resp = await _client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
