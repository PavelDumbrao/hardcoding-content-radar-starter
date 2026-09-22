"""Проверка проекта перед Pull Request.

Что проверяем:
  1. Обязательные файлы на месте (иначе агент «потерял» договорённости проекта).
  2. Секретов нет: ни файлов вида .env, ни ключей в тексте.
  3. Python и JavaScript синтаксически валидны.
  4. Compose-файлы валидны (если в среде есть docker).

Запуск: python scripts/validate_project.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "PROJECT.md",
    "TASKS.md",
    "AGENTS.md",
    ".gitignore",
    ".env.example",
    ".github/pull_request_template.md",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docs/getting-started.md",
    "docs/architecture.md",
    "docs/deploy.md",
    "docs/next-steps.md",
]

SECRET_FILES = [".env", "id_rsa", "id_ed25519", "credentials.json"]

SUSPICIOUS_PATTERNS = [
    # Присваивание с длинным значением в той же строке.
    # Важно: именно [ \t]*, а не \s* — иначе пустой SECRET_KEY=
    # «склеивается» со следующим ключом из-за перевода строки и даёт ложное срабатывание.
    re.compile(r"(?i)(api[_-]?key|secret|token|password)[ \t]*=[ \t]*['\"]?[A-Za-z0-9_\-]{16,}"),
    # Характерные префиксы реальных ключей.
    re.compile(r"apify_api_[A-Za-z0-9]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
]

TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh", ".html", ".css", ".example"}

errors: list[str] = []
notes: list[str] = []


def check_required_files() -> None:
    for name in REQUIRED:
        if not (ROOT / name).exists():
            errors.append(f"нет обязательного файла: {name}")


def check_secrets() -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.name in SECRET_FILES:
            errors.append(f"секретный файл не должен попадать в git: {path.relative_to(ROOT)}")
        if path.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                errors.append(f"похоже на секрет в файле: {path.relative_to(ROOT)}")


def check_env_example() -> None:
    """В .env.example не должно быть заполненных секретов.

    Проверяем только те ключи, значения которых обязаны быть пустыми:
    остальные настройки содержат нормальные значения по умолчанию.
    """
    example = ROOT / ".env.example"
    if not example.exists():
        return

    # Ключи, которые должны приходить только от пользователя.
    must_be_empty = {
        "LLM_API_KEY",
        "YOUTUBE_API_KEY",
        "VK_ACCESS_TOKEN",
        "APIFY_TOKEN",
    }
    # Допустимые заглушки, явно показывающие, что значение надо заменить.
    placeholders = {"change-me", "changeme", "your-key-here", "example"}

    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in must_be_empty and value:
            errors.append(f"в .env.example у {key} должно быть пустое значение")
        if key == "POSTGRES_PASSWORD" and value and value not in placeholders:
            errors.append(
                f"в .env.example у {key} должна быть заглушка ({', '.join(sorted(placeholders))})"
            )


def _run(cmd: list[str], cwd: Path, env_note: str) -> None:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        notes.append(f"пропущено ({env_note})")
        return
    if result.returncode != 0:
        errors.append(f"{' '.join(cmd)} завершился с ошибкой:\n{(result.stderr or result.stdout).strip()[:1500]}")


def check_python_syntax() -> None:
    source = ROOT / "apps/api/app"
    if not source.exists():
        return
    _run([sys.executable, "-m", "compileall", "-q", str(source)], ROOT, "python syntax")


def check_js_syntax() -> None:
    app_js = ROOT / "apps/api/app/web/app.js"
    if not app_js.exists():
        return
    if shutil.which("node") is None:
        notes.append("пропущено (node не найден): проверка синтаксиса app.js")
        return
    _run(["node", "--check", str(app_js)], ROOT, "js syntax")


def check_compose() -> None:
    """Проверяем валидность compose-файлов.

    `docker compose config` требует, чтобы файл .env существовал (он указан
    в env_file), а в репозитории его быть не должно. Поэтому на время проверки
    временно создаём .env из .env.example и обязательно убираем его за собой.
    """
    if shutil.which("docker") is None:
        notes.append("пропущено (docker не найден): проверка compose-файлов")
        return

    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    created_env = False

    if not env_file.exists() and example.exists():
        env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        created_env = True

    env = {
        "POSTGRES_PASSWORD": "test-password",
        "APP_DOMAIN": "example.com",
        "TRAEFIK_NETWORK": "traefik",
        "STACK_SUBNET": "10.247.0.0/24",
    }

    try:
        for name in ("docker-compose.yml", "docker-compose.prod.yml"):
            path = ROOT / name
            if not path.exists():
                continue
            try:
                result = subprocess.run(
                    ["docker", "compose", "-f", str(path), "config", "-q"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env={**os.environ, **env},
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                notes.append(f"пропущено (docker недоступен): {name}")
                continue
            if result.returncode != 0:
                errors.append(
                    f"{name} невалиден:\n{(result.stderr or result.stdout).strip()[:800]}"
                )
    finally:
        if created_env:
            env_file.unlink(missing_ok=True)


def main() -> None:
    check_required_files()
    check_secrets()
    check_env_example()
    check_python_syntax()
    check_js_syntax()
    check_compose()

    for note in notes:
        print("ПРОПУЩЕНО:", note)

    if errors:
        print("VALIDATION FAILED")
        for item in errors:
            print("-", item)
        raise SystemExit(1)

    print("VALIDATION OK")


if __name__ == "__main__":
    main()
