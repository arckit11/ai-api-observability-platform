"""Runtime configuration loaded from env vars via pydantic-settings.

Values documented in the root ``.env.example`` map 1:1 into this class.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Service
    service_name: str = "ml-service"
    port: int = Field(8000, alias="PORT_ML")

    # Model artifacts on disk (joblib)
    model_dir: Path = Field(Path("/app/models"), alias="ML_MODEL_DIR")

    # Analytics Service (for training data retrieval + inference features)
    analytics_base_url: str = Field(
        "http://analytics-service:8084", alias="ML_ANALYTICS_BASE_URL"
    )

    # Kafka
    kafka_bootstrap: str = Field("kafka:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    topic_predictions: str = Field("predictions", alias="KAFKA_TOPIC_PREDICTIONS")
    topic_service_health: str = Field(
        "service-health", alias="KAFKA_TOPIC_SERVICE_HEALTH"
    )

    # Retraining
    training_cron: str = Field("0 3 * * *", alias="ML_TRAINING_SCHEDULE_CRON")


settings = Settings()
