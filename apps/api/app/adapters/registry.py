"""Реестр источников: собирает адаптеры по настройкам и даёт статус доступа."""

from app.adapters.base import SocialSourceAdapter
from app.adapters.instagram import InstagramAdapter
from app.adapters.vk import VKAdapter
from app.adapters.youtube import YouTubeAdapter
from app.config import Settings
from app.schemas import SourceStatus


class SourceRegistry:
    """Держит адаптеры платформ и умеет честно рассказать, что настроено."""

    def __init__(self, settings: Settings) -> None:
        self._adapters: dict[str, SocialSourceAdapter] = {
            "youtube": YouTubeAdapter(
                api_key=settings.youtube_api_key, timeout=settings.http_timeout
            ),
            "vk": VKAdapter(
                access_token=settings.vk_access_token,
                api_version=settings.vk_api_version,
                timeout=settings.http_timeout,
            ),
            # Instagram подключается через Apify: своего публичного API для
            # competitor research у Instagram нет.
            "instagram": InstagramAdapter(
                token=settings.apify_token,
                actor=settings.apify_instagram_actor,
                sync_timeout=settings.apify_sync_timeout,
                max_charge_usd=settings.apify_max_charge_usd,
            ),
        }
        # Какая переменная окружения включает источник — чтобы статус был actionable.
        self._env_hints: dict[str, str] = {
            "youtube": "YOUTUBE_API_KEY",
            "vk": "VK_ACCESS_TOKEN",
            "instagram": "APIFY_TOKEN",
        }

    def get(self, source: str) -> SocialSourceAdapter:
        if source not in self._adapters:
            raise KeyError(f"Неизвестный источник: {source}")
        return self._adapters[source]

    def available(self, sources: list[str]) -> tuple[list[SocialSourceAdapter], list[SourceStatus]]:
        """Возвращает рабочие адаптеры и статусы всех запрошенных источников."""
        ready: list[SocialSourceAdapter] = []
        statuses: list[SourceStatus] = []
        for name in sources:
            adapter = self._adapters.get(name)
            if adapter is None:
                statuses.append(
                    SourceStatus(source=name, configured=False, detail="Источник не подключён")
                )
                continue
            if adapter.configured:
                ready.append(adapter)
                statuses.append(SourceStatus(source=name, configured=True, detail="Готов к работе"))
            else:
                hint = self._env_hints.get(name, "ключ доступа")
                statuses.append(
                    SourceStatus(
                        source=name,
                        configured=False,
                        detail=f"Не задан {hint} в окружении сервиса",
                    )
                )
        return ready, statuses

    def statuses(self) -> list[SourceStatus]:
        _, statuses = self.available(list(self._adapters.keys()))
        return statuses
