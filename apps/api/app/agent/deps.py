"""Зависимости агента: доступ к источникам, БД и накопленному evidence."""

from dataclasses import dataclass, field

from app.adapters.registry import SourceRegistry
from app.config import Settings
from app.schemas import EvidenceItem, ToolRun


@dataclass
class RadarDeps:
    """Контекст одного запуска агента.

    evidence и tool_runs наполняются инструментами по ходу выполнения:
    так пользователь получает не только текст, но и проверяемые источники.
    """

    settings: Settings
    registry: SourceRegistry
    default_sources: list[str] = field(default_factory=lambda: ["youtube", "vk", "instagram"])
    max_results: int = 15
    evidence: list[EvidenceItem] = field(default_factory=list)
    tool_runs: list[ToolRun] = field(default_factory=list)
    collected_videos: dict[str, dict] = field(default_factory=dict)

    def add_evidence(self, item: EvidenceItem) -> None:
        self.evidence.append(item)

    def add_tool_run(self, tool: str, status: str, detail: str) -> None:
        self.tool_runs.append(ToolRun(tool=tool, status=status, detail=detail))  # type: ignore[arg-type]

    def remember(self, key: str, payload: dict) -> None:
        """Запоминаем найденные ролики, чтобы агент мог ссылаться на них по id."""
        self.collected_videos[key] = payload
