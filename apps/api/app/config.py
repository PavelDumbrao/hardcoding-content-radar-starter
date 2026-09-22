"""Конфигурация сервиса Content Radar AI."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки читаются из окружения и .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Content Radar AI"
    environment: str = "local"

    # База
    database_url: str = Field(
        default="postgresql+asyncpg://radar:radar@db:5432/radar",
        description="DSN Postgres для asyncpg",
    )

    # LLM: подойдёт любой OpenAI-совместимый endpoint.
    # AliasChoices оставлен, чтобы работали и «короткие» имена (LLM_*),
    # и имена с префиксом (LITELLM_*) — например, при своём LiteLLM-шлюзе.
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "LITELLM_BASE_URL"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "LITELLM_API_KEY"),
    )
    # Модель обязана уметь tool calling: агент вызывает инструменты.
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "LITELLM_MODEL"),
    )

    # Источники
    youtube_api_key: str = ""
    vk_access_token: str = ""
    vk_api_version: str = "5.199"

    # Instagram идёт через Apify: официальный actor apify/instagram-scraper.
    apify_token: str = Field(
        default="",
        validation_alias=AliasChoices("APIFY_TOKEN", "APIFY_API_TOKEN"),
    )
    apify_instagram_actor: str = Field(
        default="apify~instagram-scraper",
        validation_alias=AliasChoices("APIFY_INSTAGRAM_ACTOR", "APIFY_ACTOR"),
    )
    # Лимиты нужны, чтобы один запрос не сжёг бюджет: actor платный за результат.
    apify_sync_timeout: int = Field(
        default=240,
        validation_alias=AliasChoices("APIFY_SYNC_TIMEOUT", "APIFY_TIMEOUT"),
    )
    apify_max_charge_usd: float = Field(
        default=0.5,
        validation_alias=AliasChoices("APIFY_MAX_CHARGE_USD", "APIFY_MAX_CHARGE"),
    )

    # Поведение
    max_results: int = 25
    http_timeout: float = 25.0
    request_limit: int = 8

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def youtube_configured(self) -> bool:
        return bool(self.youtube_api_key)

    @property
    def vk_configured(self) -> bool:
        return bool(self.vk_access_token)

    @property
    def apify_configured(self) -> bool:
        return bool(self.apify_token)


@lru_cache
def get_settings() -> Settings:
    """Кэшируем настройки: читаем окружение один раз на процесс."""
    return Settings()
