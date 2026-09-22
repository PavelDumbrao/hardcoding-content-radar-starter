"""YouTube-адаптер поверх официального YouTube Data API v3.

Ограничения API, которые учтены в коде:
  - search.list стоит 100 units квоты за вызов, поэтому поиск двухшаговый:
    дешёвый search.list (только id) + один videos.list на пачку id.
  - videos.list принимает до 50 идентификаторов за вызов
    (метода videos.batchGetStats в v3 не существует).
"""

from datetime import datetime, timezone

import httpx

from app.adapters.base import SocialSourceAdapter, SourceError
from app.schemas import NormalizedMetrics, NormalizedVideo, VideoQuery

API_ROOT = "https://www.googleapis.com/youtube/v3"
BATCH_LIMIT = 50


class YouTubeAdapter(SocialSourceAdapter):
    name = "youtube"

    def __init__(self, api_key: str, timeout: float = 25.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def _get(self, path: str, params: dict) -> dict:
        if not self.configured:
            raise SourceError(
                "YouTube API key не задан (YOUTUBE_API_KEY). Источник недоступен."
            )
        params = {**params, "key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{API_ROOT}/{path}", params=params)
        if response.status_code == 403:
            raise SourceError(f"YouTube API отклонил запрос (403): {response.text[:300]}")
        if response.status_code == 400:
            raise SourceError(f"Некорректный запрос к YouTube API (400): {response.text[:300]}")
        response.raise_for_status()
        return response.json()

    async def search_videos(self, query: VideoQuery) -> list[NormalizedVideo]:
        order_map = {"relevance": "relevance", "date": "date", "views": "viewCount"}
        params: dict = {
            "part": "snippet",
            "type": "video",
            "q": query.query,
            "maxResults": min(query.max_results, BATCH_LIMIT),
            "order": order_map[query.order],
        }
        if query.published_after:
            params["publishedAfter"] = (
                query.published_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

        payload = await self._get("search", params)
        ids = [
            item["id"]["videoId"]
            for item in payload.get("items", [])
            if item.get("id", {}).get("videoId")
        ]
        if not ids:
            return []
        return await self.refresh_metrics(ids)

    async def refresh_metrics(self, platform_video_ids: list[str]) -> list[NormalizedVideo]:
        if not platform_video_ids:
            return []
        observed_at = datetime.now(tz=timezone.utc)
        results: list[NormalizedVideo] = []
        for start in range(0, len(platform_video_ids), BATCH_LIMIT):
            chunk = platform_video_ids[start : start + BATCH_LIMIT]
            payload = await self._get(
                "videos",
                {"part": "snippet,statistics,contentDetails", "id": ",".join(chunk)},
            )
            for item in payload.get("items", []):
                results.append(self._to_normalized(item, observed_at))
        return results

    async def get_video(self, platform_video_id: str) -> NormalizedVideo:
        videos = await self.refresh_metrics([platform_video_id])
        if not videos:
            raise SourceError(f"YouTube не вернул видео {platform_video_id}")
        return videos[0]

    async def get_comments(self, platform_video_id: str, limit: int = 100) -> list[dict]:
        payload = await self._get(
            "commentThreads",
            {
                "part": "snippet",
                "videoId": platform_video_id,
                "maxResults": min(limit, 100),
                "order": "relevance",
                "textFormat": "plainText",
            },
        )
        comments: list[dict] = []
        for thread in payload.get("items", []):
            top = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comments.append(
                {
                    "platform": "youtube",
                    "external_id": thread.get("id"),
                    "video_external_id": platform_video_id,
                    "text": top.get("textDisplay"),
                    "likes": top.get("likeCount"),
                    "reply_count": thread.get("snippet", {}).get("totalReplyCount"),
                    "created_at": top.get("publishedAt"),
                }
            )
        return comments

    @staticmethod
    def _parse_duration(value: str | None) -> int | None:
        """ISO-8601 (PT1H2M3S) → секунды."""
        if not value or not value.startswith("PT"):
            return None
        total, number = 0, ""
        for char in value[2:]:
            if char.isdigit():
                number += char
                continue
            if char == "H":
                total += int(number or 0) * 3600
            elif char == "M":
                total += int(number or 0) * 60
            elif char == "S":
                total += int(number or 0)
            number = ""
        return total or None

    @staticmethod
    def _as_int(value: object) -> int | None:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def _to_normalized(self, item: dict, observed_at: datetime) -> NormalizedVideo:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        video_id = item["id"]
        channel_id = snippet.get("channelId")
        return NormalizedVideo(
            platform="youtube",
            external_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=snippet.get("title"),
            description=snippet.get("description"),
            published_at=snippet.get("publishedAt"),
            duration_seconds=self._parse_duration(item.get("contentDetails", {}).get("duration")),
            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
            creator_external_id=channel_id,
            creator_title=snippet.get("channelTitle"),
            creator_url=(
                f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
            ),
            metrics=NormalizedMetrics(
                views=self._as_int(stats.get("viewCount")),
                likes=self._as_int(stats.get("likeCount")),
                comments=self._as_int(stats.get("commentCount")),
                shares=None,  # YouTube Data API не отдаёт shares
                observed_at=observed_at,
            ),
        )
