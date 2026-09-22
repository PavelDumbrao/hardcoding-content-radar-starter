"""Content Radar AI — точка входа FastAPI."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.registry import SourceRegistry
from app.api import routes_chat, routes_system
from app.config import get_settings
from app.db import init_models

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Готовим схему БД и реестр источников на старте."""
    settings = get_settings()
    app.state.settings = settings
    app.state.registry = SourceRegistry(settings)
    await init_models()
    yield


app = FastAPI(
    title="Content Radar AI",
    description="Персональный AI-сервис контент-разведки: YouTube + VK, метрики, outlier, идеи.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(routes_system.router)
app.include_router(routes_chat.router)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Минимальный chat-интерфейс (Next.js + assistant-ui — следующая итерация)."""
    return FileResponse(WEB_DIR / "index.html")
