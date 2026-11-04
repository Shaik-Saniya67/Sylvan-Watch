FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sylvan ./sylvan
COPY configs ./configs
COPY scripts ./scripts
COPY storage/models/random_forest.joblib ./storage/models/random_forest.joblib
COPY storage/results/metrics.json ./storage/results/metrics.json
ENV SYLVAN_STORAGE_DIR=/app/storage

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /data/storage/models /data/storage/results && cp -n /app/storage/models/random_forest.joblib /data/storage/models/ 2>/dev/null || true; cp -n /app/storage/results/metrics.json /data/storage/results/ 2>/dev/null || true; exec uvicorn sylvan.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
