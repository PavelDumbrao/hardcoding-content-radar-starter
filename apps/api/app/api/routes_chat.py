"""HTTP-роуты чата: агент как основной интерфейс сервиса."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.agent.agent import build_agent
from app.agent.deps import RadarDeps
from app.models import ResearchRun
from app.db import SessionFactory
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Обработать запрос пользователя через агента и вернуть ответ с evidence."""
    settings = request.app.state.settings
    registry = request.app.state.registry

    if not settings.llm_configured:
        raise HTTPException(
            status_code=503,
            detail="LLM не настроен: задайте LITELLM_API_KEY в окружении сервиса",
        )

    deps = RadarDeps(
        settings=settings,
        registry=registry,
        default_sources=list(payload.sources),
        max_results=payload.max_results,
    )
    agent = build_agent(settings)

    run_id = await _start_run(payload.message, payload.sources)
    try:
        result = await agent.run(payload.message, deps=deps)
    except Exception as error:  # возвращаем честную ошибку вместо 500 без контекста
        await _finish_run(run_id, status="failed", error=f"{type(error).__name__}: {error}")
        raise HTTPException(status_code=502, detail=f"Ошибка агента: {error}") from error

    output = _extract_output(result)
    await _finish_run(
        run_id,
        status="completed",
        candidates=len(deps.collected_videos),
        final=len(deps.collected_videos),
    )

    return ChatResponse(
        reply=output,
        tool_runs=deps.tool_runs,
        evidence=deps.evidence,
        sources=registry.statuses(),
    )


def _extract_output(result) -> str:
    """Достаём текст ответа: у PydanticAI результат лежит в .output."""
    output = getattr(result, "output", None)
    if output is None:
        output = getattr(result, "data", "")
    return output if isinstance(output, str) else str(output)


async def _start_run(message: str, sources: list[str]) -> int | None:
    """Сохраняем research run — даёт воспроизводимость и историю запросов."""
    try:
        async with SessionFactory() as session:
            run = ResearchRun(
                query=message,
                sources=",".join(sources),
                status="running",
                started_at=datetime.now(tz=timezone.utc),
            )
            session.add(run)
            await session.commit()
            return run.id
    except Exception:
        # История запросов не должна ломать основной сценарий
        return None


async def _finish_run(
    run_id: int | None,
    status: str,
    candidates: int = 0,
    final: int = 0,
    error: str | None = None,
) -> None:
    if run_id is None:
        return
    try:
        async with SessionFactory() as session:
            run = await session.get(ResearchRun, run_id)
            if run is None:
                return
            run.status = status
            run.candidates_found = candidates
            run.final_results = final
            run.error = error[:2000] if error else None
            run.finished_at = datetime.now(tz=timezone.utc)
            await session.commit()
    except Exception:
        return
