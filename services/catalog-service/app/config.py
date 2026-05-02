from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    shopify_store_domain: str = ""
    redis_url: str = "redis://localhost:6379/0"
    catalog_cache_ttl_seconds: int = 3600
    seed_catalog_path: str = "/app/data/seed_catalog.json"
    port: int = 8001

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
