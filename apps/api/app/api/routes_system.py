"""Служебные роуты: здоровье сервиса и статус источников."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    """Liveness/readiness: приложение поднялось и отвечает."""
    settings = request.app.state.settings
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "llm_configured": settings.llm_configured,
        "model": settings.llm_model,
    }


@router.get("/api/sources")
async def sources(request: Request) -> dict:
    """Честный статус источников: что настроено, а что нет."""
    registry = request.app.state.registry
    return {"sources": [status.model_dump(mode="json") for status in registry.statuses()]}
