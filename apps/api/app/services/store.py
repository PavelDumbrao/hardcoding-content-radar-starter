"""Сохранение роликов: дедупликация, снапшоты метрик, baseline автора."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Creator, SourceEvent, Video, VideoSnapshot, utcnow
from app.schemas import EvidenceItem, NormalizedVideo


async def save_videos(session: AsyncSession, videos: list[NormalizedVideo]) -> list[Video]:
    """Upsert роликов + запись снапшота метрик на каждый замер.

    Дедупликация идёт по (platform, external_id): один и тот же ролик,
    найденный разными запросами, не создаёт дубль.
    """
    saved: list[Video] = []
    for item in videos:
        creator = await _upsert_creator(session, item)
        existing = await session.scalar(
            select(Video).where(
                Video.platform == item.platform,
                Video.external_id == item.external_id,
            )
        )
        if existing is None:
            existing = Video(
                platform=item.platform,
                external_id=item.external_id,
                url=item.url,
                first_seen_at=utcnow(),
            )
            session.add(existing)

        existing.url = item.url
        existing.title = item.title
        existing.description = item.description
        existing.published_at = item.published_at
        existing.duration_seconds = item.duration_seconds
        existing.thumbnail_url = item.thumbnail_url
        existing.creator_id = creator.id if creator else existing.creator_id
        existing.views = item.metrics.views
        existing.likes = item.metrics.likes
        existing.comments = item.metrics.comments
        existing.shares = item.metrics.shares
        existing.metrics_observed_at = item.metrics.observed_at
        existing.last_seen_at = utcnow()

        await session.flush()
        session.add(
            VideoSnapshot(
                video_id=existing.id,
                observed_at=item.metrics.observed_at,
                views=item.metrics.views,
                likes=item.metrics.likes,
                comments=item.metrics.comments,
                shares=item.metrics.shares,
            )
        )
        saved.append(existing)
    await session.commit()
    return saved


async def _upsert_creator(session: AsyncSession, item: NormalizedVideo) -> Creator | None:
    if not item.creator_external_id:
        return None
    creator = await session.scalar(
        select(Creator).where(
            Creator.platform == item.platform,
            Creator.external_id == item.creator_external_id,
        )
    )
    if creator is None:
        creator = Creator(
            platform=item.platform,
            external_id=item.creator_external_id,
            first_seen_at=utcnow(),
        )
        session.add(creator)
    creator.title = item.creator_title or creator.title
    creator.url = item.creator_url or creator.url
    creator.last_seen_at = utcnow()
    await session.flush()
    return creator


async def creator_baseline(session: AsyncSession, creator_id: int | None) -> list[int]:
    """Известные просмотры автора — база для Outlier Score."""
    if creator_id is None:
        return []
    rows = await session.scalars(
        select(Video.views).where(Video.creator_id == creator_id, Video.views.is_not(None))
    )
    return [value for value in rows.all() if value]


async def video_snapshots(session: AsyncSession, video_id: int) -> list[VideoSnapshot]:
    """История замеров ролика — база для Velocity/Acceleration."""
    rows = await session.scalars(
        select(VideoSnapshot)
        .where(VideoSnapshot.video_id == video_id)
        .order_by(VideoSnapshot.observed_at)
    )
    return list(rows.all())


async def log_source_event(
    session: AsyncSession,
    source: str,
    operation: str,
    status: str,
    latency_ms: int | None,
    message: str | None = None,
) -> None:
    """Аудит внешних вызовов: помогает разбирать сбои источников."""
    session.add(
        SourceEvent(
            source=source,
            operation=operation,
            status=status,
            latency_ms=latency_ms,
            message=message[:2000] if message else None,
        )
    )
    await session.commit()


def to_evidence(
    source: str,
    operation: str,
    summary: str,
    items: int,
    observed_at,
    url: str | None = None,
) -> EvidenceItem:
    """Единый формат доказательства для ответа агента (Freshness Contract)."""
    return EvidenceItem(
        source=source,
        operation=operation,
        observed_at=observed_at,
        summary=summary,
        items=items,
        url=url,
    )
