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

ENV SYLVAN_STORAGE_DIR=/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn sylvan.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]