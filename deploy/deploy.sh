#!/usr/bin/env bash
# Деплой Content Radar AI на свой сервер по SSH.
#
# Скрипт идемпотентный: повторный запуск обновит код и пересоберёт сервис.
# Перед первым запуском на сервере должен быть склонирован репозиторий и создан .env.
#
# Использование:
#   VPS_HOST=root@203.0.113.10 APP_DOMAIN=radar.example.com ./deploy/deploy.sh
#
# Переменные:
#   VPS_HOST     куда подключаться по SSH (обязательно)
#   VPS_KEY      путь к приватному ключу (по умолчанию ~/.ssh/id_ed25519)
#   APP_DIR      каталог проекта на сервере (по умолчанию /opt/content-radar-ai)
#   APP_DOMAIN   домен сервиса для проверки после деплоя
set -euo pipefail

VPS_HOST="${VPS_HOST:?Укажи VPS_HOST, например root@203.0.113.10}"
VPS_KEY="${VPS_KEY:-$HOME/.ssh/id_ed25519}"
APP_DIR="${APP_DIR:-/opt/content-radar-ai}"
APP_DOMAIN="${APP_DOMAIN:-}"
COMPOSE_FILE="docker-compose.prod.yml"

echo "==> Деплой на ${VPS_HOST} (${APP_DIR})"

ssh -i "${VPS_KEY}" -o BatchMode=yes "${VPS_HOST}" bash -s <<EOF
set -euo pipefail
cd "${APP_DIR}"

if [ ! -f .env ]; then
  echo "ОШИБКА: нет ${APP_DIR}/.env — создай его из .env.example и заполни" >&2
  exit 1
fi

if [ ! -f ${COMPOSE_FILE} ]; then
  echo "ОШИБКА: нет ${COMPOSE_FILE} в ${APP_DIR}" >&2
  exit 1
fi

echo "-- обновляю код"
git pull --ff-only

echo "-- собираю и запускаю"
docker compose -f ${COMPOSE_FILE} up -d --build

echo "-- проверяю, что сервис отвечает изнутри контейнера"
for _ in \$(seq 1 20); do
  if docker compose -f ${COMPOSE_FILE} exec -T api curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "api отвечает"
    break
  fi
  sleep 3
done

echo "-- статус"
docker compose -f ${COMPOSE_FILE} ps
EOF

if [ -n "${APP_DOMAIN}" ]; then
  echo "==> Проверка публичного адреса"
  curl -fsS "https://${APP_DOMAIN}/healthz" || echo "ВНИМАНИЕ: проверка не прошла (сертификат или роутинг?)"
  echo
  curl -fsS "https://${APP_DOMAIN}/api/sources" || true
  echo
fi

echo "==> Готово"
