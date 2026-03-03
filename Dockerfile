FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m alembic upgrade head 2>/dev/null || true
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5678", "--workers", "1"]
