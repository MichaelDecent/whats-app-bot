from functools import lru_cache
from pydantic import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    DELIVERY_PHONE_NUMBER: str | None = None
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "whatsapp_bot"
    SESSION_TTL_SECONDS: int = 3600

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
