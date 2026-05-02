from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    shopify_store_domain: str = ""
    seed_catalog_path: str = "/app/data/seed_catalog.json"
    port: int = 8002

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
