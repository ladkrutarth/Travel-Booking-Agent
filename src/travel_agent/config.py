"""Application configuration from environment."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    kill_switch: bool = False
    max_agent_steps: int = 12
    max_trip_cost_usd: float = 0.50
    agent_timeout_seconds: int = 120
    log_level: str = "INFO"

    database_url: str = "sqlite:///./travel_agent.db"

    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_extraction_model: str = "gpt-4o-mini"

    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    amadeus_hostname: Literal["test", "production"] = "test"
    amadeus_mock: bool = True
    flight_sources: Literal["mock", "live"] = "mock"

    openweather_api_key: str = ""
    openweather_mock: bool = True

    google_places_api_key: str = ""
    google_places_mock: bool = True

    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "travel-booking-agent"

    jwt_secret: str = "dev-change-me-travel-booking-secret"
    jwt_access_minutes: int = 60
    jwt_refresh_days: int = 14
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    proposal_ttl_minutes: int = 30

    @property
    def amadeus_base_url(self) -> str:
        if self.amadeus_hostname == "production":
            return "https://api.amadeus.com"
        return "https://test.api.amadeus.com"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
