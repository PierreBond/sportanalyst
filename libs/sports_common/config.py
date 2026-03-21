from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        validation_alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        validation_alias="DATABASE_URL_SYNC",
    )

    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )

    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000",
        validation_alias="MLFLOW_TRACKING_URI",
    )

    sportsdataio_api_key: str = Field(
        default="",
        validation_alias="SPORTSDATAIO_API_KEY",
    )
    api_sports_key: str = Field(
        default="",
        validation_alias="API_SPORTS_KEY",
    )
    mysportsfeeds_api_key: str = Field(
        default="",
        validation_alias="MYSPORTSFEEDS_API_KEY",
    )
    sportmonks_api_key: str = Field(
        default="",
        validation_alias="SPORTMONKS_API_KEY",
    )

    oddsjam_api_key: str = Field(
        default="",
        validation_alias="ODDSJAM_API_KEY",
    )
    opticodds_api_key: str = Field(
        default="",
        validation_alias="OPTICODDS_API_KEY",
    )

    catapult_api_key: str = Field(
        default="",
        validation_alias="CATAPULT_API_KEY",
    )
    catapult_base_url: str = Field(
        default="",
        validation_alias="CATAPULT_BASE_URL",
    )
    whoop_client_id: str = Field(
        default="",
        validation_alias="WHOOP_CLIENT_ID",
    )
    whoop_client_secret: str = Field(
        default="",
        validation_alias="WHOOP_CLIENT_SECRET",
    )

    twitter_bearer_token: str = Field(
        default="",
        validation_alias="TWITTER_BEARER_TOKEN",
    )
    twitter_auth_token: str = Field(
        default="",
        validation_alias="TWITTER_AUTH_TOKEN",
    )
    twitter_ct0: str = Field(
        default="",
        validation_alias="TWITTER_CT0",
    )
    reddit_client_id: str = Field(
        default="",
        validation_alias="REDDIT_CLIENT_ID",
    )
    reddit_client_secret: str = Field(
        default="",
        validation_alias="REDDIT_CLIENT_SECRET",
    )

    ingestion_port: int = Field(
        default=8001,
        validation_alias="INGESTION_PORT",
    )
    nlp_service_port: int = Field(
        default=8002,
        validation_alias="NLP_SERVICE_PORT",
    )
    biometric_service_port: int = Field(
        default=8003,
        validation_alias="BIOMETRIC_SERVICE_PORT",
    )
    model_serving_port: int = Field(
        default=8004,
        validation_alias="MODEL_SERVING_PORT",
    )
    reporting_service_port: int = Field(
        default=8005,
        validation_alias="REPORTING_SERVICE_PORT",
    )

    @model_validator(mode="after")
    def check_required_secrets(self) -> "Settings":
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        if not self.database_url_sync:
            raise ValueError("DATABASE_URL_SYNC environment variable is required")
        return self

    @property
    def kafka_consumer_group(self) -> str:
        return "sports-prediction-system"

    @property
    def kafka_topics(self) -> dict[str, str]:
        return {
            "raw_match_events": "raw.match-events",
            "raw_odds_updates": "raw.odds-updates",
            "raw_biometrics": "raw.biometrics",
            "raw_social_text": "raw.social-text",
            "processed_sentiment": "processed.sentiment",
            "processed_biometric_features": "processed.biometric-features",
            "processed_features": "processed.features",
            "processed_predictions": "processed.predictions",
        }


settings = Settings()


def get_settings() -> Settings:
    return settings


def get_setting(key: str, default: Any = None) -> Any:
    return getattr(settings, key, default)
