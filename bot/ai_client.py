"""Centralized AI services for the WhatsApp bot."""

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
