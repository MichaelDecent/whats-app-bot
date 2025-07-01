import asyncio
import logging
import httpx

from .config import get_settings

_client = httpx.AsyncClient(timeout=10)


async def close() -> None:
    await _client.aclose()


async def send_message(to: str, text: str, *, retries: int = 3, backoff: float = 1.0) -> None:
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
    for attempt in range(1, retries + 1):
        try:
            resp = await _client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return
        except httpx.HTTPError as exc:
            logging.exception("send_message attempt %s failed", attempt)
            if attempt == retries:
                logging.exception("send_message failed after %s attempts", retries)
                raise
            await asyncio.sleep(backoff * 2 ** (attempt - 1))
