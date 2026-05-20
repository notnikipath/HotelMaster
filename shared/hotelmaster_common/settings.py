from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "hotelmaster-service"
    service_port: int = 8500
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://hotelmaster:hotelmaster@postgres:5432/hotelmaster"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    jwt_secret: str = "hotelmaster-dev-secret"
    encryption_key: str = "hotelmaster-dev-encryption-key"

    booking_target_seconds: float = 3.0
    forecast_target_mape: float = 10.0
    max_rooms_supported: int = 5000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
