"""VK-адаптер поверх официального VK API.

Честные ограничения VK, которые важно помнить:
  - методы video.* требуют пользовательского токена с нужными правами;
  - часть метрик VK не отдаёт публично;
  - формат ответа — {"response": {...}} либо {"error": {...}}.
"""

from datetime import datetime, timezone

import httpx

from app.adapters.base import SocialSourceAdapter, SourceError
from app.schemas import NormalizedMetrics, NormalizedVideo, VideoQuery

API_ROOT = "https://api.vk.com/method"


class VKAdapter(SocialSourceAdapter):
    name = "vk"

    def __init__(self, access_token: str, api_version: str = "5.199", timeout: float = 25.0) -> None:
        self._token = access_token
        self._version = api_version
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._token)

    async def _call(self, method: str, params: dict) -> dict:
        if not self.configured:
            raise SourceError("VK access token не задан (VK_ACCESS_TOKEN). Источник недоступен.")
        payload = {**params, "access_token": self._token, "v": self._version}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{API_ROOT}/{method}", data=payload)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            error = body["error"]
            raise SourceError(
                f"VK API: {error.get('error_code')} {error.get('error_msg')} ({method})"
            )
        return body.get("response", {})

    async def search_videos(self, query: VideoQuery) -> list[NormalizedVideo]:
        response = await self._call(
            "video.search",
            {
                "q": query.query,
                "count": min(query.max_results, 200),
                "sort": 0 if query.order != "date" else 1,
                "adult": 0,
            },
        )
        observed_at = datetime.now(tz=timezone.utc)
        videos: list[NormalizedVideo] = []
        for item in response.get("items", []):
            normalized = self._to_normalized(item, observed_at)
            if normalized is not None:
                videos.append(normalized)
        return videos

    async def refresh_metrics(self, platform_video_ids: list[str]) -> list[NormalizedVideo]:
        if not platform_video_ids:
            return []
        observed_at = datetime.now(tz=timezone.utc)
        # Контракт ожидает строки вида "-123_456": без owner_id VK метрики не отдаёт.
        response = await self._call(
            "video.get",
            {"videos": ",".join(platform_video_ids), "extended": 1},
        )
        videos: list[NormalizedVideo] = []
        for item in response.get("items", []):
            normalized = self._to_normalized(item, observed_at)
            if normalized is not None:
                videos.append(normalized)
        return videos

    async def get_video(self, platform_video_id: str) -> NormalizedVideo:
        videos = await self.refresh_metrics([platform_video_id])
        if not videos:
            raise SourceError(f"VK не вернул видео {platform_video_id}")
        return videos[0]

    async def get_comments(self, platform_video_id: str, limit: int = 100) -> list[dict]:
        owner_id, _, video_id = platform_video_id.partition("_")
        if not owner_id or not video_id:
            raise SourceError("VK ожидает id вида '-owner_id_video_id' (например '-12345_678')")
        response = await self._call(
            "video.getComments",
            {
                "owner_id": owner_id,
                "video_id": video_id,
                "count": min(limit, 100),
                "sort": "desc",
            },
        )
        comments: list[dict] = []
        for item in response.get("items", []):
            likes = item.get("likes")
            thread = item.get("thread")
            comments.append(
                {
                    "platform": "vk",
                    "external_id": item.get("id"),
                    "video_external_id": platform_video_id,
                    "text": item.get("text"),
                    "likes": likes.get("count") if isinstance(likes, dict) else None,
                    "reply_count": thread.get("count") if isinstance(thread, dict) else None,
                    "created_at": item.get("date"),
                }
            )
        return comments

    @staticmethod
    def _count(value: object) -> int | None:
        """VK отдаёт метрики вложенным объектом {"count": N}."""
        if isinstance(value, dict):
            count = value.get("count")
            return count if isinstance(count, int) else None
        return None

    def _to_normalized(self, item: dict, observed_at: datetime) -> NormalizedVideo | None:
        owner_id = item.get("owner_id")
        video_id = item.get("id")
        if owner_id is None or video_id is None:
            return None
        external_id = f"{owner_id}_{video_id}"
        published_ts = item.get("date")
        return NormalizedVideo(
            platform="vk",
            external_id=external_id,
            url=f"https://vk.com/video{external_id}",
            title=item.get("title"),
            description=item.get("description"),
            published_at=(
                datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts else None
            ),
            duration_seconds=item.get("duration"),
            thumbnail_url=item.get("image") or item.get("photo_320"),
            creator_external_id=str(owner_id),
            creator_title=item.get("owner_name") or item.get("author_name"),
            creator_url=f"https://vk.com/club{abs(owner_id)}" if owner_id < 0 else None,
            metrics=NormalizedMetrics(
                views=item.get("views") if isinstance(item.get("views"), int) else None,
                likes=self._count(item.get("likes")),
                comments=self._count(item.get("comments")),
                shares=self._count(item.get("reposts")),
                observed_at=observed_at,
            ),
        )
