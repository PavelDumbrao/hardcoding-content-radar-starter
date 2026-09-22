"""ORM-модели: минимальный домен Block 1 + история метрик.

Принцип из архитектуры: любая метрика имеет свой observed_at,
поэтому замеры пишутся в отдельную таблицу снапшотов, а не перезаписывают поле.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Единая точка получения времени в UTC (все метрики — в UTC)."""
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    pass


class Creator(Base):
    """Автор/канал/сообщество на конкретной платформе."""

    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_creator_platform_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(191), index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    videos: Mapped[list["Video"]] = relationship(back_populates="creator")


class Video(Base):
    """Ролик с последними известными метриками (история — в VideoSnapshot)."""

    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_video_platform_ext"),
        Index("ix_videos_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(191), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    creator_id: Mapped[int | None] = mapped_column(ForeignKey("creators.id"), nullable=True)
    creator: Mapped[Creator | None] = relationship(back_populates="videos")

    # Последние известные значения + когда именно они были получены.
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    snapshots: Mapped[list["VideoSnapshot"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class VideoSnapshot(Base):
    """Замер метрик в конкретный момент времени — база для velocity и outlier."""

    __tablename__ = "video_snapshots"
    __table_args__ = (Index("ix_snapshot_video_observed", "video_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)

    video: Mapped[Video] = relationship(back_populates="snapshots")


class ResearchRun(Base):
    """Пользовательский запрос как воспроизводимый research run."""

    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    final_results: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceEvent(Base):
    """Аудит внешних вызовов: какой источник, что вернул, сколько занял."""

    __tablename__ = "source_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
