"""Инструменты агента.

Каждый инструмент — детерминированный шаг: он ходит в API, сохраняет данные
и возвращает факты с обязательным observed_at. Никаких выдуманных чисел.
"""

from datetime import datetime, timedelta, timezone
from statistics import median

from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adapters.base import SourceError
from app.agent.deps import RadarDeps
from app.db import SessionFactory
from app.models import Video
from app.schemas import VideoQuery
from app.services import metrics as metric_utils
from app.services.store import (
    creator_baseline,
    log_source_event,
    save_videos,
    to_evidence,
    video_snapshots,
)


async def get_source_status(ctx: RunContext[RadarDeps]) -> list[dict]:
    """Проверить, какие источники (YouTube, VK) реально настроены и доступны.

    Вызывай этот инструмент первым, если пользователь спрашивает про данные
    с источников, чтобы честно сказать, где нет ключа доступа.
    """
    statuses = ctx.deps.registry.statuses()
    ready = [s.source for s in statuses if s.configured]
    ctx.deps.add_tool_run(
        "get_source_status",
        "ok",
        f"доступны: {', '.join(ready) if ready else 'нет источников'}",
    )
    ctx.deps.add_evidence(
        to_evidence(
            source="registry",
            operation="get_source_status",
            summary=", ".join(f"{s.source}: {'ok' if s.configured else 'нет ключа'}" for s in statuses),
            items=len(statuses),
            observed_at=datetime.now(tz=timezone.utc),
        )
    )
    return [s.model_dump(mode="json") for s in statuses]


async def search_content(
    ctx: RunContext[RadarDeps],
    query: str,
    sources: list[str] | None = None,
    max_results: int = 15,
    published_after_days: int | None = None,
    order: str = "relevance",
) -> dict:
    """Найти ролики по запросу на выбранных платформах и сохранить метрики в базу.

    Возвращает список найденных роликов с метриками, скоростью роста (velocity),
    outlier относительно автора и предварительным trend score.
    Аргументы:
      query — поисковый запрос (например "vibe coding");
      sources — список источников: ["youtube", "vk"];
      max_results — сколько роликов запросить с каждой платформы (1..50);
      published_after_days — ограничить свежесть, например 14;
      order — relevance | date | views.
    """
    settings = ctx.deps.settings
    requested = sources or ctx.deps.default_sources
    limit = max(1, min(max_results or ctx.deps.max_results, 50))
    order_value = order if order in {"relevance", "date", "views"} else "relevance"

    published_after = None
    if published_after_days:
        published_after = datetime.now(tz=timezone.utc) - timedelta(days=published_after_days)

    adapters, statuses = ctx.deps.registry.available(requested)
    ready_sources = [s.source for s in statuses if s.configured]
    blocked = [f"{s.source} ({s.detail})" for s in statuses if not s.configured]

    collected: list[dict] = []
    errors: list[str] = []

    for adapter in adapters:
        started = datetime.now(tz=timezone.utc)
        try:
            videos = await adapter.search_videos(
                VideoQuery(
                    query=query,
                    max_results=limit,
                    published_after=published_after,
                    order=order_value,  # type: ignore[arg-type]
                )
            )
        except SourceError as error:
            errors.append(f"{adapter.name}: {error}")
            await _log(ctx, adapter.name, "search_videos", "error", started, str(error))
            continue
        except Exception as error:  # сеть/парсинг — не роняем весь запрос
            errors.append(f"{adapter.name}: неожиданная ошибка {type(error).__name__}: {error}")
            await _log(ctx, adapter.name, "search_videos", "error", started, str(error))
            continue

        await _log(ctx, adapter.name, "search_videos", "ok", started, f"найдено {len(videos)}")
        if not videos:
            continue

        async with SessionFactory() as session:
            await save_videos(session, videos)

        for video in videos:
            payload = await _describe_video(ctx, video.platform, video.external_id, video)
            if payload:
                collected.append(payload)

        ctx.deps.add_evidence(
            to_evidence(
                source=adapter.name,
                operation=f"search_videos: {query}",
                summary=f"Найдено {len(videos)} роликов по запросу «{query}»",
                items=len(videos),
                observed_at=datetime.now(tz=timezone.utc),
            )
        )

    collected.sort(key=lambda item: item.get("trend_score") or 0, reverse=True)
    top = collected[: max(limit, 10)]
    ctx.deps.add_tool_run(
        "search_content",
        "ok",
        f"найдено {len(collected)} роликов, источники: {', '.join(ready_sources) or 'нет'}",
    )

    return {
        "query": query,
        "sources_used": ready_sources,
        "sources_blocked": blocked,
        "errors": errors,
        "found": len(collected),
        "observed_at": datetime.now(tz=timezone.utc).isoformat(),
        "limit_note": f"в ответе показаны {len(top)} лучших кандидатов",
        "videos": top,
    }

async def rank_videos(
    ctx: RunContext[RadarDeps],
    min_views: int = 0,
    limit: int = 10,
    platform: str | None = None,
) -> dict:
    """Отранжировать уже сохранённые ролики по trend score и outlier.

    Используй после search_content, когда нужно ответить на вопрос
    "что сейчас залетает" и нужен подтверждённый порядок.
    """
    items = list(ctx.deps.collected_videos.values())
    if platform:
        items = [item for item in items if item["platform"] == platform]
    filtered = [item for item in items if (item.get("views") or 0) >= min_views]
    filtered.sort(key=lambda item: (item.get("trend_score") or 0, item.get("outlier") or 0), reverse=True)
    return {"count": len(filtered), "videos": filtered[: max(1, min(limit, 50))]}


async def get_comments(
    ctx: RunContext[RadarDeps],
    platform: str,
    video_external_id: str,
    limit: int = 50,
) -> dict:
    """Получить комментарии к ролику для анализа аудитории (боли, вопросы, возражения).

    platform — youtube | vk; video_external_id — id ролика на платформе
    (для VK формат "-12345_678", для YouTube — videoId).
    """
    adapter = ctx.deps.registry.get(platform)
    started = datetime.now(tz=timezone.utc)
    if not adapter.configured:
        ctx.deps.add_tool_run("get_comments", "error", f"{platform}: нет ключа доступа")
        return {"error": f"Источник {platform} не настроен: нет ключа доступа", "comments": []}

    try:
        comments = await adapter.get_comments(video_external_id, limit=limit)
    except SourceError as error:
        await _log(ctx, platform, "get_comments", "error", started, str(error))
        ctx.deps.add_tool_run("get_comments", "error", f"{platform}: {error}")
        return {"error": str(error), "comments": []}

    await _log(ctx, platform, "get_comments", "ok", started, f"получено {len(comments)}")
    ctx.deps.add_evidence(
        to_evidence(
            source=platform,
            operation=f"get_comments: {video_external_id}",
            summary=f"Собрано {len(comments)} комментариев к ролику",
            items=len(comments),
            observed_at=datetime.now(tz=timezone.utc),
        )
    )
    ctx.deps.add_tool_run("get_comments", "ok", f"{platform}: {len(comments)} комментариев")
    return {
        "platform": platform,
        "video_external_id": video_external_id,
        "count": len(comments),
        "observed_at": datetime.now(tz=timezone.utc).isoformat(),
        "comments": comments[: max(1, min(limit, 100))],
    }


async def _describe_video(
    ctx: RunContext[RadarDeps],
    platform: str,
    external_id: str,
    video,
) -> dict | None:
    """Собирает карточку ролика: метрики + история + outlier + trend score."""
    async with SessionFactory() as session:
        # selectinload обязателен: к creator обращаемся уже после закрытия сессии,
        # а ленивая загрузка вне сессии падает с DetachedInstanceError.
        row = await session.scalar(
            select(Video)
            .options(selectinload(Video.creator))
            .where(Video.platform == platform, Video.external_id == external_id)
        )
        if row is None:
            return None
        baseline = await creator_baseline(session, row.creator_id)
        snapshots = await video_snapshots(session, row.id)

    points = [metric_utils.SnapshotPoint(p.observed_at, p.views) for p in snapshots]
    velocity = metric_utils.compute_velocity(points)
    outlier = metric_utils.compute_outlier(row.views, baseline)
    engagement = metric_utils.engagement_rate(row.views, row.likes, row.comments)
    now = datetime.now(tz=timezone.utc)
    age = metric_utils.age_hours(row.published_at, now)
    trend = metric_utils.compute_trend_score(
        velocity.velocity_per_hour, velocity.acceleration_per_hour2, outlier, engagement, age
    )

    payload = {
        "platform": row.platform,
        "external_id": row.external_id,
        "url": row.url,
        "title": row.title,
        "creator": row.creator.title if row.creator else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "age_hours": round(age, 1) if age is not None else None,
        "views": row.views,
        "likes": row.likes,
        "comments": row.comments,
        "engagement_rate": round(engagement, 5) if engagement is not None else None,
        "views_per_hour": round(velocity.velocity_per_hour, 1) if velocity.velocity_per_hour else None,
        "acceleration": (
            round(velocity.acceleration_per_hour2, 2) if velocity.acceleration_per_hour2 else None
        ),
        "outlier": outlier,
        "creator_median_views": int(median(baseline)) if baseline else None,
        "trend_score": trend,
        "snapshots": len(snapshots),
        "metrics_observed_at": row.metrics_observed_at.isoformat() if row.metrics_observed_at else None,
    }
    ctx.deps.remember(f"{platform}:{external_id}", payload)
    return payload


async def _log(ctx: RunContext[RadarDeps], source: str, operation: str, status: str, started, message: str) -> None:
    """Пишем аудит внешнего вызова (source_events) — нужно для observability."""
    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    async with SessionFactory() as session:
        await log_source_event(session, source, operation, status, latency_ms, message)

