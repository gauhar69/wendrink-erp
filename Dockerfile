FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# alembic upgrade head вынесен в scripts/docker-entrypoint.sh,
# чтобы запускаться при старте контейнера (когда volume mount уже активен),
# а не на этапе build (где БД из образа затирается volume mount).
RUN chmod +x /app/scripts/docker-entrypoint.sh

CMD ["/app/scripts/docker-entrypoint.sh"]
