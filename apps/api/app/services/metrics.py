"""Детерминированный расчёт метрик.

Здесь нет LLM: velocity, acceleration и outlier считает код.
Это ключевое требование архитектуры — модель не придумывает числа.
"""

from dataclasses import dataclass
from datetime import datetime
from statistics import median


@dataclass
class SnapshotPoint:
    """Точка истории метрик для расчёта динамики."""

    observed_at: datetime
    views: int | None


@dataclass
class VelocityResult:
    velocity_per_hour: float | None
    acceleration_per_hour2: float | None
    hours_span: float | None
    samples: int


def _hours_between(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds() / 3600.0


def compute_velocity(points: list[SnapshotPoint]) -> VelocityResult:
    """Считает скорость и ускорение роста просмотров по истории замеров.

    Ускорение считается по последним трём точкам: для нормальной оценки
    нужно минимум три замера, иначе возвращаем только скорость.
    """
    clean = [p for p in points if p.views is not None]
    if len(clean) < 2:
        return VelocityResult(None, None, None, len(clean))

    clean.sort(key=lambda p: p.observed_at)
    first, last = clean[0], clean[-1]
    span = _hours_between(last.observed_at, first.observed_at)
    velocity = (last.views - first.views) / span if span > 0 else None  # type: ignore[operator]

    acceleration = None
    if len(clean) >= 3:
        mid = clean[-2]
        span_a = _hours_between(mid.observed_at, first.observed_at)
        span_b = _hours_between(last.observed_at, mid.observed_at)
        if span_a > 0 and span_b > 0:
            v1 = (mid.views - first.views) / span_a  # type: ignore[operator]
            v2 = (last.views - mid.views) / span_b  # type: ignore[operator]
            acceleration = (v2 - v1) / span_b

    return VelocityResult(velocity, acceleration, span, len(clean))


def compute_outlier(views: int | None, creator_views: list[int]) -> float | None:
    """Во сколько раз ролик превышает обычную медиану автора.

    Медиана выбрана осознанно вместо среднего: одиночный старый вирусный ролик
    искажает среднее и ломает baseline автора.
    """
    if views is None:
        return None
    baseline_values = [value for value in creator_views if value and value > 0]
    if len(baseline_values) < 3:
        return None  # слишком мало данных — честно не считаем
    baseline = median(baseline_values)
    if baseline <= 0:
        return None
    return round(views / baseline, 2)


def compute_trend_score(
    velocity_per_hour: float | None,
    acceleration_per_hour2: float | None,
    outlier: float | None,
    engagement_rate: float | None,
    age_hours: float | None,
) -> float | None:
    """Стартовая эвристика Trend Score из архитектуры (веса — в одном месте).

    30% velocity + 20% acceleration + 20% outlier + 10% engagement + 10% freshness
    (оставшиеся 10% зарезервированы под niche relevance, который появится позже).
    """
    if velocity_per_hour is None:
        return None

    velocity_part = min(velocity_per_hour / 2000.0, 1.0)
    acceleration_part = 0.0 if acceleration_per_hour2 is None else min(max(acceleration_per_hour2, 0) / 500.0, 1.0)
    outlier_part = 0.0 if outlier is None else min(outlier / 10.0, 1.0)
    engagement_part = 0.0 if engagement_rate is None else min(engagement_rate / 0.1, 1.0)
    freshness_part = 0.0 if age_hours is None else max(0.0, min(1.0, 1 - (age_hours / 168.0)))

    score = (
        0.30 * velocity_part
        + 0.20 * acceleration_part
        + 0.20 * outlier_part
        + 0.10 * engagement_part
        + 0.10 * freshness_part
    )
    return round(score * 100, 1)


def engagement_rate(views: int | None, likes: int | None, comments: int | None) -> float | None:
    """Доля реакций к просмотрам — сравнивает ролики разного масштаба."""
    if not views:
        return None
    return ((likes or 0) + (comments or 0)) / views


def age_hours(published_at: datetime | None, now: datetime) -> float | None:
    """Возраст ролика в часах — нужен для нормализации свежести."""
    if published_at is None:
        return None
    return max(_hours_between(now, published_at), 0.0)
