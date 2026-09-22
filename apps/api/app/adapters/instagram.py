"""Instagram-адаптер через Apify.

Провайдер — официальный actor `apify/instagram-scraper` (Apify-maintained).
Подтверждённая схема входа: `resultsType` (posts|details|comments|reels|mentions|stories),
`directUrls`, `search`, `searchType` (hashtag|profile|place|user), `resultsLimit`,
`searchLimit`, `onlyPostsNewerThan`.

Особенности, которые учтены в коде:
  - результат платный (price-per-result ~$0.0023), поэтому в каждом вызове передаётся
    `maxTotalChargeUsd` — жёсткий потолок расходов на один запуск;
  - синхронный endpoint Apify живёт максимум 300 секунд, поэтому timeout < 300;
  - формат URL зависит от `resultsType`: `/p/` для постов и комментариев,
    `/reel/` для рилсов, `/username/` для профиля;
  - Instagram отдаёт метрики только как счётчики на момент скрейпа —
    именно этот момент и становится `observed_at`.
"""

from datetime import datetime, timezone

import httpx

from app.adapters.base import SocialSourceAdapter, SourceError
from app.schemas import NormalizedMetrics, NormalizedVideo, VideoQuery

APIFY_BASE = "https://api.apify.com/v2/acts"
HASHTAG_RESULT_LIMIT = 50


class InstagramAdapter(SocialSourceAdapter):
    name = "instagram"

    def __init__(
        self,
        token: str,
        actor: str = "apify~instagram-scraper",
        sync_timeout: int = 240,
        max_charge_usd: float = 0.5,
    ) -> None:
        self._token = token
        self._actor = actor
        self._sync_timeout = min(sync_timeout, 290)
        self._max_charge_usd = max_charge_usd

    @property
    def configured(self) -> bool:
        return bool(self._token)

    async def _run_actor(self, payload: dict, limit: int | None = None) -> list[dict]:
        """Запустить actor синхронно и вернуть элементы датасета."""
        if not self.configured:
            raise SourceError("Apify token не задан (APIFY_TOKEN). Источник недоступен.")

        params: dict = {
            "token": self._token,
            "timeout": self._sync_timeout,
            "format": "json",
            "clean": "true",
        }
        if limit:
            params["limit"] = max(1, limit)
        if self._max_charge_usd:
            params["maxTotalChargeUsd"] = self._max_charge_usd

        url = f"{APIFY_BASE}/{self._actor}/run-sync-get-dataset-items"
        # Клиентский таймаут больше серверного, чтобы получить осмысленную ошибку Apify,
        # а не обрыв соединения на нашей стороне.
        timeout = httpx.Timeout(self._sync_timeout + 30, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, params=params, json=payload)

        if response.status_code in (401, 403):
            raise SourceError("Apify отклонил токен (401/403). Проверьте APIFY_TOKEN.")
        if response.status_code == 402:
            raise SourceError("Apify: исчерпан лимит аккаунта или превышен maxTotalChargeUsd.")
        if response.status_code == 429:
            raise SourceError("Apify: превышен rate limit, попробуйте позже.")
        if response.status_code >= 400:
            raise SourceError(
                f"Apify вернул {response.status_code}: {response.text[:300]}"
            )

        body = response.json()
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            return body.get("items", [])
        return []

    async def search_videos(self, query: VideoQuery) -> list[NormalizedVideo]:
        """Найти контент: `@username` — посты профиля, иначе поиск по хештегу."""
        term = query.query.strip()
        if term.startswith("@"):
            payload = {
                "directUrls": [f"https://www.instagram.com/{term[1:]}/"],
                "resultsType": "posts",
                "resultsLimit": min(query.max_results, HASHTAG_RESULT_LIMIT),
            }
        else:
            # Instagram-хештег не может содержать пробелы, поэтому склеиваем слова:
            # "vibe coding" → "#vibecoding".
            tag = term.lstrip("#").replace(" ", "").replace("-", "").lower()
            payload = {
                "search": f"#{tag}",
                "searchType": "hashtag",
                "searchLimit": 1,
                "resultsType": "posts",
                "resultsLimit": min(query.max_results, HASHTAG_RESULT_LIMIT),
            }

        if query.published_after:
            payload["onlyPostsNewerThan"] = query.published_after.astimezone(
                timezone.utc
            ).strftime("%Y-%m-%d")

        items = await self._run_actor(payload, limit=query.max_results)
        observed_at = datetime.now(tz=timezone.utc)
        videos: list[NormalizedVideo] = []
        for item in items:
            normalized = self._to_normalized(item, observed_at)
            if normalized is not None:
                videos.append(normalized)
        return videos

    async def refresh_metrics(self, platform_video_ids: list[str]) -> list[NormalizedVideo]:
        """Обновить метрики по списку постов/рилсов (id, shortCode или URL)."""
        if not platform_video_ids:
            return []
        urls = [self._as_url(item) for item in platform_video_ids]
        payload = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": 1,  # один пост на каждый URL
        }
        items = await self._run_actor(payload, limit=len(urls))
        observed_at = datetime.now(tz=timezone.utc)
        videos: list[NormalizedVideo] = []
        for item in items:
            normalized = self._to_normalized(item, observed_at)
            if normalized is not None:
                videos.append(normalized)
        return videos

    async def get_video(self, platform_video_id: str) -> NormalizedVideo:
        videos = await self.refresh_metrics([platform_video_id])
        if not videos:
            raise SourceError(f"Instagram не вернул пост {platform_video_id}")
        return videos[0]

    async def get_comments(self, platform_video_id: str, limit: int = 100) -> list[dict]:
        """Комментарии доступны только для постов: /p/<code>/, а не для профиля."""
        payload = {
            "directUrls": [self._as_url(platform_video_id, prefer_reel=False)],
            "resultsType": "comments",
            "resultsLimit": max(1, min(limit, 100)),
        }
        items = await self._run_actor(payload, limit=limit)
        comments: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            comments.append(
                {
                    "platform": "instagram",
                    "external_id": item.get("id"),
                    "video_external_id": platform_video_id,
                    "text": item.get("text"),
                    "likes": self._as_int(item.get("likesCount")),
                    "reply_count": self._as_int(item.get("repliesCount")),
                    "created_at": item.get("timestamp"),
                    "author": item.get("ownerUsername"),
                }
            )
        return comments

    @staticmethod
    def _as_url(value: str, prefer_reel: bool = False) -> str:
        """Приводим id/shortCode к URL поста — формат обязателен для actor'а."""
        if value.startswith("http"):
            return value
        segment = "reel" if prefer_reel else "p"
        return f"https://www.instagram.com/{segment}/{value}/"

    @staticmethod
    def _as_int(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _first_line(text: str | None, fallback: str | None) -> str | None:
        """Заголовок ролика: первая строка caption, иначе подпись из метаданных."""
        if text:
            for line in text.splitlines():
                if line.strip():
                    return line.strip()[:512]
        return fallback

    def _to_normalized(self, item: dict, observed_at: datetime) -> NormalizedVideo | None:
        """Преобразовать элемент actor'а в наш NormalizedVideo."""
        if not isinstance(item, dict) or item.get("error"):
            return None
        short_code = item.get("shortCode") or item.get("shortcode")
        post_id = item.get("id")
        if not short_code and not post_id:
            return None

        # Рилы живут по /reel/, обычные посты — по /p/.
        is_reel = (item.get("productType") == "clips") or (item.get("type") == "Reel")
        segment = "reel" if is_reel else "p"
        url = item.get("url") or (
            f"https://www.instagram.com/{segment}/{short_code or post_id}/"
        )

        caption = item.get("caption")
        owner = item.get("ownerUsername") or item.get("ownerId")
        views = (
            self._as_int(item.get("videoViewCount"))
            or self._as_int(item.get("videoPlayCount"))
            or self._as_int(item.get("videoViewCount"))
        )
        published_at = item.get("timestamp")
        if isinstance(published_at, (int, float)):
            published_at = datetime.fromtimestamp(published_at, tz=timezone.utc).isoformat()

        return NormalizedVideo(
            platform="instagram",
            external_id=short_code or str(post_id),
            url=url,
            title=self._first_line(caption, item.get("alt")),
            description=caption,
            published_at=published_at,
            duration_seconds=self._as_int(item.get("videoDuration")),
            thumbnail_url=item.get("displayUrl"),
            creator_external_id=owner,
            creator_title=owner,
            creator_url=(
                f"https://www.instagram.com/{owner}/" if owner else None
            ),
            metrics=NormalizedMetrics(
                views=views,
                likes=self._as_int(item.get("likesCount")),
                comments=self._as_int(item.get("commentsCount")),
                shares=None,  # Instagram публично не отдаёт shares
                observed_at=observed_at,
            ),
        )

