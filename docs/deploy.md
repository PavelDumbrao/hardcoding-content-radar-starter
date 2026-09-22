# Деплой на свой сервер

Этот гайд — про выкладывание сервиса в интернет. Если ты только учишься и тебе
достаточно локального запуска, отложи его и вернись позже.

## Что понадобится

- Сервер с Docker и Docker Compose (подойдёт любой VPS на Ubuntu).
- Домен, который можно направить на этот сервер.
- Reverse-proxy на сервере, который держит порты 80/443 и выдаёт HTTPS-сертификаты.
  В примере ниже — Traefik, но принцип тот же для Caddy или nginx.

## Как это устроено

```
Интернет
   │  домен → IP сервера
   ▼
Reverse-proxy (Traefik) на портах 80/443
   │  читает labels контейнера и сам выдаёт сертификат
   ▼
api (FastAPI, порт 8000 только внутри сети)
   │
   ▼
db (PostgreSQL, наружу вообще не смотрит)
```

**Сервис не публикует порты в интернет.** Это осознанное решение: любой опубликованный
порт Docker доступен снаружи в обход firewall. Единственный публичный вход — proxy,
который сам терминирует HTTPS.

## Шаг 1. Подготовь сервер

```bash
# Docker и compose
curl -fsSL https://get.docker.com | sh

# Проверить
docker --version && docker compose version
```

Дальше нужен reverse-proxy. Минимальный Traefik, который сам выписывает сертификаты:

```bash
# сеть, в которой будет жить proxy
docker network create traefik
```

```yaml
# /opt/traefik/docker-compose.yml
services:
  traefik:
    image: traefik:v3
    restart: always
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=you@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_data:/letsencrypt
    networks:
      - traefik

volumes:
  traefik_data:

networks:
  traefik:
    name: traefik
```

```bash
cd /opt/traefik && docker compose up -d
```

Важно: `exposedbydefault=false` означает, что контейнер попадает в proxy только если
у него есть labels с `traefik.enable=true`. Это защита от случайной публикации.

## Шаг 2. DNS

Создай A-запись: `radar.твой-домен` → IP сервера. Проверь, что запись разошлась:

```bash
dig +short radar.твой-домен
```

Не продолжай, пока не увидишь IP сервера: сертификат не выпишется, если домен
ещё не указывает на сервер.

## Шаг 3. Код на сервере

```bash
git clone <адрес-твоего-репозитория> /opt/content-radar-ai
cd /opt/content-radar-ai
cp .env.example .env
```

Если репозиторий приватный, используй отдельный ключ только для этого репозитория:
создай на сервере ключ, добавь его публичную часть как Deploy Key с правом только на
чтение, а в `~/.ssh/config` заведи удобный алиас. Ключ с правом записи на сервере не нужен.

## Шаг 4. Настройки под сервер

Допиши в `.env`:

```env
ENVIRONMENT=production
APP_DOMAIN=radar.твой-домен
TRAEFIK_NETWORK=traefik
TRAEFIK_CERTRESOLVER=letsencrypt
STACK_SUBNET=10.247.0.0/24
```

Про `STACK_SUBNET`: на серверах с большим количеством проектов у Docker заканчиваются
свободные диапазоны адресов, и сеть без явной подсети просто не создаётся с ошибкой
`all predefined address pools have been fully subnetted`. Явная подсеть это лечит.
Выбирай диапазон, не пересекающийся с другими стеками, и не трогай чужие сети.

Пароль базы обязательно поменяй с `change-me` на свой:

```bash
openssl rand -hex 24
```

Права на файл с секретами:

```bash
chmod 600 .env
```

## Шаг 5. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

Проверка:

```bash
curl -s https://radar.твой-домен/healthz
curl -s https://radar.твой-домен/api/sources
```

Первый запрос к домену может занять несколько секунд: proxy выписывает сертификат.

## Обновление версии

```bash
cd /opt/content-radar-ai
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
```

Или одной командой через готовый скрипт:

```bash
VPS_HOST=root@203.0.113.10 APP_DOMAIN=radar.твой-домен ./deploy/deploy.sh
```

## Правила, которые стоит соблюдать на общем сервере

- Не публикуй порты сервиса в интернет. Только proxy и labels.
- Не храни секреты в репозитории и не передавай их в чат.
- Перед правкой общих файлов других проектов делай резервную копию.
- Новый сервис ставь в отдельный каталог и отдельный compose-проект.
- Не запускай `docker system prune` на боевом сервере просто так: можно снести чужие
  неиспользуемые образы и надолго загрузить диск.
- Проверяй занятость портов и подсетей до запуска, а не после.

## Если что-то не работает

```bash
docker compose -f docker-compose.prod.yml ps        # состояние сервисов
docker compose -f docker-compose.prod.yml logs --tail 100 api
docker inspect <имя-контейнера> --format '{{json .State.Health}}'
```

**Сертификат не выписывается.** Почти всегда: DNS ещё не разошёлся, порт 80 закрыт,
или домен уже занят другим роутером в proxy.

**502 от proxy.** Контейнер не поднялся или слушает другой порт. Сверь
`loadbalancer.server.port=8000` в `docker-compose.prod.yml` и `EXPOSE` в Dockerfile.

**`all predefined address pools have been fully subnetted`.** Задай `STACK_SUBNET`
в `.env` — свободный диапазон, не пересекающийся с другими проектами.

**Контейнер healthy, а снаружи недоступен.** Проверь, что api подключён к внешней сети
(`TRAEFIK_NETWORK`) и что label `traefik.docker.network` указывает именно на неё.
