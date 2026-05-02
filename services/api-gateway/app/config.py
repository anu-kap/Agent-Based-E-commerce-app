from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    catalog_service_url: str = "http://catalog-service:8001"
    payment_service_url: str = "http://payment-service:8002"
    order_service_url: str = "http://order-service:8003"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = ""
    shopify_store_domain: str = ""
    port: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
