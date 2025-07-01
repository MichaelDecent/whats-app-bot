"""Centralized AI services for the WhatsApp bot."""

import asyncio
import logging
from openai import AsyncOpenAI

from .config import get_settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create a singleton OpenAI client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.API_KEY)
    return _client


async def create_chat_completion(*args, retries: int = 3, backoff: float = 1.0, **kwargs):
    """Wrapper around OpenAI chat completion with retries."""
    client = get_openai_client()
    for attempt in range(1, retries + 1):
        try:
            return await client.chat.completions.create(*args, **kwargs)
        except Exception as exc:
            logging.exception("OpenAI attempt %s failed", attempt)
            if attempt == retries:
                logging.exception("OpenAI request failed after %s attempts", retries)
                raise
            await asyncio.sleep(backoff * 2 ** (attempt - 1))
