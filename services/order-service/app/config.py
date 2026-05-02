from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    sqs_order_events_url: str = ""
    aws_region: str = "us-east-1"
    kestra_url: str = "http://localhost:8080"
    kestra_namespace: str = "demo.commerce"
    kestra_flow_id: str = "chat-commerce-order-fulfillment"
    kestra_radar_flow_id: str = "campus-demand-radar"
    port: int = 8003

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
