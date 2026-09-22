"""Pydantic-схемы: контракты адаптеров, evidence и ответов API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["youtube", "vk", "instagram"]


class VideoQuery(BaseModel):
    """Параметры поиска, не зависящие от платформы."""

    query: str = Field(min_length=1, max_length=300)
    max_results: int = Field(default=25, ge=1, le=100)
    published_after: datetime | None = None
    order: Literal["relevance", "date", "views"] = "relevance"


class NormalizedMetrics(BaseModel):
    """Метрики с обязательным временем наблюдения — требование Freshness Contract."""

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    observed_at: datetime


class NormalizedVideo(BaseModel):
    """Единое представление ролика для всех платформ."""

    platform: Platform
    external_id: str
    url: str
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None

    creator_external_id: str | None = None
    creator_title: str | None = None
    creator_url: str | None = None

    metrics: NormalizedMetrics


class SourceStatus(BaseModel):
    """Состояние источника: настроен ли доступ и что именно отсутствует."""

    source: str
    configured: bool
    detail: str


class EvidenceItem(BaseModel):
    """Доказательство под цифру в ответе агента."""

    source: str
    operation: str
    observed_at: datetime
    summary: str
    items: int = 0
    url: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    sources: list[Platform] = Field(default_factory=lambda: ["youtube", "vk"])
    max_results: int = Field(default=15, ge=1, le=50)


class ToolRun(BaseModel):
    """Один вызов инструмента агентом — для прозрачности в UI."""

    tool: str
    status: Literal["ok", "error"]
    detail: str


class ChatResponse(BaseModel):
    reply: str
    tool_runs: list[ToolRun] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
