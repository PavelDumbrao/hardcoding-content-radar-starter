# AI First Content Radar
## Персональный AI-сервис поиска вирусного контента, конкурентов, идей и аудитории

**Статус:** Architecture Blueprint / Source of Truth  
**Формат:** Personal AI First Service  
**Основной UX:** Chat-first  
**Приоритетные платформы V1:** YouTube + VK  
**Следующий приоритет:** Instagram Reels  
**Цель:** находить лучшие контент-механики, тренды, конкурентов и околоконкурентов, понимать причины вирусности и превращать найденные сигналы в идеи, адаптированные под пользователя.

---

# 1. Product Vision

Сервис должен работать как ChatGPT для контент-разведки.

Пользователь не обязан вручную строить фильтры, искать конкурентов, собирать ролики, читать сотни комментариев и сравнивать метрики.

Пример запроса:

> Найди, что за последние 14 дней начинает залетать в русскоязычном и англоязычном Vibe Coding. Посмотри YouTube и VK. Найди прямых конкурентов и околоконкурентов. Покажи 20 лучших механик, которые можно адаптировать под меня.

Ожидаемый результат:

- найденные ролики;
- ссылки на оригиналы;
- свежие метрики;
- Trend Score;
- Outlier Score;
- Audience Score;
- Content DNA;
- Audience DNA;
- объяснение, почему ролик работает;
- сегменты аудитории;
- боли / вопросы / возражения из комментариев;
- способ адаптации механики;
- готовые идеи новых роликов;
- подтверждение источниками и временем последнего измерения.

---

# 2. Главный принцип

## AI управляет исследованием. Данные и scoring остаются детерминированными.

LLM отвечает за:

- понимание запроса;
- расширение ниши;
- поиск смежных тематик;
- выбор нужных tools;
- построение гипотез;
- интерпретацию Content DNA;
- интерпретацию Audience DNA;
- объяснение причин;
- генерацию новых идей.

Обычный код отвечает за:

- API;
- collectors;
- дедупликацию;
- метрики;
- timestamps;
- фильтры;
- velocity;
- acceleration;
- outlier;
- хранение;
- расчёт score;
- freshness;
- ограничения источников.

LLM **никогда не придумывает просмотры, лайки, даты, комментарии или scoring**.

---

# 3. Конечный пользовательский интерфейс

Главный интерфейс — чат.

```text
┌──────────────────────────────────────────────────────┐
│                   CONTENT RADAR AI                   │
│                                                      │
│ Ты:                                                  │
│ Что мне сегодня снять про Vibe Coding?               │
│                                                      │
│ AI:                                                  │
│ За последние 24 часа я проверил:                     │
│ YouTube: 1 842 ролика                                │
│ VK:       617 роликов                                │
│                                                      │
│ Нашёл:                                               │
│ 🔥 12 breakout                                       │
│ ⚡ 31 accelerating                                    │
│ 💎 18 сильных evergreen                              │
│                                                      │
│ Лучшие возможности ↓                                 │
│                                                      │
│ [Video Card]                                         │
│ [Video Card]                                         │
│ [Idea Card]                                          │
└──────────────────────────────────────────────────────┘
```

Пример карточки:

```text
🔥 Trend Score: 91/100
🎯 Opportunity Score: 94/100

YouTube
127 400 просмотров
+18 300 views/hour
Outlier: 8.7×
Возраст: 17 часов

HOOK:
«Я заменил программиста на AI за 30 минут»

АУДИТОРИЯ:
- предприниматели без технического опыта
- начинающие вайбкодеры

ЧТО ПИШУТ В КОММЕНТАРИЯХ:
- «как это повторить?»
- «сколько стоит?»
- «можно ли без программиста?»

ПОЧЕМУ РАБОТАЕТ:
- конкретный срок;
- заметная трансформация;
- AI vs специалист;
- демонстрация результата;
- сильный curiosity gap.

КАК АДАПТИРОВАТЬ:
«Я дал GPT задачу разработчика за 150 000 ₽.
Вот что он сделал за 47 минут.»

[Оригинал]
```

---

# 4. Высокоуровневая архитектура

```text
                         ┌─────────────────────┐
                         │      CHAT UI        │
                         │ Next.js             │
                         │ assistant-ui        │
                         └─────────┬───────────┘
                                   │
                                   ▼
                    ┌───────────────────────────┐
                    │      CONTENT AGENT        │
                    │                           │
                    │       PydanticAI          │
                    │                           │
                    │ Intent → Plan → Tools     │
                    └───────────┬───────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
 ┌────────────────┐    ┌────────────────┐    ┌─────────────────┐
 │ DISCOVERY      │    │ TREND ENGINE   │    │ AI SEARCH       │
 │                │    │                │    │                 │
 │ competitors    │    │ velocity       │    │ semantic search │
 │ niches         │    │ acceleration   │    │ similarity      │
 │ videos         │    │ outlier        │    │ content DNA     │
 └───────┬────────┘    └───────┬────────┘    └────────┬────────┘
         │                     │                      │
         └─────────────────────┼──────────────────────┘
                               ▼
                  ┌──────────────────────────┐
                  │    CONTENT DATABASE      │
                  │ PostgreSQL + pgvector    │
                  └───────────┬──────────────┘
                              │
               ┌──────────────┴───────────────┐
               ▼                              ▼
      ┌─────────────────┐            ┌────────────────┐
      │ YouTube Adapter │            │ VK Adapter     │
      └─────────────────┘            └────────────────┘
               │                              │
               └──────────────┬───────────────┘
                              ▼
                     ┌──────────────────┐
                     │ Source Layer     │
                     │ APIs / Collectors│
                     └──────────────────┘
```

Дополнительно:

```text
VIDEO
  │
  ├── Metrics Intelligence
  │      views / likes / velocity / outlier
  │
  ├── Content Intelligence
  │      transcript / scenes / hook / format
  │
  └── Audience Intelligence
         comments / replies / pains / questions
```

---

# 5. Платформы

## V1 — обязательные

1. YouTube
2. VK / VK Clips

## V2

3. Instagram Reels

## V3

4. TikTok
5. Telegram
6. Rutube
7. Дзен

---

# 6. Source Adapter Contract

Все платформы подключаются через единый контракт.

```python
class SocialSourceAdapter:

    async def search_videos(self, query, filters):
        ...

    async def get_video(self, platform_video_id):
        ...

    async def get_creator(self, creator_id):
        ...

    async def get_creator_videos(self, creator_id, filters):
        ...

    async def get_comments(self, platform_video_id, filters):
        ...

    async def refresh_metrics(self, platform_video_ids):
        ...
```

Важно:

- бизнес-логика не зависит напрямую от API конкретной площадки;
- источник можно заменить;
- можно иметь primary/fallback collector;
- можно менять API без переписывания Trend Engine или AI Agent.

---

# 7. YouTube Adapter

## Основной источник

YouTube Data API.

Нужен для:

- keyword discovery;
- поиска каналов;
- поиска видео;
- metadata;
- statistics;
- comments;
- replies;
- регулярных snapshot метрик.

Полезные endpoints:

- `search.list`
- `videos.list`
- `videos.batchGetStats` — для пакетного обновления статистики
- `commentThreads.list`
- `comments.list`

## Transcript

Порядок:

1. официальные / доступные captions;
2. `youtube-transcript-api`;
3. STT fallback.

## Media fallback

`yt-dlp`

Использовать только там, где это допустимо для нашего режима анализа и с учётом правил источника.

---

# 8. VK Adapter

## Основной источник

VK API.

Нужен для:

- video discovery;
- VK Clips;
- communities;
- wall posts;
- video metadata;
- comments;
- replies;
- creator/community analysis.

Рекомендуемые кирпичи:

- `VKCOM/vk-api-schema`
- `python273/vk_api`

Контракт остаётся нашим.

---

# 9. Instagram Adapter

Для своих Professional Accounts:

- официальный Instagram API.

Для публичного competitor research:

```text
InstagramCommentsAdapter

Primary:
Apify

Fallback:
Bright Data
```

Тот же принцип для Reels discovery.

Instagram ingestion считается более хрупким, поэтому всегда минимум два заменяемых provider'а.

---

# 10. Niche Graph

Сервис не должен искать только точные ключевые слова.

Пример:

```text
                         Vibe Coding
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
       AI Coding        No-code          AI Business
             │                │                │
             ▼                ▼                ▼
        Cursor           Lovable           Agents
        Claude Code      Replit            Automation
        Codex            Bolt              Productivity
```

Каждый найденный creator классифицируется как:

- `DIRECT_COMPETITOR`
- `ADJACENT_COMPETITOR`
- `AUDIENCE_COMPETITOR`
- `FORMAT_REFERENCE`
- `GLOBAL_REFERENCE`

Цель — находить не только тех, кто говорит теми же словами, но и тех, кто борется за ту же аудиторию или использует переносимую механику.

---

# 11. Competitor Discovery

Сервис должен уметь находить конкурентов автоматически.

Источники сигналов:

- ключевые слова;
- семантическая близость;
- аудитория;
- комментарии;
- повторяющиеся темы;
- похожие creators;
- пересечение тем;
- похожий формат;
- похожие promises;
- похожие CTA.

Результат:

```json
{
  "creator_id": "x",
  "relationship": "ADJACENT_COMPETITOR",
  "confidence": 0.88,
  "reasons": [
    "shared audience",
    "same problem space",
    "similar content mechanics"
  ]
}
```

---

# 12. Snapshot Engine

Для viral detection нужна история.

Таблица:

```text
video_snapshots

video_id
observed_at
views
likes
comments
shares
```

Пример:

```text
10:00   1 400 views
11:00   2 100
12:00   5 600
13:00  14 900
14:00  37 000
```

Главная ценность — не абсолютное число просмотров, а динамика.

---

# 13. Trend Engine

## View Velocity

```text
velocity = Δviews / Δtime
```

## Acceleration

```text
acceleration = Δvelocity / Δtime
```

## Comment Velocity

```text
comment_velocity = Δcomments / Δtime
```

## Engagement Velocity

Дополнительно:

- like velocity;
- share velocity;
- reply velocity.

---

# 14. Outlier Engine

Видео оценивается относительно обычной производительности автора.

Пример:

```text
Медиана автора:
12 000 просмотров за 72 часа

Новое видео:
96 000 просмотров за 24 часа

Outlier ≈ 8×+
```

Нельзя использовать только среднее: старые вирусные ролики искажают baseline.

Приоритет:

- median;
- percentile baseline;
- нормализация по возрасту ролика;
- нормализация по размеру канала.

---

# 15. Trend Score

Стартовая эвристика:

```text
TrendScore =

30% velocity
20% acceleration
20% creator outlier
10% engagement
10% freshness
10% niche relevance
```

Веса должны храниться в конфиге.

Позже возможна supervised calibration на собственных historical outcomes.

---

# 16. Reference Score

Trend и historical reference — разные задачи.

`Trend Score`:

> Что начинает расти сейчас?

`Reference Score`:

> Что доказанно хорошо сработало за выбранный период?

Reference Score может учитывать:

- итоговые просмотры;
- outlier;
- engagement quality;
- audience quality;
- content adaptability;
- longevity;
- relevance.

---

# 17. Video Intelligence Pipeline

```text
VIDEO URL
    │
    ▼
 yt-dlp / API
    │
    ├── audio
    └── video
          │
          ├───────────────┐
          ▼               ▼
 youtube transcript    PySceneDetect
 / STT fallback            │
          │             scenes
          ▼               │
      transcript           │
          └──────┬─────────┘
                 ▼
             Vision LLM
                 │
                 ▼
            CONTENT DNA
```

---

# 18. STT Layer

Приоритет:

1. platform transcript;
2. `youtube-transcript-api`;
3. `faster-whisper`;
4. `WhisperX`, когда нужны alignment / diarization.

Open-source:

- `jdepoix/youtube-transcript-api`
- `SYSTRAN/faster-whisper`
- `m-bain/whisperX`

---

# 19. Scene Detection

Использовать:

- `Breakthrough/PySceneDetect`
- `FFmpeg`

Цель:

не анализировать каждый кадр.

Нужно получить:

- shot boundaries;
- representative frames;
- количество сцен;
- average scene length;
- pacing.

---

# 20. Content DNA

Для каждого сильного ролика создаётся структурированный профиль.

```json
{
  "topic": "AI coding",
  "subtopics": [
    "Claude Code",
    "automation"
  ],

  "audience": "entrepreneurs",

  "format": "talking_head_screen_demo",

  "hook": {
    "text": "Я уволил программиста после этого",
    "type": "provocation",
    "strength": 0.91
  },

  "structure": [
    "hook",
    "problem",
    "demo",
    "proof",
    "cta"
  ],

  "visual_style": "fast_screen_demo",

  "editing": {
    "pace": "fast",
    "scene_changes": 14
  },

  "emotion": [
    "surprise",
    "curiosity"
  ],

  "cta": "comment_keyword",

  "promise": "save money",
  "proof_type": "live_demo"
}
```

---

# 21. Audience Intelligence

Комментарии — обязательный слой.

Система должна понимать:

- кто реально реагирует;
- почему ролик цепляет;
- что люди хотят;
- что не понимают;
- что мешает покупке/действию;
- какие темы просят раскрыть;
- какие сегменты аудитории проявляются.

Не нужно строить психологический профиль отдельных людей.

Нужно агрегировать общественные сигналы.

---

# 22. Comment Collection

## YouTube

Собирать:

- top relevant comments;
- newest comments;
- replies;
- likes;
- reply count.

Практичный sample:

```text
TOP 100 by relevance
+
NEWEST 100
+
replies к 20–30 самым важным threads
```

Не нужно собирать все 20 000 комментариев под каждым видео.

## VK

Собирать:

- text;
- author/group;
- likes;
- replies;
- thread depth.

## Instagram

Primary:

- Apify.

Fallback:

- Bright Data.

---

# 23. Comment Intelligence

Каждый комментарий можно классифицировать по сигналам:

```text
question
pain
objection
desire
experience
purchase_intent
content_request
agreement
disagreement
spam
other
```

Дополнительно:

- language;
- semantic embedding;
- toxicity/spam quality;
- usefulness;
- reply depth.

---

# 24. Audience DNA

Для видео формируется агрегированный профиль.

```json
{
  "audience": [
    {
      "segment": "предприниматели без технического опыта",
      "share_estimate": 0.38,
      "signals": [
        "как сделать без программиста?",
        "можно ли внедрить это в бизнес?"
      ]
    },
    {
      "segment": "начинающие разработчики",
      "share_estimate": 0.24
    }
  ],

  "pains": [
    "дорогие разработчики",
    "сложно разобраться в AI",
    "непонятно с чего начать"
  ],

  "questions": [
    "какой AI использован?",
    "сколько это стоит?",
    "есть инструкция?"
  ],

  "objections": [
    "AI всё равно ошибается",
    "для реального бизнеса не подходит"
  ],

  "desires": [
    "автоматизировать работу",
    "сделать приложение самому",
    "сократить расходы"
  ],

  "content_requests": [
    "покажи полный туториал",
    "сравни Claude Code и Codex"
  ]
}
```

---

# 25. Comment Quality Metrics

Важные показатели:

- `Comment Velocity`
- `Meaningful Comment Rate`
- `Question Density`
- `Experience Sharing Rate`
- `Reply Depth`
- `Comment Like Score`
- `Purchase / Action Intent`
- `Content Request Density`
- `Unique Audience Cluster Count`

Пример:

```text
100 000 views
500 comments
310 meaningful
```

может быть ценнее:

```text
1 000 000 views
2 000 comments
80 meaningful
```

---

# 26. Semantic Search

Нужен поиск не только по словам, но и по смыслу.

Пример:

> Найди видео, где предприниматели хотят сэкономить на разработчиках с помощью AI.

Сервис должен найти даже ролик:

> Я сократил отдел разработки с пяти человек до двух.

Даже если в нём нет точных слов из запроса.

---

# 27. Embeddings

Для первого релиза:

- BGE-M3
- PostgreSQL + pgvector

BGE-M3 подходит для multilingual RU/EN retrieval.

Embeddings создаём для:

- title;
- description;
- transcript chunks;
- Content DNA;
- comments;
- Audience DNA;
- generated idea signatures.

---

# 28. Personal Preference Engine

Система должна обучаться вкусу пользователя.

Feedback:

```text
👍 Хочу такое
👎 Не моё
⭐ Сохранить
🎬 Снять
```

Система постепенно накапливает предпочтения.

Пример:

```text
нравится:
- live demo
- конкретные цифры
- AI vs human
- before/after
- бизнес-эффект
- provocation

не нравится:
- generic AI news
- мотивация без доказательств
- пустые мемы
```

---

# 29. Opportunity Score

Итоговая модель:

```text
OpportunityScore =

Virality
×
Niche Relevance
×
Audience Relevance
×
Personal Fit
×
Adaptability
×
Novelty
```

Практически лучше считать нормализованным weighted score, а не буквальным перемножением.

Пример компонентов:

```text
ViralityScore
ContentFitScore
AudienceFitScore
PersonalFitScore
AdaptabilityScore
MarketGapScore
FreshnessScore
```

---

# 30. Cross-Market Gap Detection

Отдельный сильный режим:

```text
US / EN trends
       ↓
semantic clustering
       ↓
RU YouTube / VK
       ↓
penetration analysis
```

Запрос:

> Что сейчас растёт в США, но ещё почти никто не делает в России?

Ответ:

- trend cluster;
- количество EN breakout videos;
- количество RU analogues;
- audience signal;
- content gap;
- recommended adaptation.

---

# 31. Adapt, Don't Clone

Сервис не должен тупо копировать чужие ролики.

Он должен извлекать механику.

```text
ORIGINAL

«Я построил SaaS за 24 часа»

↓ CONTENT MECHANIC ↓

deadline challenge
+ visible result
+ live build
+ curiosity

↓ ADAPTATION ↓

«Я за 24 часа попробовал заменить
маркетолога AI-агентом. Вот результат.»
```

Извлекаем:

- hook;
- promise;
- conflict;
- format;
- proof;
- pacing;
- CTA;
- audience;
- objections;
- transferable mechanic.

---

# 32. Agent Tools

Главный AI Agent получает типизированные tools.

```text
search_youtube
search_vk
search_instagram

discover_creators
find_direct_competitors
find_adjacent_competitors

get_recent_videos
get_video_metrics
get_comments

find_trending
find_outliers

semantic_video_search
semantic_comment_search

analyze_video
analyze_audience

compare_creators
find_content_patterns
find_market_gaps

generate_content_ideas

save_reference
save_idea
add_creator_to_watchlist
record_feedback
```

---

# 33. PydanticAI

Используется как основной agent framework.

Почему:

- типизированные tools;
- structured outputs;
- toolsets;
- MCP support;
- Python ecosystem;
- простая интеграция с FastAPI.

Не нужно строить multi-agent архитектуру на старте.

V1:

```text
1 Main Agent
+
deterministic tools
```

---

# 34. Chat UI

Рекомендуется:

- Next.js;
- assistant-ui.

UI должен поддерживать:

- streaming;
- tool status;
- cards;
- inline sources;
- save;
- feedback;
- follow-up;
- filters внутри ответа;
- preview найденных роликов.

---

# 35. Database

Основная база:

**PostgreSQL + pgvector**

Таблицы:

```text
users
user_preferences

niches
topics
topic_relations

creators
creator_relationships
creator_snapshots

videos
video_snapshots

video_transcripts
video_scenes
video_features
video_embeddings

comments
comment_features
comment_embeddings

video_audience_profiles

trend_scores
reference_scores
opportunity_scores

references
ideas
feedback

watchlists
research_runs
source_events
```

---

# 36. Пример схемы comments

```text
comments
---------
id
platform
external_id
video_id
author_id_hash
text
created_at
likes
reply_count
parent_id
observed_at
```

---

# 37. comment_features

```text
comment_features
----------------
comment_id
language
intent
pain
question
objection
desire
experience
purchase_intent
content_request
spam_score
quality_score
embedding
```

---

# 38. video_audience_profiles

```text
video_audience_profiles
-----------------------
video_id
generated_at
audience_clusters
pain_clusters
question_clusters
objection_clusters
desire_clusters
content_requests
comment_quality_score
audience_fit_score
```

---

# 39. Freshness Contract

Любая цифра в пользовательском ответе должна иметь:

```text
source
observed_at
value
```

Пример:

```text
Source: YouTube API
Observed: 2026-09-22 09:32
Views: 92 134
```

Агент не должен говорить:

> сейчас 92k

если последняя метрика была измерена три дня назад.

---

# 40. Processing Strategy

Не анализировать все ролики тяжёлым AI.

Правильный funnel:

```text
100 000 найденных видео
        ↓
10 000 релевантных
        ↓
1 000 statistical candidates
        ↓
200 strong candidates
        ↓
comments enrichment
        ↓
100 video AI analysis
        ↓
50–100 final references
```

Это главный принцип контроля стоимости.

---

# 41. Job Types

## Frequent jobs

- metric snapshots;
- watchlist updates;
- breakout detection.

## Medium frequency

- niche discovery;
- competitor discovery;
- new creator detection.

## On-demand

- historical research;
- deep comments;
- video multimodal analysis;
- cross-market analysis.

---

# 42. Scheduler

Для личного сервиса достаточно:

- lightweight worker;
- Redis;
- cron / scheduler.

Не нужны:

- Kafka;
- Kubernetes;
- complex event bus.

---

# 43. Object Storage

Хранить только то, что действительно нужно.

S3-compatible storage:

- temporary media;
- extracted audio;
- keyframes;
- thumbnails;
- derived artifacts.

Не строить собственную библиотеку чужих видео без необходимости.

---

# 44. Recommended Stack

| Layer | Choice |
|---|---|
| UI | Next.js + assistant-ui |
| Backend | Python + FastAPI |
| Agent | PydanticAI |
| Database | PostgreSQL |
| Vector | pgvector |
| Embeddings | BGE-M3 |
| YouTube | Official Data API |
| VK | Official VK API |
| Instagram | Official API / Apify / Bright Data |
| Download | yt-dlp |
| Media | FFmpeg |
| Captions | youtube-transcript-api |
| STT | faster-whisper / WhisperX |
| Scene Detection | PySceneDetect |
| Jobs | Redis + worker |
| Storage | S3-compatible |
| Deployment | Docker Compose |
| Observability | structured logs + metrics |

---

# 45. Open-Source Building Blocks

## Agent / UI

- https://github.com/pydantic/pydantic-ai
- https://github.com/assistant-ui/assistant-ui

## Data / Search

- https://github.com/pgvector/pgvector
- https://github.com/FlagOpen/FlagEmbedding

## Video

- https://github.com/yt-dlp/yt-dlp
- https://github.com/jdepoix/youtube-transcript-api
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/m-bain/whisperX
- https://github.com/Breakthrough/PySceneDetect

## VK

- https://github.com/VKCOM/vk-api-schema
- https://github.com/python273/vk_api

---

# 46. Что берём готовым

Максимально reuse:

```text
Chat UI
Agent tool framework
Postgres vector
Embeddings
Video download
Captions
STT
Scene detection
VK SDK/API schema
YouTube official API
Instagram collectors
```

---

# 47. Что является нашим IP

Пишем сами:

```text
Niche Graph Engine

Competitor Discovery
Adjacent Competitor Discovery

Source Normalization

Snapshot Engine

Trend Engine
Outlier Engine

Content DNA Schema
Audience DNA Schema

Comment Intelligence

Personal Preference Engine

Opportunity Score

Cross-Market Gap Detection

Content Idea Synthesizer
```

---

# 48. Repository Structure

```text
content-radar-ai/
│
├── apps/
│   ├── web/
│   └── api/
│
├── packages/
│   ├── agent/
│   ├── domain/
│   ├── scoring/
│   ├── search/
│   ├── intelligence/
│   └── shared/
│
├── adapters/
│   ├── youtube/
│   ├── vk/
│   ├── instagram/
│   ├── embeddings/
│   ├── llm/
│   ├── storage/
│   └── stt/
│
├── workers/
│   ├── discovery/
│   ├── metrics/
│   ├── comments/
│   ├── video_ai/
│   └── embeddings/
│
├── migrations/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker/
│
├── docs/
│
├── docker-compose.yml
└── README.md
```

---

# 49. Domain Objects

Главные сущности:

```text
Niche
Topic
Creator
CreatorRelationship
Video
VideoSnapshot
Comment
CommentFeature
ContentDNA
AudienceDNA
TrendScore
ReferenceScore
OpportunityScore
Idea
Feedback
ResearchRun
Watchlist
```

---

# 50. ResearchRun

Каждый пользовательский сложный запрос желательно сохранять как research run.

```json
{
  "id": "run_x",
  "query": "что снять про vibe coding",
  "started_at": "...",
  "sources": ["youtube", "vk"],
  "filters": {},
  "status": "completed",
  "candidates_found": 1842,
  "final_results": 20
}
```

Это даёт:

- воспроизводимость;
- debug;
- историю;
- audit trail;
- сравнение качества выдачи.

---

# 51. MVP — 5 блоков

## Block 1 — Foundation

Цель:

рабочий Chat → Tools → YouTube/VK → ответ.

Состав:

```text
Next.js
assistant-ui
FastAPI
PydanticAI
PostgreSQL
pgvector
YouTube Adapter
VK Adapter
```

Acceptance:

> запрос «найди ролики про Vibe Coding» возвращает реальные YouTube/VK результаты со ссылками и свежими метриками.

---

## Block 2 — Intelligence

Состав:

```text
Niche Graph
Competitor Discovery
Adjacent Competitors
Snapshot Engine
Trend Engine
Outlier Engine
```

Acceptance:

> запрос «что сейчас начинает залетать?» возвращает breakout/accelerating видео с объяснимым scoring.

---

## Block 3 — Video Brain

Состав:

```text
transcripts
STT
PySceneDetect
Vision analysis
Content DNA
embeddings
semantic search
```

Acceptance:

> запрос «найди ролики с провокационным hook и live-demo» работает по смыслу, а не только по title.

---

## Block 4 — Audience Brain

Состав:

```text
comments collectors
reply collectors
comment embeddings
comment classification
Audience DNA
Audience Score
```

Acceptance:

> запрос «найди видео, где предприниматели спрашивают, как повторить это самим» работает по комментариям.

---

## Block 5 — Personal Autonomous Radar

Состав:

```text
feedback
personal preferences
Opportunity Score
watchlists
scheduled discovery
alerts
cross-market gap detection
idea generation
```

Acceptance:

> запрос «что мне сегодня снять?» возвращает персонально ранжированные идеи с доказательствами.

---

# 52. E2E User Scenarios

## Scenario 1

> Что сейчас вирусится в Vibe Coding на русском?

Система:

1. строит semantic query;
2. ищет YouTube + VK;
3. фильтрует freshness;
4. считает Trend Score;
5. сортирует;
6. анализирует Content DNA top candidates;
7. выдаёт список.

---

## Scenario 2

> Найди мне конкурентов Hard Coding Pro.

Система:

1. строит niche graph;
2. находит creators;
3. считает relationship;
4. делит direct/adjacent/audience/format;
5. показывает доказательства классификации.

---

## Scenario 3

> Почему этот ролик залетел?

Система:

1. metrics;
2. outlier;
3. transcript;
4. Content DNA;
5. comments;
6. Audience DNA;
7. объяснение;
8. transferable mechanic.

---

## Scenario 4

> Что аудитория хочет узнать дальше?

Система:

1. получает comments;
2. группирует questions;
3. группирует content requests;
4. считает frequency;
5. выдаёт темы следующих роликов.

---

## Scenario 5

> Что растёт в США, но ещё не дошло до России?

Система:

1. EN discovery;
2. breakout clusters;
3. RU semantic search;
4. penetration score;
5. market gap;
6. идеи адаптации.

---

# 53. Quality Rules

Сервис обязан:

- показывать source;
- показывать observed_at;
- не выдумывать цифры;
- отделять факт от AI interpretation;
- не считать старую метрику текущей;
- дедуплицировать видео;
- учитывать platform-specific ограничения;
- не зависеть от одного scraper/provider;
- сохранять evidence.

---

# 54. Cost Control Rules

1. Сначала metadata.
2. Потом statistical filtering.
3. Потом comments enrichment.
4. Потом transcript.
5. Потом heavy VLM.
6. Только top candidates проходят полный анализ.

Никакого full multimodal анализа всего потока.

---

# 55. Reliability Rules

Для каждого внешнего источника:

```text
Primary
Fallback
Circuit breaker
Retry policy
Rate limit handling
Freshness status
```

Никаких blind retry после неизвестного результата.

---

# 56. Security

Минимально:

- secrets only via env / secret store;
- API keys не попадать в logs;
- internal user auth;
- rate limits;
- provider isolation;
- audit logs для external calls;
- хранить только необходимый пользовательский контекст.

---

# 57. Observability

Минимальные метрики:

```text
collector_success_rate
collector_latency
videos_discovered
snapshots_written
comments_collected
AI_jobs_completed
AI_cost
embedding_jobs
trend_candidates
source_errors
stale_results
```

---

# 58. Что НЕ делать на V1

Не нужны:

- Kubernetes;
- Kafka;
- Elasticsearch;
- Qdrant отдельно от Postgres;
- десятки микросервисов;
- multi-agent swarm;
- полный scraping всех соцсетей;
- постоянное хранение всех чужих видео;
- сложная ML-модель вирусности до накопления данных.

---

# 59. First Technical Milestone

Самый первый реальный milestone:

```text
USER
  ↓
Chat UI
  ↓
PydanticAI
  ↓
search_youtube()
search_vk()
  ↓
Normalize results
  ↓
PostgreSQL
  ↓
Agent response with sources
```

После этого можно начинать Trend Engine.

---

# 60. Definition of Done V1

V1 считается готовой, когда пользователь может открыть сервис и написать:

> Найди мне 20 лучших роликов про Vibe Coding за последние 30 дней на YouTube и VK. Учти не только просмотры, но и outlier относительно автора. Проанализируй комментарии у лучших роликов, скажи, кто аудитория, какие у неё боли и вопросы, и придумай 10 механик, которые можно адаптировать под меня.

И сервис:

1. реально обращается к источникам;
2. находит реальные видео;
3. хранит свежие метрики;
4. считает Trend/Outlier;
5. анализирует Content DNA;
6. анализирует Audience DNA;
7. показывает ссылки;
8. показывает freshness;
9. не придумывает данные;
10. генерирует персонализированные идеи.

---

# 61. Source References

## YouTube

- https://developers.google.com/youtube/v3/docs/search/list
- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/comments/list

## VK

- https://github.com/VKCOM/vk-api-schema
- https://github.com/python273/vk_api

## Instagram / external ingestion

- https://apify.com/
- https://brightdata.com/

## Open Source

- https://github.com/pydantic/pydantic-ai
- https://github.com/assistant-ui/assistant-ui
- https://github.com/pgvector/pgvector
- https://github.com/FlagOpen/FlagEmbedding
- https://github.com/yt-dlp/yt-dlp
- https://github.com/jdepoix/youtube-transcript-api
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/m-bain/whisperX
- https://github.com/Breakthrough/PySceneDetect

---

# 62. Next Action

Следующий этап — не новый research.

Следующий этап:

## Создать репозиторий и реализовать Block 1 до рабочего E2E.

Порядок:

```text
1. Repository bootstrap
2. Docker Compose
3. PostgreSQL + pgvector
4. FastAPI
5. PydanticAI agent
6. YouTube Adapter
7. VK Adapter
8. Chat UI
9. E2E query
10. Evidence verification
11. Checkpoint
```

После верифицированного Block 1 переходить к Block 2.

---

# Final Architecture Principle

> **AI управляет исследованием.  
> Источники дают факты.  
> Код считает метрики.  
> Комментарии объясняют аудиторию.  
> Content DNA объясняет механику.  
> Audience DNA объясняет спрос.  
> Opportunity Score решает, что полезнее именно пользователю.**

