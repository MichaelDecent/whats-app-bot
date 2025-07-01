from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str | None = None
    MODEL_MODEL: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    DELIVERY_PHONE_NUMBER: str | None = None
    MONGO_URL: str
    MONGO_DB_NAME: str
    MONGO_COLLECTION_NAME: str
    SESSION_TTL_SECONDS: int
    ORDER_ETA_MESSAGE: str = "Your order is on its way!"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
