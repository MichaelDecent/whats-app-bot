"""Helpers for sending WhatsApp messages asynchronously."""

import asyncio
import contextlib
from typing import Tuple

import httpx

from .config import get_settings

_client = httpx.AsyncClient(timeout=10)

_send_queue: asyncio.Queue[Tuple[str, str]] | None = None
_worker_task: asyncio.Task[None] | None = None


def start_worker() -> None:
    """Start background worker for queued messages."""
    global _send_queue, _worker_task
    if _send_queue is None:
        _send_queue = asyncio.Queue()
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_process_queue())


async def _process_queue() -> None:
    assert _send_queue is not None
    while True:
        to, text = await _send_queue.get()
        try:
            await _send(to, text)
        finally:
            _send_queue.task_done()


async def _send(to: str, text: str) -> None:
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


async def send_message(to: str, text: str, *, use_queue: bool = False) -> None:
    """Send a WhatsApp message.

    If ``use_queue`` is ``True`` the message is placed on a background queue and
    processed by a worker task. Otherwise the message is sent immediately.
    """

    if use_queue:
        start_worker()
        assert _send_queue is not None
        await _send_queue.put((to, text))
    else:
        await _send(to, text)


async def close() -> None:
    if _worker_task:
        _worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _worker_task
    await _client.aclose()

