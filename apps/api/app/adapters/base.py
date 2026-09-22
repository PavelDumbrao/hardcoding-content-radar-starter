"""Единый контракт источника.

Бизнес-логика и агент работают только с этим интерфейсом и с NormalizedVideo,
поэтому платформу можно заменить, не трогая scoring и агента.
"""

from abc import ABC, abstractmethod

from app.schemas import NormalizedVideo, VideoQuery


class SourceError(RuntimeError):
    """Ошибка источника с понятным для агента текстом.

    Отдельный тип нужен, чтобы отличать ожидаемые сбои (нет ключа, квота,
    недоступный API) от багов кода: агент получает сообщение и продолжает работу.
    """


class SocialSourceAdapter(ABC):
    """Контракт источника из архитектуры (search/get/comments/metrics)."""

    name: str

    @abstractmethod
    async def search_videos(self, query: VideoQuery) -> list[NormalizedVideo]:
        """Найти ролики по запросу."""

    @abstractmethod
    async def get_video(self, platform_video_id: str) -> NormalizedVideo:
        """Получить один ролик со свежими метриками."""

    @abstractmethod
    async def get_comments(self, platform_video_id: str, limit: int = 100) -> list[dict]:
        """Получить комментарии (Block 4, интерфейс зафиксирован заранее)."""

    @abstractmethod
    async def refresh_metrics(self, platform_video_ids: list[str]) -> list[NormalizedVideo]:
        """Обновить метрики пакетом — база для Snapshot Engine."""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Настроен ли доступ (ключ/токен)."""
