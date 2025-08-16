from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str | None = None
    MODEL_MODEL: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    DELIVERY_PHONE_NUMBER: str | None = None
    DATABASE_URL: str = (
        "sqlite+aiosqlite:///./whatsapp_bot.db"  # Default to SQLite for dev
    )
    SESSION_TTL_SECONDS: int = 3600  # Default 1 hour
    ORDER_ETA_MESSAGE: str = "Your order is on its way!"

    # Address validation settings
    GOOGLE_PLACES_API_KEY: str | None = None
    ENABLE_ADDRESS_VALIDATION: bool = False
    DEFAULT_COUNTRY_CODE: str = "NG"  # Nigeria by default
    ENABLE_LOCATION_SHARING: bool = True

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
