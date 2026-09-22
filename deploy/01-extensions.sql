-- Расширения Postgres для Content Radar AI.
-- pgvector нужен для семантического поиска (Block 3 по архитектуре),
-- поэтому включаем сразу, чтобы не пересоздавать БД позже.
CREATE EXTENSION IF NOT EXISTS vector;
