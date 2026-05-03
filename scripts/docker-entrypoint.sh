#!/bin/sh
# WENDRINK ERP — entrypoint для production контейнера.
#
# КЛЮЧЕВОЕ: alembic запускается ИМЕННО ЗДЕСЬ, в момент старта контейнера,
# а не на этапе RUN в Dockerfile. Причина: docker-compose.prod.yml монтирует
# хостовый wendrink.db поверх образного через volume mount. Build-stage
# применение миграций к /app/wendrink.db бесполезно — этот файл затирается
# volume mount при `docker run`. Только entrypoint видит реальную БД.
#
# Безопасность: alembic upgrade head — идемпотентный, повторный запуск
# не создаёт лишних миграций. При сбое — set -e остановит контейнер до
# uvicorn, и данные останутся в исходном состоянии (миграции idempotent).

set -e

echo "[entrypoint] Applying alembic migrations to mounted DB..."
alembic upgrade head

echo "[entrypoint] Starting uvicorn on 0.0.0.0:5678..."
exec uvicorn app.main:app --host 0.0.0.0 --port 5678 --workers 1
